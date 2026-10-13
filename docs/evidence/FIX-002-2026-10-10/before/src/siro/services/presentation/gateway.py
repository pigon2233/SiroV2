"""Authenticated loopback HTTP/WebSocket presentation gateway."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import secrets
import shutil
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from functools import partial
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from siro.adapters.body.web import WebSocketBodyTransport
from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.memory import Memory, MemoryService
from siro.ports.models import ToolCall
from siro.services.agent.organization import MemoryOrganizer
from siro.services.audio.protocol import (
    AudioFrame,
    AudioMetadata,
    AudioRingBuffer,
    PlaybackOwnership,
)
from siro.services.audio.stt import SpeechToText
from siro.services.audio.tts import EdgeNeuralTTS, KokoroLocalTTS, QwenReferenceTTS, plan_speech
from siro.services.tools.execution import ExecutionContext
from siro.services.tools.orchestrator import (
    DEFAULT_MODEL_TOOLS,
    AvailabilityReason,
    AvailabilityState,
    ProposalState,
    ToolAvailability,
    ToolCatalog,
    ToolDescriptor,
    ToolExecutor,
    ToolMetadata,
    ToolOrchestrator,
    ToolProposal,
)
from siro.services.tools.workspace import WorkspaceRuntime


class JsonSocket(Protocol):
    async def send_json(self, data: object) -> None: ...

    async def close(self, code: int = 1000, reason: str | None = None) -> None: ...


class SpeechSynthesizer(Protocol):
    async def render(self, text: str, *, rate: float, pitch: float, energy: float) -> bytes: ...


class SessionTokens:
    class CapacityExceeded(RuntimeError):
        """All retained session tokens are still valid."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 300,
        max_tokens: int = 128,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_tokens < 1:
            raise ValueError("session token capacity must be positive")
        self._ttl = ttl_seconds
        self._max_tokens = max_tokens
        self._clock = clock
        self._tokens: dict[str, float] = {}

    def issue(self) -> tuple[str, float]:
        now = self._clock()
        self._tokens = {token: expiry for token, expiry in self._tokens.items() if expiry > now}
        if len(self._tokens) >= self._max_tokens:
            raise self.CapacityExceeded("session token capacity reached")
        token = secrets.token_urlsafe(32)
        expires_at = now + self._ttl
        self._tokens[token] = expires_at
        return token, self._ttl

    def valid(self, token: str) -> bool:
        expires_at = self._tokens.get(token)
        if expires_at is None:
            return False
        if self._clock() >= expires_at:
            self._tokens.pop(token, None)
            return False
        return True


@dataclass(slots=True)
class GatewayState:
    identity: dict[str, str] = field(
        default_factory=lambda: {"identity_id": "siro", "name": "SIRO"}
    )
    active_turns: dict[str, dict[str, str]] = field(default_factory=dict)
    health: dict[str, str] = field(default_factory=lambda: {"core": "healthy"})
    routes: dict[str, str] = field(
        default_factory=lambda: {"model": "local", "audio": "disabled", "body": "disabled"}
    )
    kill_switches: dict[str, bool] = field(
        default_factory=lambda: {"cloud": False, "tools": True, "microphone": False}
    )
    authorization_mode: str = "full"

    def snapshot(self) -> dict[str, object]:
        return {
            "type": "snapshot",
            "identity": dict(self.identity),
            "active_turns": dict(self.active_turns),
            "health": dict(self.health),
            "routes": dict(self.routes),
            "kill_switches": dict(self.kill_switches),
            "authorization_mode": self.authorization_mode,
        }


_RUN_PROGRESS_EVENTS = frozenset(
    {
        "assistant_started",
        "assistant_delta",
        "affect_state",
        "agent_step",
        "tool_proposal",
        "tool_started",
        "tool_result",
    }
)


class ClientChannel:
    def __init__(
        self,
        client_id: str,
        socket: JsonSocket,
        *,
        urgent_capacity: int,
        normal_capacity: int,
        terminal_fencing: bool = False,
    ) -> None:
        self.client_id = client_id
        self.socket = socket
        self.urgent: asyncio.Queue[dict[str, object]] = asyncio.Queue(urgent_capacity)
        self.normal: asyncio.Queue[dict[str, object]] = asyncio.Queue(normal_capacity)
        self.writer: asyncio.Task[None] | None = None
        self.closed = False
        self.terminal_fencing = terminal_fencing
        self._ended_streams: set[str] = set()
        self._ended_order: deque[str] = deque()
        self._fence_capacity = 5 * (urgent_capacity + normal_capacity) + 2

    def start(self) -> None:
        self.writer = asyncio.create_task(
            self._write_loop(), name=f"gateway-writer-{self.client_id}"
        )

    def enqueue(self, message: dict[str, object], *, urgent: bool = False) -> bool:
        queue = self.urgent if urgent else self.normal
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            return False
        return True

    async def stop(self, *, code: int = 1000, reason: str = "") -> None:
        if self.closed:
            return
        self.closed = True
        if self.writer is not None:
            self.writer.cancel()
            await asyncio.gather(self.writer, return_exceptions=True)
        # The peer may already be gone; cleanup remains idempotent.
        with contextlib.suppress(Exception):
            await self.socket.close(code=code, reason=reason or None)

    async def _write_loop(self) -> None:
        urgent_burst = 0
        while True:
            if not self.urgent.empty() and (urgent_burst < 4 or self.normal.empty()):
                message = await self.urgent.get()
                urgent_burst += 1
            elif not self.normal.empty():
                message = await self.normal.get()
                urgent_burst = 0
            else:
                urgent_get = asyncio.create_task(self.urgent.get())
                normal_get = asyncio.create_task(self.normal.get())
                done, pending = await asyncio.wait(
                    {urgent_get, normal_get}, return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                if urgent_get in done and normal_get in done:
                    # Both gets may complete in the same loop tick. Preserve the
                    # normal item instead of silently dropping it.
                    self.normal.put_nowait(normal_get.result())
                    selected = urgent_get
                else:
                    selected = done.pop()
                message = selected.result()
                urgent_burst = 1 if selected is urgent_get else 0
            stream_id = message.get("stream_id")
            kind = message.get("type")
            if (
                self.terminal_fencing
                and isinstance(stream_id, str)
                and stream_id in self._ended_streams
                and (kind in _RUN_PROGRESS_EVENTS or kind == "assistant_terminal")
            ):
                continue
            await self.socket.send_json(message)
            # Only this writer sends frames: after this await, no later frame from
            # this stream may resurrect it, regardless of queue arbitration.
            if (
                self.terminal_fencing
                and isinstance(stream_id, str)
                and kind == "assistant_terminal"
            ):
                self._ended_streams.add(stream_id)
                self._ended_order.append(stream_id)
                if len(self._ended_order) > self._fence_capacity:
                    self._ended_streams.discard(self._ended_order.popleft())


class GatewayHub:
    def __init__(self, *, urgent_capacity: int = 32, normal_capacity: int = 256) -> None:
        self._urgent_capacity = urgent_capacity
        self._normal_capacity = normal_capacity
        self._clients: dict[str, ClientChannel] = {}
        self._closing_tasks: set[asyncio.Task[None]] = set()
        self._terminal_fencing = False
        self._proposal_streams: dict[str, str] = {}

    def enable_terminal_fencing(self) -> None:
        self._terminal_fencing = True
        for channel in self._clients.values():
            channel.terminal_fencing = True

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, socket: JsonSocket, snapshot: dict[str, object]) -> ClientChannel:
        channel = ClientChannel(
            str(uuid4()),
            socket,
            urgent_capacity=self._urgent_capacity,
            normal_capacity=self._normal_capacity,
            terminal_fencing=self._terminal_fencing,
        )
        self._clients[channel.client_id] = channel
        channel.start()
        channel.enqueue(snapshot, urgent=True)
        return channel

    async def disconnect(self, channel: ClientChannel) -> None:
        self._clients.pop(channel.client_id, None)
        await channel.stop()

    async def broadcast(self, message: dict[str, object], *, urgent: bool = False) -> None:
        if self._terminal_fencing:
            stream_id, proposal_id = message.get("stream_id"), message.get("proposal_id")
            if not isinstance(stream_id, str) and isinstance(proposal_id, str):
                stream_id = self._proposal_streams.get(proposal_id)
                if stream_id is not None:
                    message = {**message, "stream_id": stream_id}
            if isinstance(stream_id, str):
                if message.get("type") == "tool_proposal" and isinstance(proposal_id, str):
                    self._proposal_streams[proposal_id] = stream_id
                elif message.get("type") == "assistant_terminal":
                    self._proposal_streams = {
                        key: value
                        for key, value in self._proposal_streams.items()
                        if value != stream_id
                    }
        overflowed: list[ClientChannel] = []
        for channel in tuple(self._clients.values()):
            if not channel.enqueue(message, urgent=urgent):
                self._clients.pop(channel.client_id, None)
                overflowed.append(channel)
        for channel in overflowed:
            task = asyncio.create_task(
                channel.stop(code=1013, reason="client queue capacity exceeded")
            )
            self._closing_tasks.add(task)
            task.add_done_callback(self._closing_tasks.discard)

    async def shutdown(self) -> None:
        channels = tuple(self._clients.values())
        self._clients.clear()
        await asyncio.gather(
            *(channel.stop(code=1012, reason="service shutdown") for channel in channels),
            return_exceptions=True,
        )
        if self._closing_tasks:
            await asyncio.gather(*self._closing_tasks, return_exceptions=True)


class TurnInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=32_768)
    input_mode: Literal["text", "speech"] = "text"


class CancelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="user", min_length=1, max_length=512)


class KillSwitchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class MemoryCorrectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=32_768)
    reason: str = Field(default="owner correction", min_length=1, max_length=512)


class SpeechInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4_000)
    rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=0.0, ge=-1.0, le=1.0)
    energy: float = Field(default=0.5, ge=0.0, le=1.0)


class SpeechPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=16_000)


class ToolApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool


_URL = re.compile(r"https?://[^\s<>]+")
_APPLICATION_ALIASES = {
    "firefox": ("firefox", "火狐"),
    "files": ("檔案", "文件", "files", "nautilus"),
    "terminal": ("終端機", "終端", "terminal", "ptyxis"),
    "settings": ("設定", "settings"),
    "calculator": ("計算機", "calculator"),
    "text-editor": ("文字編輯器", "記事本", "text editor"),
    "chrome": ("chrome", "google瀏覽器", "google chrome"),
    "vscode": ("vscode", "visual studio code", "code編輯器"),
}


def _browser_request(text: str) -> str | None:
    match = _URL.search(text)
    intents = ("開啟", "打開", "前往", "瀏覽", "read", "open")
    if match is None or not any(word in text.lower() for word in intents):
        return None
    return match.group(0).rstrip("。！？,.!?)）")  # noqa: RUF001


def _application_request(text: str) -> str | None:
    normalized = "".join(text.lower().split())
    intents = ("開啟", "打開", "啟動", "open", "launch", "start")
    if not any(word in normalized for word in intents):
        return None
    for application, aliases in _APPLICATION_ALIASES.items():
        if any("".join(alias.split()) in normalized for alias in aliases):
            return application
    return None


def _proposal_json(proposal: ToolProposal) -> dict[str, object]:
    return {
        "proposal_id": proposal.proposal_id,
        "session_id": proposal.session_id,
        "call_id": proposal.call_id,
        "capability": proposal.capability,
        "arguments": proposal.arguments,
        "risk": proposal.risk,
        "status": proposal.state.value,
    }


def _memory_json(memory: Memory) -> dict[str, object]:
    return {
        "memory_id": str(memory.memory_id),
        "identity_id": memory.identity_id,
        "person_id": memory.person_id,
        "kind": memory.kind,
        "text": memory.text,
        "confidence": memory.confidence,
        "status": memory.status,
        "revision": memory.revision,
        "valid_from": memory.created_at.isoformat(),
        "valid_to": memory.valid_to.isoformat() if memory.valid_to else None,
        "source_event_ids": [str(value) for value in memory.source_event_ids],
    }


TurnHandler = Callable[[str, str, str], Awaitable[None]]
CancelHandler = Callable[[str, str], Awaitable[None]]
MemoryCorrectionHandler = Callable[[UserTextEvent, Memory], Awaitable[None]]
ToolResultHandler = Callable[[ToolProposal], Awaitable[None]]
BrowserToolHandler = Callable[[str], Awaitable[dict[str, str]]]
ApplicationToolHandler = Callable[[str], Awaitable[dict[str, str]]]


async def _ignore_turn(_session_id: str, _text: str, _input_mode: str) -> None:
    return None


async def _ignore_cancel(_turn_id: str, _reason: str) -> None:
    return None


async def _ignore_memory_correction(_source: UserTextEvent, _memory: Memory) -> None:
    return None


async def _ignore_tool_result(_proposal: ToolProposal) -> None:
    return None


