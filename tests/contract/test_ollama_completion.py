from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.adapters.models.failover import FailoverModel
from siro.adapters.models.http import ProviderResponseInvalid
from siro.adapters.models.mock import MockModel
from siro.adapters.models.ollama import OllamaAdapter
from siro.adapters.models.openai_compatible import (
    ProviderOutputIncomplete,
    ProviderOutputTruncated,
)
from siro.core.conversation import MAX_CONTINUATIONS
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

PARTIAL = "synthetic unfinished local reply"
CALL: dict[str, object] = {
    "function": {"name": "computer.execute", "arguments": {"argv": ["must-not-execute"]}}
}


class AtomicTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    async def post(
        self, url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
    ) -> dict[str, object]:
        del url, headers, timeout
        self.requests.append(payload)
        return self.response


class Lines(AsyncIterator[str]):
    def __init__(self, owner: StreamTransport, cancellation: CancellationToken) -> None:
        self.owner = owner
        self.cancellation = cancellation
        self.index = 0

    async def __anext__(self) -> str:
        await asyncio.sleep(0)
        if self.index == len(self.owner.events):
            if self.owner.wire_error:
                raise ConnectionError("synthetic wire failure")
            raise StopAsyncIteration
        event = self.owner.events[self.index]
        self.index += 1
        if self.owner.cancel_at_terminal and isinstance(event, dict) and event.get("done") is True:
            self.cancellation.cancel()
        return json.dumps(event) if isinstance(event, dict) else event

    async def aclose(self) -> None:
        self.owner.closed = True
        if self.owner.cleanup_error:
            raise ConnectionError("synthetic cleanup failure")


class StreamTransport:
    def __init__(
        self,
        events: Sequence[dict[str, object] | str],
        *,
        cleanup_error: bool = False,
        wire_error: bool = False,
        cancel_at_terminal: bool = False,
    ) -> None:
        self.events = events
        self.cleanup_error = cleanup_error
        self.wire_error = wire_error
        self.cancel_at_terminal = cancel_at_terminal
        self.closed = False
        self.requests: list[dict[str, object]] = []

    def stream_lines(
        self,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout: float,
        cancellation: CancellationToken,
    ) -> Lines:
        del url, headers, timeout
        self.requests.append(payload)
        return Lines(self, cancellation)


class Fallback(MockModel):
    def __init__(self) -> None:
        super().__init__(("synthetic fallback must not run",))
        self.requests = 0

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests += 1
        async for chunk in super().stream(request, cancellation):
            yield chunk


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("reason", ["length", "unknown"])
@pytest.mark.parametrize("with_tools", [False, True])
async def test_ollama_incomplete_terminal_preserves_partial_without_tools_or_retry(
    streaming: bool, reason: str, with_tools: bool
) -> None:
    message: dict[str, object] = {"content": PARTIAL}
    if with_tools:
        message["tool_calls"] = [CALL]
    transport: AtomicTransport | StreamTransport
    if streaming:
        transport = StreamTransport(
            (
                {"message": message, "done": False},
                {"done": True, "done_reason": reason},
                {"done": True, "done_reason": "stop"},
            )
        )
    else:
        transport = AtomicTransport({"message": message, "done": True, "done_reason": reason})
    adapter = OllamaAdapter(model="synthetic", transport=transport)
    fallback = Fallback()
    chunks = []
    expected = ProviderOutputTruncated if reason == "length" else ProviderOutputIncomplete
    with pytest.raises(expected, match="provider output"):
        async for chunk in FailoverModel((adapter, fallback), backoff_seconds=0).stream(
            ModelRequest("synthetic", "g"), CancellationToken()
        ):
            chunks.append(chunk)
    assert [chunk.text for chunk in chunks if chunk.kind == "text"] == [PARTIAL]
    assert not any(chunk.kind in {"tool_request", "finished"} for chunk in chunks)
    assert len(transport.requests) == 1 and fallback.requests == 0
    if isinstance(transport, StreamTransport):
        assert transport.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("reason", [None, "stop"])
@pytest.mark.parametrize("with_tools", [False, True])
async def test_ollama_stop_and_legacy_success_preserve_pairing_and_usage(
    streaming: bool, reason: str | None, with_tools: bool
) -> None:
    message: dict[str, object] = {"content": "" if with_tools else "synthetic complete"}
    if with_tools:
        message["tool_calls"] = [CALL]
    terminal: dict[str, object] = {"prompt_eval_count": 3, "eval_count": 4}
    if reason is not None:
        terminal.update(done=True, done_reason=reason)
    transport: AtomicTransport | StreamTransport
    if streaming:
        terminal["done"] = True  # Original streaming fixtures omit reason, not done.
        transport = StreamTransport(({"message": message, "done": False}, terminal))
    else:
        transport = AtomicTransport({"message": message, **terminal})
    adapter = OllamaAdapter(model="synthetic", transport=transport)
    chunks = []
    async for chunk in adapter.stream(ModelRequest("synthetic", "g"), CancellationToken()):
        if chunk.kind == "tool_request" and isinstance(transport, StreamTransport):
            assert transport.closed  # No tool before successful owned cleanup.
        chunks.append(chunk)
    assert chunks[-1].kind == "finished"
    assert next(chunk.usage_tokens for chunk in chunks if chunk.kind == "usage") == 7
    if with_tools:
        assert next(
            chunk.tool_call for chunk in chunks if chunk.kind == "tool_request"
        ) == ToolCall("ollama-g-0", "computer.execute", {"argv": ["must-not-execute"]})
    else:
        assert [chunk.text for chunk in chunks if chunk.kind == "text"] == ["synthetic complete"]


