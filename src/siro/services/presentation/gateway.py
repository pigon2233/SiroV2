"""Authenticated loopback HTTP/WebSocket presentation gateway."""

from __future__ import annotations

import asyncio
import contextlib
import os
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from siro.adapters.body.web import WebSocketBodyTransport
from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.memory import Memory, MemoryService
from siro.services.audio.protocol import (
    AudioFrame,
    AudioMetadata,
    AudioRingBuffer,
    PlaybackOwnership,
)


class JsonSocket(Protocol):
    async def send_json(self, data: object) -> None: ...

    async def close(self, code: int = 1000, reason: str | None = None) -> None: ...


class SessionTokens:
    def __init__(self, *, ttl_seconds: float = 300) -> None:
        self._ttl = ttl_seconds
        self._tokens: dict[str, float] = {}

    def issue(self) -> tuple[str, float]:
        token = secrets.token_urlsafe(32)
        expires_at = time.monotonic() + self._ttl
        self._tokens[token] = expires_at
        return token, self._ttl

    def valid(self, token: str) -> bool:
        expires_at = self._tokens.get(token)
        if expires_at is None:
            return False
        if time.monotonic() >= expires_at:
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
        default_factory=lambda: {"cloud": False, "tools": False, "microphone": False}
    )

    def snapshot(self) -> dict[str, object]:
        return {
            "type": "snapshot",
            "identity": dict(self.identity),
            "active_turns": dict(self.active_turns),
            "health": dict(self.health),
            "routes": dict(self.routes),
            "kill_switches": dict(self.kill_switches),
        }


class ClientChannel:
    def __init__(
        self,
        client_id: str,
        socket: JsonSocket,
        *,
        urgent_capacity: int,
        normal_capacity: int,
    ) -> None:
        self.client_id = client_id
        self.socket = socket
        self.urgent: asyncio.Queue[dict[str, object]] = asyncio.Queue(urgent_capacity)
        self.normal: asyncio.Queue[dict[str, object]] = asyncio.Queue(normal_capacity)
        self.writer: asyncio.Task[None] | None = None
        self.closed = False

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
                selected = done.pop()
                message = selected.result()
                urgent_burst = 1 if selected is urgent_get else 0
            await self.socket.send_json(message)


class GatewayHub:
    def __init__(self, *, urgent_capacity: int = 32, normal_capacity: int = 256) -> None:
        self._urgent_capacity = urgent_capacity
        self._normal_capacity = normal_capacity
        self._clients: dict[str, ClientChannel] = {}
        self._closing_tasks: set[asyncio.Task[None]] = set()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, socket: JsonSocket, snapshot: dict[str, object]) -> ClientChannel:
        channel = ClientChannel(
            str(uuid4()),
            socket,
            urgent_capacity=self._urgent_capacity,
            normal_capacity=self._normal_capacity,
        )
        self._clients[channel.client_id] = channel
        channel.start()
        channel.enqueue(snapshot, urgent=True)
        return channel

    async def disconnect(self, channel: ClientChannel) -> None:
        self._clients.pop(channel.client_id, None)
        await channel.stop()

    async def broadcast(self, message: dict[str, object], *, urgent: bool = False) -> None:
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


class TurnInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=32_768)


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


TurnHandler = Callable[[str, str], Awaitable[None]]
CancelHandler = Callable[[str, str], Awaitable[None]]


async def _ignore_turn(_session_id: str, _text: str) -> None:
    return None


async def _ignore_cancel(_turn_id: str, _reason: str) -> None:
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
    live2d_dist: Path | None = None,
    on_turn: TurnHandler = _ignore_turn,
    on_cancel: CancelHandler = _ignore_cancel,
) -> FastAPI:
    allowed = allowed_origins or {"http://127.0.0.1:8000", "http://localhost:8000"}
    gateway_state = state or GatewayState()
    gateway_hub = hub or GatewayHub()
    session_tokens = tokens or SessionTokens()
    renderer_transport = body_transport or WebSocketBodyTransport()
    audio_owners = playback_ownership or PlaybackOwnership()
    app = FastAPI(title="SIRO Presentation Gateway")
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
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/body", response_class=HTMLResponse)
    async def body_page() -> HTMLResponse:
        path = Path(__file__).with_name("static") / "body.html"
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
        token, ttl = session_tokens.issue()
        return {"token": token, "expires_in_seconds": ttl}

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
        turn_id = str(uuid4())
        gateway_state.active_turns[session_id] = {"turn_id": turn_id, "state": "responding"}
        await gateway_hub.broadcast(
            {"type": "turn_started", "session_id": session_id, "turn_id": turn_id}
        )
        await on_turn(session_id, body.text)
        return {"turn_id": turn_id}

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
                await renderer_transport.detach()
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

    configured = os.environ.get("SIRO_LIVE2D_DIST")
    live2d_dist = Path(configured).resolve() if configured else None
    uvicorn.run(
        create_app(live2d_dist=live2d_dist), host="127.0.0.1", port=8000, log_level="info"
    )