def create_app(
    *,
    allowed_origins: set[str] | None = None,
    state: GatewayState | None = None,
    hub: GatewayHub | None = None,
    tokens: SessionTokens | None = None,
    body_transport: WebSocketBodyTransport | None = None,
    memory_service: MemoryService | None = None,
    playback_ownership: PlaybackOwnership | None = None,
    speech_to_text: SpeechToText | None = None,
    text_to_speech: SpeechSynthesizer | None = None,
    live2d_dist: Path | None = None,
    on_turn: TurnHandler = _ignore_turn,
    on_cancel: CancelHandler = _ignore_cancel,
    on_memory_correction: MemoryCorrectionHandler = _ignore_memory_correction,
    on_tool_result: ToolResultHandler = _ignore_tool_result,
    on_browser_tool: BrowserToolHandler | None = None,
    on_application_tool: ApplicationToolHandler | None = None,
    tool_orchestrator: ToolOrchestrator | None = None,
    legacy_shortcuts: bool = False,
    runtime_profile: str = "legacy",
    configuration_source: str = "injected",
    on_startup: Callable[[], Awaitable[None]] | None = None,
    on_shutdown: Callable[[], Awaitable[None]] | None = None,
    on_recovery: Callable[[str], Awaitable[dict[str, object] | None]] | None = None,
    feature_status: Callable[[], dict[str, object]] | None = None,
    memory_organizer: MemoryOrganizer | None = None,
    workspace_service: WorkspaceRuntime | None = None,
    on_memory_invalidated: Callable[[], Awaitable[None]] | None = None,
) -> FastAPI:
    allowed = allowed_origins or {"http://127.0.0.1:8000", "http://localhost:8000"}
    gateway_state = state or GatewayState()
    gateway_hub = hub or GatewayHub()
    session_tokens = tokens or SessionTokens()
    renderer_transport = body_transport or WebSocketBodyTransport()
    audio_owners = playback_ownership or PlaybackOwnership()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            if on_startup is not None:
                await on_startup()
            yield
        finally:
            gateway_state.health["core"] = "draining"
            for turn in gateway_state.active_turns.values():
                turn["state"] = "interrupted_shutdown"
                with contextlib.suppress(Exception):
                    await on_cancel(turn["turn_id"], "service shutdown")
            try:
                if on_shutdown is not None:
                    await on_shutdown()
            finally:
                try:
                    if isinstance(text_to_speech, QwenReferenceTTS):
                        await text_to_speech.close()
                finally:
                    await gateway_hub.shutdown()

    app = FastAPI(title="SIRO Presentation Gateway", lifespan=lifespan)
    app.state.gateway_hub = gateway_hub
    app.state.body_transport = renderer_transport

    def require_origin(origin: str | None) -> None:
        if origin not in allowed:
            raise HTTPException(status_code=403, detail="origin is not allowed")

    def require_token(authorization: str | None) -> None:
        prefix = "Bearer "
        if authorization is None or not authorization.startswith(prefix):
            raise HTTPException(status_code=401, detail="session token is required")
        if not session_tokens.valid(authorization.removeprefix(prefix)):
            raise HTTPException(status_code=401, detail="session token is invalid or expired")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        path = Path(__file__).with_name("static") / "index.html"
        html = path.read_text(encoding="utf-8")
        if live2d_dist is not None:
            renderer_path = "/live2d/"
            renderer_status = "Live2D 載入中…"
        else:
            renderer_path = "/body"
            renderer_status = "目前是替身 renderer。尚未載入 Cubism 模型。"
        return HTMLResponse(
            html.replace("__SIRO_RENDERER_PATH__", renderer_path).replace(
                "__SIRO_RENDERER_STATUS__", renderer_status
            )
        )

    @app.get("/body", response_class=HTMLResponse)
    async def body_page() -> HTMLResponse:
        path = Path(__file__).with_name("static") / "body.html"
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/audio-field-test", response_class=HTMLResponse)
    async def audio_field_test() -> HTMLResponse:
        path = Path(__file__).with_name("static") / "audio-field-test.html"
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"state": "alive"}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        return {"state": gateway_state.health.get("core", "unavailable")}

    @app.post("/v1/session")
    async def issue_session(request: Request) -> dict[str, object]:
        require_origin(request.headers.get("origin"))
        if request.client is None or request.client.host not in {"127.0.0.1", "testclient"}:
            raise HTTPException(status_code=403, detail="session bootstrap is loopback only")
        try:
            token, ttl = session_tokens.issue()
        except SessionTokens.CapacityExceeded as error:
            raise HTTPException(status_code=429, detail="too many active sessions") from error
        return {"token": token, "expires_in_seconds": ttl}

    @app.post("/v1/audio/transcriptions")
    async def transcribe_audio(
        request: Request,
        language: str | None = Query(default="zh"),
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_origin(request.headers.get("origin"))
        require_token(authorization)
        if not gateway_state.kill_switches.get("microphone", False):
            raise HTTPException(status_code=403, detail="microphone is disabled")
        if speech_to_text is None:
            raise HTTPException(status_code=503, detail="speech recognition is unavailable")
        audio = await request.body()
        if not audio or len(audio) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="audio must be between 1 byte and 10 MiB")
        try:
            transcript = await speech_to_text.transcribe(audio, language=language)
        except Exception as error:
            logging.getLogger(__name__).warning(
                "speech recognition failed: %s", type(error).__name__
            )
            raise HTTPException(status_code=502, detail="speech recognition failed") from error
        return {
            "text": transcript.text,
            "language": transcript.language,
            "final": transcript.final,
        }

    @app.post("/v1/audio/speech/plan")
    async def prepare_speech_plan(
        body: SpeechPlanInput,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_origin(request.headers.get("origin"))
        require_token(authorization)
        try:
            return plan_speech(body.text)
        except OverflowError as error:
            raise HTTPException(status_code=413, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    async def render_owned_speech(body: SpeechInput, request: Request) -> bytes:
        assert text_to_speech is not None
        render = asyncio.create_task(
            text_to_speech.render(body.text, rate=body.rate, pitch=body.pitch, energy=body.energy)
        )

        async def disconnected() -> None:
            while not await request.is_disconnected():
                await asyncio.sleep(0.05)

        disconnect = asyncio.create_task(disconnected())
        try:
            done, _ = await asyncio.wait({render, disconnect}, return_when=asyncio.FIRST_COMPLETED)
            if disconnect in done:
                raise asyncio.CancelledError("speech client disconnected")
            return await render
        finally:
            render.cancel()
            disconnect.cancel()
            await asyncio.gather(render, disconnect, return_exceptions=True)

    @app.post("/v1/audio/speech")
    async def synthesize_speech(
        body: SpeechInput,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> Response:
        require_origin(request.headers.get("origin"))
        require_token(authorization)
        if gateway_state.routes.get("tts", "").startswith(
            "edge:"
        ) and not gateway_state.kill_switches.get("cloud", False):
            raise HTTPException(status_code=403, detail="cloud speech is disabled")
        if text_to_speech is None:
            raise HTTPException(status_code=503, detail="speech synthesis is unavailable")
        try:
            if isinstance(text_to_speech, QwenReferenceTTS) and text_to_speech.lifecycle_enabled:
                audio = await render_owned_speech(body, request)
            else:
                audio = await text_to_speech.render(
                    body.text, rate=body.rate, pitch=body.pitch, energy=body.energy
                )
        except Exception as error:
            logging.getLogger(__name__).warning("speech synthesis failed: %s", type(error).__name__)
            raise HTTPException(status_code=502, detail="speech synthesis failed") from error
        media_type = "audio/wav" if audio.startswith(b"RIFF") else "audio/mpeg"
        return Response(audio, media_type=media_type)

    @app.get("/v1/runtime")
    async def runtime_configuration(
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_token(authorization)
        return {
            "features": feature_status() if feature_status is not None else {},
            "runtime_profile": runtime_profile,
            "configuration_source": configuration_source,
            "catalog_enabled": tool_orchestrator is not None
            and tool_orchestrator.catalog is not None,
            "json_settings_applied": False,
            "authorization_mode": gateway_state.authorization_mode,
            "kill_switches": {
                k: gateway_state.kill_switches[k] for k in ("cloud", "tools", "microphone")
            },
            "routes": {
                k: gateway_state.routes[k]
                for k in ("model", "audio", "body", "tts")
                if k in gateway_state.routes
            },
            "tools": tool_orchestrator.tool_status() if tool_orchestrator is not None else [],
        }

    @app.post("/v1/workspace/{action}")
    async def workspace_readback(
        action: Literal["read", "list"],
        path: str = Query(default=".", min_length=1, max_length=4096),
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_token(authorization)
        if not gateway_state.kill_switches["tools"]:
            raise HTTPException(status_code=403, detail="tools are disabled")
        if workspace_service is None or not workspace_service.available:
            raise HTTPException(status_code=503, detail="workspace is unavailable")
        # This is an explicit authenticated owner read, not model-supplied approval.
        context = ExecutionContext(str(uuid4()), "owner-workspace", str(uuid4()), authorized=True)
        if memory_organizer is not None:
            await memory_organizer.foreground()
        try:
            result = await workspace_service.execute(
                "filesystem." + action, {"path": path}, context
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=400, detail="workspace path cannot be read") from error
        except Exception as error:
            raise HTTPException(status_code=502, detail="workspace read failed") from error
        return {"path": path, "result": result, "backend": "rust.scoped"}

    @app.get("/v1/memory-organization")
    async def organization_status(
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_token(authorization)
        if memory_organizer is None:
            return {"enabled": False, "state": "unavailable", "groups": []}
        return await memory_organizer.snapshot()

    @app.post("/v1/memory-organization")
    async def organization_control(
        enabled: bool = Query(),
        refresh: bool = Query(default=False),
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_token(authorization)
        if memory_organizer is None:
            raise HTTPException(status_code=503, detail="memory organization unavailable")
        await memory_organizer.configure(enabled)
        if refresh and enabled:
            memory_organizer.request()
        return await memory_organizer.snapshot()

    @app.get("/v1/snapshot")
    async def snapshot(authorization: str | None = Header(default=None)) -> dict[str, object]:
        require_token(authorization)
        return gateway_state.snapshot()

    @app.post("/v1/conversations/{session_id}/turns")
    async def create_turn(
        session_id: str,
        body: TurnInput,
        authorization: str | None = Header(default=None),
    ) -> dict[str, str]:
        require_token(authorization)
        if (
            gateway_state.routes.get("model", "").startswith("cloud:")
            and not gateway_state.kill_switches["cloud"]
        ):
            raise HTTPException(status_code=403, detail="cloud conversation is disabled")
        turn_id = str(uuid4())
        gateway_state.active_turns[session_id] = {"turn_id": turn_id, "state": "responding"}
        await gateway_hub.broadcast(
            {"type": "turn_started", "session_id": session_id, "turn_id": turn_id}
        )
        browser_url = _browser_request(body.text) if legacy_shortcuts else None
        application = _application_request(body.text) if legacy_shortcuts else None
        if browser_url is not None or application is not None:
            if tool_orchestrator is None:
                raise HTTPException(status_code=503, detail="tool orchestrator is unavailable")
            parsed = urlsplit(browser_url) if browser_url else None
            capability = "browser.navigate+read" if browser_url else "process.start"
            target = browser_url or application or ""
            proposal = await tool_orchestrator.propose(
                session_id,
                ToolCall(
                    f"gateway:{turn_id}",
                    capability,
                    {"url": target} if browser_url else {"application": target},
                ),
                risk="observe/read-only" if browser_url else "normal/process-start",
            )
            scope = (
                f"{parsed.scheme}://{parsed.netloc}"
                if parsed is not None
                else f"allowlisted application: {application}"
            )
            await gateway_hub.broadcast(
                {
                    "type": "tool_proposal",
                    **_proposal_json(proposal),
                    "target": target,
                    "scope": scope,
                },
                urgent=True,
            )
            gateway_state.active_turns[session_id]["state"] = "awaiting_approval"
            return {"turn_id": turn_id}
        if memory_organizer is not None:
            await memory_organizer.foreground()
        await on_turn(session_id, body.text, body.input_mode)
        gateway_state.active_turns[session_id]["state"] = "completed"
        return {"turn_id": turn_id}

    @app.get("/v1/agent-runs/{session_id}")
    async def agent_run_readback(
        session_id: str, authorization: str | None = Header(default=None)
    ) -> dict[str, object]:
        require_token(authorization)
        result = await on_recovery(session_id) if on_recovery is not None else None
        if result is None:
            raise HTTPException(status_code=404, detail="agent run was not found")
        return result

    @app.post("/v1/tool-proposals/{proposal_id}/approve")
    async def approve_tool_proposal(
        proposal_id: str,
        body: ToolApprovalInput,
        authorization: str | None = Header(default=None),
    ) -> dict[str, str]:
        require_token(authorization)
        if tool_orchestrator is None:
            raise HTTPException(status_code=503, detail="tool orchestrator is unavailable")
        proposal = await tool_orchestrator.get(proposal_id)
        if proposal is None or proposal.state is not ProposalState.PENDING:
            raise HTTPException(status_code=404, detail="pending proposal was not found")
        if not gateway_state.kill_switches["tools"]:
            raise HTTPException(status_code=403, detail="tools kill switch is disabled")
        resolved = await tool_orchestrator.resolve(
            proposal_id, approved=body.approved, arguments=proposal.arguments
        )
        if resolved.state is ProposalState.DENIED:
            await on_tool_result(resolved)
            return {"status": resolved.state.value}
        if tool_orchestrator.is_fenced(proposal_id):
            return {"status": "denied"}
        await gateway_hub.broadcast(
            {"type": "tool_started", **_proposal_json(proposal)}, urgent=True
        )
        result = await tool_orchestrator.execute(proposal_id)
        if tool_orchestrator.is_fenced(proposal_id):
            return {"status": result.state.value}
        await gateway_hub.broadcast(
            {
                "type": "tool_result",
                **_proposal_json(result),
                "result": result.observation,
                "error": result.error,
            },
            urgent=True,
        )
        await on_tool_result(result)
        if result.state is ProposalState.FAILED:
            raise HTTPException(status_code=502, detail="tool execution failed")
        return {"status": result.state.value}

    @app.post("/v1/turns/{turn_id}/cancel")
    async def cancel_turn(
        turn_id: str,
        body: CancelInput,
        authorization: str | None = Header(default=None),
    ) -> dict[str, str]:
        require_token(authorization)
        await on_cancel(turn_id, body.reason)
        await gateway_hub.broadcast(
            {"type": "turn_cancelled", "turn_id": turn_id, "reason": body.reason},
            urgent=True,
        )
        return {"state": "cancelling"}

    @app.put("/v1/kill-switches/{name}")
    async def set_kill_switch(
        name: str,
        body: KillSwitchInput,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_token(authorization)
        if name not in gateway_state.kill_switches:
            raise HTTPException(status_code=404, detail="unknown kill switch")
        gateway_state.kill_switches[name] = body.enabled
        if (
            name == "cloud"
            and not body.enabled
            and gateway_state.routes.get("model", "").startswith("cloud:")
            and on_cancel is not None
        ):
            await on_cancel("active", "cloud disabled")
        message = {"type": "kill_switch", "name": name, "enabled": body.enabled}
        await gateway_hub.broadcast(message, urgent=True)
        return message

    @app.get("/v1/memories")
    async def list_memories(
        identity_id: str = Query(default="siro", min_length=1, max_length=128),
        person_id: str = Query(default="owner", min_length=1, max_length=128),
        query: str = Query(default="", max_length=4096),
        source_event_id: UUID | None = None,
        limit: int = Query(default=100, ge=1, le=100),
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_token(authorization)
        if memory_service is None:
            raise HTTPException(status_code=503, detail="memory service is unavailable")
        items = (
            await memory_service.recall(
                identity_id,
                query,
                person_id=person_id,
                source_event_id=source_event_id,
                limit=limit,
            )
            if query.strip()
            else await memory_service.browse(identity_id, person_id=person_id, limit=limit)
        )
        return {"items": [_memory_json(item) for item in items]}

    @app.get("/v1/memories/{memory_id}/revisions")
    async def memory_revisions(
        memory_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_token(authorization)
        if memory_service is None:
            raise HTTPException(status_code=503, detail="memory service is unavailable")
        revisions = await memory_service.revisions(memory_id)
        return {
            "items": [
                {
                    "memory_id": str(item.memory_id),
                    "revision": item.revision,
                    "text": item.text,
                    "status": item.status,
                    "reason": item.reason,
                    "changed_at": item.changed_at.isoformat(),
                    "source_event_ids": [str(value) for value in item.source_event_ids],
                }
                for item in revisions
            ]
        }

    @app.post("/v1/memories/{memory_id}/correct")
    async def correct_memory(
        memory_id: UUID,
        body: MemoryCorrectionInput,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_token(authorization)
        if memory_service is None:
            raise HTTPException(status_code=503, detail="memory service is unavailable")
        now = datetime.now(UTC)
        source = UserTextEvent(
            event_id=uuid4(),
            type="conversation.user_text.v1",
            source="owner-memory-api",
            occurred_at=now,
            received_at=now,
            trace_id=str(uuid4()),
            session_id="memory-admin",
            turn_id=str(uuid4()),
            sequence=1,
            priority=Priority.INTERACTIVE,
            privacy=Privacy.LOCAL_ONLY,
            payload=UserTextPayload(text=body.text, language="zh-TW"),
        )
        try:
            corrected = await memory_service.correct(
                memory_id, body.text, source, reason=body.reason
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="memory not found") from error
        if on_memory_invalidated is not None:
            await on_memory_invalidated()
        await on_memory_correction(source, corrected)
        return _memory_json(corrected)

    @app.delete("/v1/memories/{memory_id}")
    async def delete_memory(
        memory_id: UUID,
        reason: str = Query(default="owner deletion", min_length=1, max_length=512),
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_token(authorization)
        if memory_service is None:
            raise HTTPException(status_code=503, detail="memory service is unavailable")
        if not await memory_service.delete(memory_id, reason=reason):
            raise HTTPException(status_code=404, detail="memory not found")
        if on_memory_invalidated is not None:
            await on_memory_invalidated()
        return {"memory_id": str(memory_id), "status": "deleted"}

    @app.websocket("/ws/control")
    async def control(websocket: WebSocket) -> None:
        if websocket.headers.get("origin") not in allowed:
            await websocket.close(code=1008, reason="origin is not allowed")
            return
        await websocket.accept()
        try:
            hello = await asyncio.wait_for(websocket.receive_json(), timeout=3)
            if not isinstance(hello, dict) or hello.get("type") != "authenticate":
                await websocket.close(code=1008, reason="authentication required")
                return
            token = hello.get("token")
            if not isinstance(token, str) or not session_tokens.valid(token):
                await websocket.close(code=1008, reason="invalid session token")
                return
            channel = await gateway_hub.connect(websocket, gateway_state.snapshot())
            try:
                while True:
                    message = await websocket.receive_json()
                    if isinstance(message, dict) and message.get("type") == "ping":
                        channel.enqueue({"type": "pong"}, urgent=True)
            except WebSocketDisconnect:
                pass
            finally:
                await gateway_hub.disconnect(channel)
        except TimeoutError:
            await websocket.close(code=1008, reason="authentication timeout")

    @app.websocket("/ws/body")
    async def body(websocket: WebSocket) -> None:
        if websocket.headers.get("origin") not in allowed:
            await websocket.close(code=1008, reason="origin is not allowed")
            return
        await websocket.accept()
        try:
            hello = await asyncio.wait_for(websocket.receive_json(), timeout=3)
            token = hello.get("token") if isinstance(hello, dict) else None
            if (
                not isinstance(hello, dict)
                or hello.get("type") != "authenticate"
                or not isinstance(token, str)
                or not session_tokens.valid(token)
            ):
                await websocket.close(code=1008, reason="invalid renderer authentication")
                return
            await renderer_transport.attach(websocket)
            try:
                while True:
                    await websocket.receive_json()
            except WebSocketDisconnect:
                pass
            finally:
                await renderer_transport.detach(socket=websocket)
        except TimeoutError:
            await websocket.close(code=1008, reason="authentication timeout")

    async def audio_hello(websocket: WebSocket) -> tuple[str, AudioMetadata] | None:
        hello = await asyncio.wait_for(websocket.receive_json(), timeout=3)
        token = hello.get("token") if isinstance(hello, dict) else None
        metadata = hello.get("metadata") if isinstance(hello, dict) else None
        owner_id = hello.get("owner_id") if isinstance(hello, dict) else None
        if (
            not isinstance(token, str)
            or not session_tokens.valid(token)
            or not isinstance(metadata, dict)
            or not isinstance(owner_id, str)
        ):
            await websocket.close(code=1008, reason="invalid audio authentication")
            return None
        try:
            names = ("stream_id", "session_id", "turn_id", "generation_id", "speech_id")
            identifiers = [metadata.get(name) for name in names]
            sample_rate = metadata.get("sample_rate")
            if not all(isinstance(value, str) for value in identifiers) or not isinstance(
                sample_rate, int
            ):
                raise ValueError("invalid metadata types")
            parsed = AudioMetadata(
                str(identifiers[0]),
                str(identifiers[1]),
                str(identifiers[2]),
                str(identifiers[3]),
                str(identifiers[4]),
                sample_rate=sample_rate,
                channels=int(metadata.get("channels", 1)),
                codec=str(metadata.get("codec", "pcm_s16le")),
            )
        except (TypeError, ValueError):
            await websocket.close(code=1003, reason="invalid audio metadata")
            return None
        return owner_id, parsed

    @app.websocket("/ws/audio/input")
    async def audio_input(websocket: WebSocket) -> None:
        if websocket.headers.get("origin") not in allowed:
            await websocket.close(code=1008, reason="origin is not allowed")
            return
        await websocket.accept()
        try:
            opened = await audio_hello(websocket)
            if opened is None:
                return
            _, metadata = opened
            buffer = AudioRingBuffer(metadata)
            await websocket.send_json({"type": "audio_ready", "sample_rate": metadata.sample_rate})
            while True:
                encoded = await websocket.receive_bytes()
                frame = AudioFrame.decode(encoded)
                result = buffer.push(frame)
                await websocket.send_json(
                    {"type": "audio_frame_status", "sequence": frame.sequence, "result": result}
                )
                if result == "overflow":
                    await websocket.close(code=1009, reason="audio input buffer overflow")
                    return
        except (TimeoutError, WebSocketDisconnect):
            return
        except ValueError:
            await websocket.close(code=1003, reason="invalid audio frame")

    @app.websocket("/ws/audio/output")
    async def audio_output(websocket: WebSocket) -> None:
        if websocket.headers.get("origin") not in allowed:
            await websocket.close(code=1008, reason="origin is not allowed")
            return
        await websocket.accept()
        opened: tuple[str, AudioMetadata] | None = None
        try:
            opened = await audio_hello(websocket)
            if opened is None:
                return
            owner_id, metadata = opened
            if not audio_owners.acquire(metadata.session_id, owner_id):
                await websocket.close(code=1008, reason="playback owner already exists")
                return
            await websocket.send_json({"type": "playback_owner", "owner_id": owner_id})
            while True:
                await websocket.receive_text()
        except (TimeoutError, WebSocketDisconnect):
            return
        finally:
            if opened is not None:
                audio_owners.release(opened[1].session_id, opened[0])

    if live2d_dist is not None:
        app.mount("/live2d", StaticFiles(directory=live2d_dist, html=True), name="live2d")

    return app


def main() -> None:
    import uvicorn

    from siro.adapters.body.web import MinimalWebBodyAdapter
    from siro.adapters.browser import ScopedBrowserDriver
    from siro.adapters.models.mock import OfflineDemoModel
    from siro.adapters.models.ollama import OllamaAdapter
    from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
    from siro.core.memory import MemoryService
    from siro.persistence.memory import SQLiteMemoryRepository
    from siro.persistence.sqlite import SQLiteStore
    from siro.ports.models import LanguageModel
    from siro.ports.models import Privacy as ModelPrivacy
    from siro.services.audio.stt import GroqWhisper
    from siro.services.presentation.integrated import IntegratedCompanion
    from siro.services.tools.orchestrator import SQLiteToolProposalRepository

    runtime_profile = os.environ.get("SIRO_RUNTIME_PROFILE", "legacy")
    configured = os.environ.get("SIRO_LIVE2D_DIST")
    live2d_dist = Path(configured).resolve() if configured else None
    hub = GatewayHub()
    body_transport = WebSocketBodyTransport()
    backend = "offline"
    privacy = ModelPrivacy.LOCAL_ONLY
    ollama_model = os.environ.get("SIRO_OLLAMA_MODEL")
    cloud_key = os.environ.get("SIRO_OPENAI_API_KEY")
    cloud_model = os.environ.get("SIRO_OPENAI_MODEL")
    model: LanguageModel
    if ollama_model:
        model = OllamaAdapter(model=ollama_model)
        backend = f"ollama:{ollama_model}"
    elif cloud_key and cloud_model:
        model = OpenAICompatibleAdapter(
            base_url=os.environ.get("SIRO_OPENAI_BASE_URL", "https://api.groq.com/openai"),
            api_key=cloud_key,
            model=cloud_model,
        )
        backend = f"cloud:{cloud_model}"
        privacy = ModelPrivacy.CLOUD_ALLOWED
    else:
        model = OfflineDemoModel()
    summary_enabled = (
        runtime_profile == "candidate"
        and os.environ.get("SIRO_CONTEXT_SUMMARY_ENABLED", "1") == "1"
    )
    selected_provider = model
    if runtime_profile == "candidate":
        from siro.adapters.models.failover import FailoverModel

        retry_enabled = os.environ.get("SIRO_MODEL_RETRY_ENABLED", "1")
        if retry_enabled not in {"0", "1"}:
            raise ValueError("SIRO_MODEL_RETRY_ENABLED must be 0 or 1")
        if retry_enabled == "1":
            model = FailoverModel(
                (model,),
                cloud_indices=frozenset({0})
                if privacy is ModelPrivacy.CLOUD_ALLOWED
                else frozenset(),
                cloud_request_budget=0,
            )
        from siro.services.agent.context import (
            ContextBudgetModel,
            ContextBudgetUnavailable,
            TokenBudget,
            UnavailableTokenBudget,
        )

        context_max_bytes = int(os.environ.get("SIRO_CONTEXT_MAX_BYTES", "65536"))
        if context_max_bytes < 0:
            raise ValueError("SIRO_CONTEXT_MAX_BYTES must be nonnegative")
        native_enabled = os.environ.get("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "1")
        if native_enabled not in {"0", "1"}:
            raise ValueError("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED must be 0 or 1")
        token_budget: TokenBudget | None = None
        if native_enabled == "1" and backend != "offline":
            token_budget = UnavailableTokenBudget()
            if (
                backend == "cloud:openai/gpt-oss-20b"
                and urlsplit(
                    os.environ.get("SIRO_OPENAI_BASE_URL", "https://api.groq.com/openai")
                ).hostname
                == "api.groq.com"
                and isinstance(selected_provider, OpenAICompatibleAdapter)
            ):
                from siro.services.agent.native_context import GPTOSSBudget

                tokenizer_directory = Path(
                    os.environ.get(
                        "SIRO_CONTEXT_TOKENIZER_DIR",
                        str(Path(__file__).parents[4] / ".siro-data/tokenizers/gpt-oss-20b"),
                    )
                )
                try:
                    token_budget = GPTOSSBudget(
                        tokenizer_directory,
                        selected_provider.request_payload,
                        context_window=int(os.environ.get("SIRO_CONTEXT_WINDOW_TOKENS", "131072")),
                    )
                except (FileNotFoundError, ContextBudgetUnavailable):
                    # Explicit failure on request, never substitute a byte/token guess.
                    token_budget = UnavailableTokenBudget()
        if context_max_bytes or token_budget is not None:
            model = ContextBudgetModel(
                model,
                max_bytes=context_max_bytes or None,
                token_budget=token_budget,
                summary_enabled=summary_enabled,
            )
    data_dir = Path(os.environ.get("SIRO_DATA_DIR", ".siro-data"))
    state = GatewayState()
    state.routes["model"] = backend
    state.kill_switches["cloud"] = privacy is ModelPrivacy.CLOUD_ALLOWED
    state.routes["body"] = "websocket"
    speech_to_text = GroqWhisper(cloud_key) if cloud_key else None
    kokoro_dir = data_dir / "models" / "kokoro"
    kokoro_model = kokoro_dir / "kokoro-v1.0-q4.onnx"
    kokoro_voices = kokoro_dir / "voices-v1.0.bin"
    text_to_speech: SpeechSynthesizer
    project_root = Path(__file__).parents[4]
    qwen_python = data_dir / "qwen-tts-venv" / "bin" / "python"
    qwen_model = data_dir / "models" / "qwen3-tts-0.6b-base"
    qwen_reference = data_dir / "qwen3-siro-anime-daughter-v1.wav"
    qwen_worker = project_root / "scripts" / "qwen_tts_worker.py"
    if all(path.exists() for path in (qwen_python, qwen_model, qwen_reference, qwen_worker)):
        text_to_speech = QwenReferenceTTS(
            qwen_python,
            qwen_worker,
            qwen_model,
            qwen_reference,
            "爸爸，你回來啦？我等你好久了。今天有沒有發生什麼有趣的事？",  # noqa: RUF001
            data_dir / "tts-cache" / "qwen3-siro-anime-daughter-v1",
            lifecycle=runtime_profile == "candidate",
        )
        state.routes["tts"] = "local:qwen3-tts-0.6b-base:anime-daughter-v1"
    elif kokoro_model.is_file() and kokoro_voices.is_file():
        text_to_speech = KokoroLocalTTS(str(kokoro_model), str(kokoro_voices))
        state.routes["tts"] = "local:kokoro-82m-zf-xiaobei"
    else:
        text_to_speech = EdgeNeuralTTS()
        state.routes["tts"] = "edge:zh-TW-HsiaoChenNeural"
    state.routes["audio"] = "groq:whisper-large-v3-turbo" if speech_to_text else "disabled"
    shared_store = SQLiteStore(data_dir / "siro.db")
    asyncio.run(shared_store.initialize())
    memory_service = MemoryService(SQLiteMemoryRepository(shared_store))

    from siro.services.tools.browser_session import BrowserSessions
    from siro.services.tools.orchestrator import BROWSER_SESSION_TOOLS

    browser_sessions = None
    if runtime_profile == "candidate":
        browser_setting = os.environ.get("SIRO_BROWSER_SESSION_ENABLED", "1")
        if browser_setting not in {"0", "1"}:
            raise ValueError("SIRO_BROWSER_SESSION_ENABLED must be 0 or 1")
        if browser_setting == "1":
            browser_sessions = BrowserSessions(ScopedBrowserDriver)

    async def browser_tool(url: str) -> dict[str, str]:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        async with ScopedBrowserDriver((origin,)) as browser:
            observation = await browser.navigate(url)
        return {
            "url": observation.url,
            "title": observation.title,
            "text": observation.text[:4000],
            "screen_version": observation.screen_version,
        }

    async def application_tool(application: str) -> dict[str, str]:
        async def spawn_owned(*argv: str, **options: Any) -> asyncio.subprocess.Process:
            if runtime_profile != "candidate":
                return await asyncio.create_subprocess_exec(*argv, **options)
            from siro.services.tools.execution import _protected_cleanup

            options["start_new_session"] = True
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(*argv, **options))
            try:
                return await asyncio.shield(spawn)
            except asyncio.CancelledError:
                process = await asyncio.shield(spawn)
                await _protected_cleanup(process, [])
                raise

        async def stop_unacknowledged(process: asyncio.subprocess.Process) -> None:
            if runtime_profile == "candidate":
                from siro.services.tools.execution import _protected_cleanup

                await _protected_cleanup(process, [])

        desktop_apps = {
            "files": ("檔案", "org.gnome.Nautilus"),
            "terminal": ("終端機", "org.gnome.Ptyxis"),
            "settings": ("設定", "org.gnome.Settings"),
            "calculator": ("計算機", "org.gnome.Calculator"),
            "text-editor": ("文字編輯器", "org.gnome.TextEditor"),
            "chrome": ("Google Chrome", "google-chrome"),
            "vscode": ("Visual Studio Code", "code"),
        }
        if application == "firefox":
            executable = "/usr/bin/firefox"
            if not Path(executable).is_file():
                raise FileNotFoundError(executable)
            process = await spawn_owned(
                executable,
                "--new-window",
                "about:blank",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            acknowledged = False
            try:
                await asyncio.sleep(2)
                if process.returncode not in {None, 0}:
                    raise RuntimeError(f"Firefox launcher exited with {process.returncode}")
                probe = await spawn_owned(
                    "pgrep",
                    "-x",
                    "firefox",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                try:
                    stdout, _ = await probe.communicate()
                finally:
                    if probe.returncode is None:
                        await stop_unacknowledged(probe)
                pids = stdout.decode().split()
                if not pids:
                    raise RuntimeError("Firefox process readback failed")
                acknowledged = True
                return {"application": "Firefox", "state": "running", "pid": pids[0]}
            finally:
                if not acknowledged:
                    await stop_unacknowledged(process)
        spec = desktop_apps.get(application)
        if spec is None:
            raise ValueError("application is not allowlisted")
        display_name, desktop_id = spec
        process = await spawn_owned(
            "/usr/bin/gtk-launch",
            desktop_id,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        acknowledged = False
        try:
            returncode = await asyncio.wait_for(process.wait(), timeout=15)
            if returncode != 0:
                raise RuntimeError(f"desktop launcher exited with {returncode}")
            acknowledged = True
            return {"application": display_name, "state": "launch-confirmed"}
        finally:
            if not acknowledged:
                await stop_unacknowledged(process)

    async def execute_browser(arguments: dict[str, object]) -> object:
        url = arguments.get("url")
        if not isinstance(url, str):
            raise ValueError("browser.navigate+read requires a URL")
        return await browser_tool(url)

    async def execute_application(arguments: dict[str, object]) -> object:
        application = arguments.get("application")
        if not isinstance(application, str):
            raise ValueError("process.start requires an application")
        return await application_tool(application)

    # Controller, executor and TTS share the frozen startup profile.

    async def execute_computer(
        arguments: dict[str, object], context: ExecutionContext | None = None
    ) -> object:
        raw_argv = arguments.get("argv")
        if (
            not isinstance(raw_argv, list)
            or not raw_argv
            or len(raw_argv) > 64
            or not all(isinstance(item, str) and item for item in raw_argv)
        ):
            raise ValueError("computer.execute requires 1-64 non-empty argv strings")
        argv = tuple(raw_argv)
        if argv[0] in {"sudo", "doas", "pkexec"}:
            raise PermissionError("privileged execution profile is not enabled")
        if len(argv) >= 2 and argv[0] in {"sh", "bash", "dash", "zsh"} and argv[1] == "-c":
            raise PermissionError("shell command strings are not accepted; use direct argv")
        raw_cwd = arguments.get("cwd", str(Path.home()))
        if not isinstance(raw_cwd, str):
            raise ValueError("computer.execute cwd must be a path string")
        cwd = Path(raw_cwd).expanduser().resolve(strict=True)
        timeout = arguments.get("timeout_seconds", 30)
        if not isinstance(timeout, int) or not 1 <= timeout <= 120:
            raise ValueError("computer.execute timeout must be between 1 and 120 seconds")
        detach = arguments.get("detach", False)
        if not isinstance(detach, bool):
            raise ValueError("computer.execute detach must be boolean")
        child_env = os.environ.copy()
        for secret_name in ("SIRO_OPENAI_API_KEY", "GROQ_API_KEY"):
            child_env.pop(secret_name, None)
        if runtime_profile == "candidate":
            from siro.services.tools.execution import execute_bounded_argv

            if context is not None:
                deadline = asyncio.get_running_loop().time() + timeout
                context = replace(
                    context,
                    deadline=deadline
                    if context.deadline is None
                    else min(deadline, context.deadline),
                )
            return await execute_bounded_argv(
                argv,
                cwd=cwd,
                environment=child_env,
                timeout=timeout,
                detach=detach,
                context=context,
            )
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=child_env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL if detach else asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL if detach else asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        if detach:
            await asyncio.sleep(0.25)
            return {"argv": list(argv), "pid": process.pid, "state": "started"}
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise TimeoutError("computer.execute exceeded its timeout") from None
        output_limit = 64 * 1024
        return {
            "argv": list(argv),
            "cwd": str(cwd),
            "returncode": process.returncode,
            "stdout": stdout[:output_limit].decode(errors="replace"),
            "stderr": stderr[:output_limit].decode(errors="replace"),
            "truncated": len(stdout) > output_limit or len(stderr) > output_limit,
        }

    from siro.services.tools.workspace import WORKSPACE_TOOLS

    workspace = (
        WorkspaceRuntime(
            Path(os.environ.get("SIRO_WORKSPACE_DIR", str(data_dir / "workspace"))),
            Path(
                os.environ.get(
                    "SIRO_RUNTIME_BINARY", str(project_root / "target/debug/siro-runtime")
                )
            ),
        )
        if runtime_profile == "candidate" and os.environ.get("SIRO_WORKSPACE_ENABLED", "1") == "1"
        else None
    )

    handlers: dict[str, ToolExecutor] = {
        "browser.navigate+read": execute_browser,
        "process.start": execute_application,
        "computer.execute": execute_computer,
    }

    async def browser_without_context(arguments: dict[str, object]) -> object:
        raise PermissionError("browser requires session context")

    async def session_browser(
        action: str, arguments: dict[str, object], context: ExecutionContext
    ) -> object:
        if browser_sessions is None:
            raise RuntimeError("browser sessions disabled")
        return await browser_sessions.execute(action, arguments, context)

    browser_contextual = {}
    if browser_sessions is not None:
        for action in ("navigate+read", "read", "fill", "click", "close"):
            name = "browser." + action
            handlers[name] = browser_without_context
            browser_contextual[name] = partial(session_browser, action)

    workspace_contextual = {}
    if workspace is not None:
        for definition in WORKSPACE_TOOLS:
            handlers[definition.name] = browser_without_context
            workspace_contextual[definition.name] = partial(workspace.execute, definition.name)

    definitions = {definition.name: definition for definition in DEFAULT_MODEL_TOOLS}
    if workspace is not None:
        definitions.update({d.name: d for d in WORKSPACE_TOOLS})
    if browser_sessions is not None:
        definitions.update({d.name: d for d in BROWSER_SESSION_TOOLS})

    def readiness(name: str) -> ToolAvailability:
        if not state.kill_switches["tools"]:
            return ToolAvailability(
                AvailabilityState.UNAVAILABLE, AvailabilityReason.TOOLS_DISABLED
            )
        if name.startswith("filesystem."):
            ready = workspace is not None and workspace.available
            return ToolAvailability(
                AvailabilityState.AVAILABLE if ready else AvailabilityState.UNAVAILABLE,
                AvailabilityReason.READY if ready else AvailabilityReason.WORKSPACE_UNAVAILABLE,
            )
        if name.startswith("browser."):
            ready = bool(shutil.which("google-chrome") or shutil.which("chromium"))
            return ToolAvailability(
                AvailabilityState.AVAILABLE if ready else AvailabilityState.UNAVAILABLE,
                AvailabilityReason.READY
                if ready
                else AvailabilityReason.BROWSER_EXECUTABLE_MISSING,
            )
        # Target checks remain in existing handlers; this is not a successful action probe.
        return ToolAvailability(AvailabilityState.AVAILABLE, AvailabilityReason.READY)

    def tool_metadata(name: str) -> ToolMetadata:
        labels = {
            "computer.execute": "執行電腦任務",
            "process.start": "啟動應用程式",
            "browser.navigate+read": "開啟並閱讀網頁",
            "browser.read": "閱讀目前網頁",
            "browser.fill": "填寫網頁欄位",
            "browser.click": "操作網頁按鈕",
            "browser.close": "關閉目前網頁",
            "filesystem.read": "讀取工作目錄文字檔",
            "filesystem.list": "查看工作目錄檔案",
        }
        read_only = name in {
            "browser.navigate+read",
            "browser.read",
            "filesystem.read",
            "filesystem.list",
        }
        return ToolMetadata(
            display_name=labels.get(name),
            required_permissions=("tool_approval", "workspace_path_grant")
            if name.startswith("filesystem.")
            else ("tool_approval",),
            risk_level="observe/read-only" if read_only else "computer",
            version="siro-tool-contract-v1",
            provenance="siro_builtin",
            timeout_seconds=120
            if name == "computer.execute"
            else (30 if name.startswith("browser.") and browser_sessions is not None else None),
            failure_behavior="Failures produce failed observations. Unknown effects are not "
            "automatically repeated. Availability is not proof of successful execution.",
        )

    catalog = (
        ToolCatalog(
            tuple(
                ToolDescriptor(
                    name,
                    definitions.get(name),
                    handler,
                    available=partial(readiness, name),
                    backend="rust.scoped"
                    if name.startswith("filesystem.")
                    else ("playwright" if name.startswith("browser.") else "python.argv"),
                    effect="read"
                    if name
                    in {
                        "browser.navigate+read",
                        "browser.read",
                        "filesystem.read",
                        "filesystem.list",
                    }
                    else "computer",
                    contextual_executor=execute_computer
                    if name == "computer.execute"
                    else (browser_contextual.get(name) or workspace_contextual.get(name)),
                    metadata=tool_metadata(name),
                )
                for name, handler in handlers.items()
            )
        )
        if runtime_profile == "candidate"
        else None
    )
    tool_orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(shared_store),
        handlers,
        contextual_executors={
            "computer.execute": execute_computer,
            **browser_contextual,
            **workspace_contextual,
        }
        if runtime_profile == "candidate"
        else None,
        catalog=catalog,
    )
    session_restore_enabled = True
    if runtime_profile == "candidate":
        restore_setting = os.environ.get("SIRO_SESSION_RESTORE_ENABLED", "1")
        if restore_setting not in {"0", "1"}:
            raise ValueError("SIRO_SESSION_RESTORE_ENABLED must be 0 or 1")
        session_restore_enabled = restore_setting == "1"
    memory_ingress_enabled = True
    if runtime_profile == "candidate":
        memory_setting = os.environ.get("SIRO_MEMORY_INGRESS_ENABLED", "1")
        if memory_setting not in {"0", "1"}:
            raise ValueError("SIRO_MEMORY_INGRESS_ENABLED must be 0 or 1")
        memory_ingress_enabled = memory_setting == "1"
    controller = IntegratedCompanion(
        data_dir,
        model,
        hub,
        MinimalWebBodyAdapter(body_transport),
        privacy=privacy,
        tool_orchestrator=tool_orchestrator,
        runtime_profile=runtime_profile,
        session_restore_enabled=session_restore_enabled,
        memory_ingress_enabled=memory_ingress_enabled,
        summary_enabled=summary_enabled,
        auto_authorize=lambda: state.authorization_mode == "full" and state.kill_switches["tools"],
    )

    organizer = (
        MemoryOrganizer(
            memory_service,
            lambda: controller.foreground_active,
            enabled=os.environ.get("SIRO_MEMORY_ORGANIZATION_ENABLED", "1") == "1",
        )
        if runtime_profile == "candidate"
        else None
    )

    async def start_controller() -> None:
        await controller.startup()
        if organizer is not None:
            await organizer.start()
        if workspace is not None:
            await workspace.start()
        if browser_sessions is not None:
            await browser_sessions.start()

    async def stop_controller() -> None:
        try:
            if organizer is not None:
                await organizer.close()
        finally:
            try:
                if browser_sessions is not None:
                    await browser_sessions.close()
            finally:
                if workspace is not None:
                    await workspace.close()

    def product_features() -> dict[str, object]:
        return {
            "summary": {
                "enabled": summary_enabled,
                "mode": "extractive",
                "history_pairs": 24 if summary_enabled else 6,
                "budget_compactions": getattr(model, "summarized_requests", 0),
            },
            "memory_organization": {"enabled": organizer is not None and organizer.enabled},
            "workspace": {
                "enabled": workspace is not None,
                "available": workspace is not None and workspace.available,
                "directory": str(workspace.root) if workspace is not None else None,
                "error": workspace.error if workspace is not None else None,
            },
        }

    async def cancel_controller(turn_id: str, reason: str) -> None:
        if runtime_profile == "candidate" and turn_id != "active":
            # Keep the HTTP contract; map its existing turn ID to the owned session.
            sessions = [
                session_id
                for session_id, turn in state.active_turns.items()
                if turn["turn_id"] == turn_id
            ]
            for session_id in sessions:
                await controller.cancel(turn_id, reason, session_id=session_id)
                if browser_sessions is not None:
                    await browser_sessions.close_session(session_id)
            return
        await controller.cancel(turn_id, reason)
        if browser_sessions is not None:
            await browser_sessions.clear()

    log_directory = os.environ.get("SIRO_LOG_DIR")
    if log_directory:
        directory = Path(log_directory)
        directory.mkdir(parents=True, exist_ok=True)
        handler = TimedRotatingFileHandler(
            directory / "siro.log", when="midnight", backupCount=14, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.basicConfig(level=logging.INFO, handlers=[handler])
    port_text = os.environ.get("SIRO_GATEWAY_PORT", "8000")
    try:
        port = int(port_text)
    except ValueError as error:
        raise ValueError("SIRO_GATEWAY_PORT must be an integer") from error
    if not 1024 <= port <= 65535:
        raise ValueError("SIRO_GATEWAY_PORT must be between 1024 and 65535")
    uvicorn.run(
        create_app(
            state=state,
            hub=hub,
            runtime_profile=runtime_profile,
            configuration_source="gateway_env_and_defaults",
            allowed_origins={f"http://127.0.0.1:{port}", f"http://localhost:{port}"},
            body_transport=body_transport,
            memory_service=memory_service,
            speech_to_text=speech_to_text,
            text_to_speech=text_to_speech,
            live2d_dist=live2d_dist,
            on_startup=start_controller,
            on_shutdown=stop_controller,
            feature_status=product_features,
            on_recovery=controller.recovery_readback,
            on_turn=controller.respond,
            memory_organizer=organizer,
            workspace_service=workspace,
            on_memory_invalidated=controller.invalidate_memory_context,
            on_cancel=cancel_controller,
            on_memory_correction=controller.memory_corrected,
            on_tool_result=controller.continue_after_tool,
            on_browser_tool=browser_tool,
            on_application_tool=application_tool,
            tool_orchestrator=tool_orchestrator,
        ),
        host="127.0.0.1",
        port=port,
        log_level="info",
        log_config=None if log_directory else uvicorn.config.LOGGING_CONFIG,
    )