@pytest.mark.asyncio
@pytest.mark.parametrize("with_text,with_tools", [(True, False), (False, True), (True, True)])
async def test_ollama_bare_eof_never_completes_or_releases_buffered_tools(
    with_text: bool, with_tools: bool
) -> None:
    message: dict[str, object] = {"content": PARTIAL if with_text else ""}
    if with_tools:
        message["tool_calls"] = [CALL]
    transport = StreamTransport(({"message": message, "done": False},))
    fallback = Fallback()
    chunks = []
    with pytest.raises(ProviderOutputIncomplete, match="provider output"):
        async for chunk in FailoverModel(
            (OllamaAdapter(model="synthetic", transport=transport), fallback), backoff_seconds=0
        ).stream(ModelRequest("synthetic", "g"), CancellationToken()):
            chunks.append(chunk)
    assert [chunk.kind for chunk in chunks] == (["text"] if with_text else [])
    assert transport.closed and fallback.requests == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("output", ["empty", "thinking", "usage_only"])
async def test_ollama_no_answer_or_tools_cannot_complete(streaming: bool, output: str) -> None:
    message: dict[str, object] = {} if output == "usage_only" else {"content": ""}
    if output == "thinking":
        message["thinking"] = "synthetic analysis without a usable answer"
    response = {"message": message, "done": True, "done_reason": "stop", "eval_count": 512}
    transport: AtomicTransport | StreamTransport = (
        StreamTransport((response,)) if streaming else AtomicTransport(response)
    )
    with pytest.raises(ProviderOutputIncomplete, match="provider"):
        _ = [
            chunk
            async for chunk in OllamaAdapter(model="synthetic", transport=transport).stream(
                ModelRequest("synthetic", "g"), CancellationToken()
            )
        ]


@pytest.mark.asyncio
async def test_ollama_atomic_explicit_unfinished_response_preserves_partial() -> None:
    adapter = OllamaAdapter(
        model="synthetic",
        transport=AtomicTransport({"message": {"content": PARTIAL}, "done": False}),
    )
    chunks = []
    with pytest.raises(ProviderOutputIncomplete):
        async for chunk in adapter.stream(ModelRequest("synthetic", "g"), CancellationToken()):
            chunks.append(chunk)
    assert [chunk.kind for chunk in chunks] == ["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_ollama_cancel_after_same_event_text_precedes_length_or_tools(
    streaming: bool,
) -> None:
    response = {
        "message": {"content": PARTIAL, "tool_calls": [CALL]},
        "done": True,
        "done_reason": "length",
    }
    transport: AtomicTransport | StreamTransport = (
        StreamTransport((response,)) if streaming else AtomicTransport(response)
    )
    token = CancellationToken()
    chunks = []
    async for chunk in OllamaAdapter(model="synthetic", transport=transport).stream(
        ModelRequest("synthetic", "g"), token
    ):
        chunks.append(chunk)
        token.cancel()
    assert [chunk.kind for chunk in chunks] == ["text"]
    if isinstance(transport, StreamTransport):
        assert transport.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["done", "length", "cancel", "wire"])
async def test_ollama_cleanup_error_preserves_primary_cancellation_and_tool_intent(
    ending: str,
) -> None:
    events: list[dict[str, object] | str] = [
        {"message": {"content": "", "tool_calls": [CALL]}, "done": False}
    ]
    if ending != "wire":
        events.append({"done": True, "done_reason": "length" if ending == "length" else "stop"})
    transport = StreamTransport(
        events,
        cleanup_error=True,
        wire_error=ending == "wire",
        cancel_at_terminal=ending == "cancel",
    )
    token = CancellationToken()
    fallback = Fallback()
    chunks = []
    failure: Exception | None = None
    try:
        async for chunk in FailoverModel(
            (OllamaAdapter(model="synthetic", transport=transport), fallback), backoff_seconds=0
        ).stream(ModelRequest("synthetic", "g"), token):
            chunks.append(chunk)
    except Exception as error:
        failure = error
    assert chunks == [] and fallback.requests == 0 and transport.closed
    if ending == "cancel":
        assert failure is None and token.cancelled
    elif ending == "length":
        assert isinstance(failure, ProviderOutputTruncated)
        assert "siro: provider stream cleanup failed" in getattr(failure, "__notes__", ())
    else:
        assert isinstance(failure, ConnectionError)
        assert "siro: provider tool intent emitted" in getattr(failure, "__notes__", ())


@pytest.mark.asyncio
async def test_ollama_error_envelope_after_tool_intent_stays_safe_without_release() -> None:
    transport = StreamTransport(
        (
            {"message": {"tool_calls": [CALL]}, "done": False},
            {"error": "synthetic-private-canary"},
        )
    )
    chunks = []
    with pytest.raises(ProviderResponseInvalid) as caught:
        async for chunk in OllamaAdapter(model="synthetic", transport=transport).stream(
            ModelRequest("synthetic", "g"), CancellationToken()
        ):
            chunks.append(chunk)
    assert chunks == [] and transport.closed
    assert "synthetic-private-canary" not in str(caught.value)


class RecordingHub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    async def broadcast(self, message: dict[str, object], *, urgent: bool = False) -> None:
        del urgent
        self.events.append(message)


@asynccontextmanager
async def local_provider(body: bytes) -> AsyncIterator[tuple[str, list[dict[str, object]]]]:
    requests: list[dict[str, object]] = []
    errors: list[Exception] = []
    handlers: set[asyncio.Task[None]] = set()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        handlers.add(task)
        try:
            async with asyncio.timeout(3):
                headers = await reader.readuntil(b"\r\n\r\n")
                assert headers.startswith(b"POST /api/chat HTTP/1.1\r\n")
                length = next(
                    int(line.split(b":", 1)[1])
                    for line in headers.split(b"\r\n")
                    if line.lower().startswith(b"content-length:")
                )
                payload = json.loads(await reader.readexactly(length))
                assert isinstance(payload, dict) and payload["stream"] is True
                requests.append(payload)
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/x-ndjson\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
                await writer.drain()
        except Exception as error:
            errors.append(error)
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}", requests
    finally:
        server.close()
        await server.wait_closed()
        for handler in tuple(handlers):
            handler.cancel()
        await asyncio.gather(*tuple(handlers), return_exceptions=True)
    assert not errors, errors


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["legacy", "candidate"])
@pytest.mark.parametrize("ending", ["length", "bare_eof"])
async def test_ollama_real_http_incomplete_preserves_failed_partial_without_effect_or_replay(
    tmp_path: Path, profile: Literal["legacy", "candidate"], ending: str
) -> None:
    events = [{"message": {"content": PARTIAL, "tool_calls": [CALL]}, "done": False}]
    if ending == "length":
        events.append({"done": True, "done_reason": "length"})
    body = "".join(json.dumps(event) + "\n" for event in events).encode()
    effects: list[dict[str, object]] = []

    async def execute(arguments: dict[str, object]) -> object:
        effects.append(arguments)
        return {"synthetic": "must not execute"}

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repository = SQLiteAgentRunRepository(store)
    hub = RecordingHub()
    async with local_provider(body) as (base_url, requests):
        model = FailoverModel(
            (OllamaAdapter(base_url=base_url, model="synthetic"),), backoff_seconds=0
        )

        def controller(selected_hub: RecordingHub) -> IntegratedCompanion:
            return IntegratedCompanion(
                tmp_path,
                model,
                selected_hub,
                MinimalWebBodyAdapter(WebSocketBodyTransport()),
                privacy=Privacy.LOCAL_ONLY,
                tool_orchestrator=ToolOrchestrator(
                    SQLiteToolProposalRepository(store), {"computer.execute": execute}
                ),
                runtime_profile=profile,
                auto_authorize=lambda: True,
            )

        runtime = controller(hub)
        await asyncio.wait_for(runtime.respond("session", "synthetic goal"), 10)
        expected = "ProviderOutputTruncated" if ending == "length" else "ProviderOutputIncomplete"
        # A length cut is continued up to MAX_CONTINUATIONS times (the provider keeps cutting it);
        # a bare EOF gets no continuation. Its cut tool calls are never dispatched either way.
        extra = MAX_CONTINUATIONS if ending == "length" else 0
        assert len(requests) == 1 + extra and effects == []
        terminals = [event for event in hub.events if event["type"] == "assistant_terminal"]
        assert len(terminals) == 1
        assert terminals[0]["state"] == "failed" and terminals[0]["error"] == expected
        assert [event["text"] for event in hub.events if event["type"] == "assistant_delta"] == [
            PARTIAL
        ] * (1 + extra)
        assert not any(event["type"] == "tool_proposal" for event in hub.events)
        readback = await runtime.recovery_readback("session")
        assert readback is not None and readback["state"] == "failed"
        assert readback["error"] == expected
        steps = await repository.steps(str(readback["run_id"]))
        finals = [step.payload for step in steps if step.kind == "final"]
        assert len(finals) == 1 and isinstance(finals[0], dict)
        assert finals[0]["text"] == PARTIAL * (1 + extra)
        assert (
            await store.run_transaction(
                lambda connection: connection.execute(
                    "SELECT count(*) FROM tool_proposals"
                ).fetchone()[0]
            )
            == 0
        )
        restarted_hub = RecordingHub()
        restarted = controller(restarted_hub)
        await restarted.startup()
        assert await restarted.recovery_readback("session") == readback
        assert len(requests) == 1 + extra and effects == [] and restarted_hub.events == []
        assert await repository.recent_session_messages("session", privacy="local_only") == ()
