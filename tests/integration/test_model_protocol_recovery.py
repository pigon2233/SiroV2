from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from siro.adapters.models.failover import FailoverModel
from siro.adapters.models.http import UrllibJsonTransport
from siro.adapters.models.ollama import OllamaAdapter
from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.core.conversation import ConversationEngine, ConversationSignal, TurnState
from siro.core.identity import IdentityService, ImmutableCore
from siro.persistence.conversation import SQLiteConversationRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy


@asynccontextmanager
async def provider_server(bodies: tuple[bytes, ...]) -> AsyncIterator[tuple[str, list[bytes]]]:
    requests: list[bytes] = []
    handlers: set[asyncio.Task[None]] = set()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        handlers.add(task)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            requests.append(await reader.readexactly(length))
            body = bodies[min(len(requests) - 1, len(bodies) - 1)]
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/x-ndjson\r\n"
                + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}", requests
    finally:
        server.close()
        await server.wait_closed()
        for handler in tuple(handlers):
            handler.cancel()
        await asyncio.gather(*handlers, return_exceptions=True)


class ScriptModel:
    name = "synthetic-fallback"

    def __init__(self, fail_first: bool = False) -> None:
        self.requests: list[ModelRequest] = []
        self.fail_first = fail_first

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        if self.fail_first and len(self.requests) % 2:
            raise ConnectionError("synthetic unavailable provider")
        yield ModelChunk("text", "recovered")
        yield ModelChunk("finished")


class ScriptTransport:
    def __init__(self, steps: tuple[str | Exception, ...]) -> None:
        self.steps = steps
        self.closed = False

    async def stream_lines(
        self,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout: float,
        cancellation: CancellationToken,
    ) -> AsyncIterator[str]:
        del url, payload, headers, timeout, cancellation
        try:
            for step in self.steps:
                if isinstance(step, Exception):
                    raise step
                yield step
        finally:
            self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"model loading", b'{"message":', b"\xff"])
async def test_real_http_json_failures_have_safe_adapter_error(body: bytes) -> None:
    async with provider_server((body,)) as (url, requests):
        with pytest.raises(ValueError) as failure:
            await UrllibJsonTransport().post(url, {"prompt": "synthetic"}, {}, 2)
    assert type(failure.value).__name__ == "ProviderResponseInvalid"
    assert str(failure.value) == "provider returned invalid JSON or text encoding"
    assert failure.value.__context__ is failure.value.__cause__ is None
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        b"model loading\n",
        b'{"message":\n',
        b"\xff\n",
        b'{"error":"synthetic model loading"}\n',
    ],
)
async def test_real_ollama_invalid_ndjson_never_dispatches_fallback(body: bytes) -> None:
    fallback = ScriptModel()
    async with provider_server((body,)) as (url, requests):
        wrapper = FailoverModel(
            (OllamaAdapter(base_url=url, model="synthetic", timeout=2), fallback),
            backoff_seconds=0,
        )
        with pytest.raises(ValueError) as failure:
            _ = [c async for c in wrapper.stream(ModelRequest("hello", "g"), CancellationToken())]
    assert type(failure.value).__name__ == "ProviderResponseInvalid"
    assert failure.value.__context__ is failure.value.__cause__ is None
    assert len(requests) == 1
    assert not fallback.requests


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first",
    [
        '{"message":{"content":"partial"}}',
        '{"message":{"tool_calls":[{"function":{"name":"read","arguments":{}}}]}}',
    ],
)
@pytest.mark.parametrize("failure_kind", ["json", "unicode"])
async def test_partial_output_survives_protocol_failure_without_retry(
    first: str, failure_kind: str
) -> None:
    bad: str | Exception = (
        "synthetic malformed provider payload"
        if failure_kind == "json"
        else UnicodeDecodeError("utf-8", b"\xff", 0, 1, "synthetic encoding failure")
    )
    transport = ScriptTransport((first, bad))
    fallback = ScriptModel()
    wrapper = FailoverModel(
        (OllamaAdapter(model="synthetic", transport=transport), fallback), backoff_seconds=0
    )
    chunks: list[ModelChunk] = []
    with pytest.raises(ValueError) as failure:
        async for chunk in wrapper.stream(ModelRequest("hello", "g"), CancellationToken()):
            chunks.append(chunk)
    assert type(failure.value).__name__ == "ProviderResponseInvalid"
    assert failure.value.__context__ is failure.value.__cause__ is None
    assert len(chunks) == 1
    assert chunks[0].kind == ("text" if "partial" in first else "tool_request")
    assert "synthetic" not in str(failure.value)
    assert not fallback.requests
    assert transport.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["none", "text", "tool"])
async def test_openai_bad_sse_preserves_emission_and_tool_fence(prefix: str) -> None:
    first = {
        "none": (),
        "text": ('data: {"choices":[{"delta":{"content":"partial"}}]}',),
        "tool": (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"intent",'
            '"function":{"name":"read","arguments":"{"}}]}}]}',
        ),
    }[prefix]
    transport = ScriptTransport((*first, "data: synthetic malformed provider payload"))
    adapter = OpenAICompatibleAdapter(
        base_url="http://127.0.0.1",
        api_key="synthetic",  # pragma: allowlist secret
        model="synthetic",
        transport=transport,
    )
    fallback = ScriptModel()
    chunks: list[ModelChunk] = []
    with pytest.raises(ValueError) as failure:
        async for chunk in FailoverModel((adapter, fallback), backoff_seconds=0).stream(
            ModelRequest("synthetic", "g", Privacy.CLOUD_ALLOWED), CancellationToken()
        ):
            chunks.append(chunk)
    assert type(failure.value).__name__ == "ProviderResponseInvalid"
    assert failure.value.__context__ is failure.value.__cause__ is None
    assert [c.text for c in chunks] == (["partial"] if prefix == "text" else [])
    assert ("siro: provider tool intent emitted" in getattr(failure.value, "__notes__", ())) == (
        prefix == "tool"
    )
    assert not fallback.requests
    assert transport.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_phase", ["none", "output", "cleanup"])
async def test_ollama_cleanup_failure_cannot_erase_protocol_failure_or_cancellation(
    cancel_phase: str,
) -> None:
    token = CancellationToken()

    class ClosingTransport(ScriptTransport):
        async def stream_lines(
            self,
            url: str,
            payload: dict[str, object],
            headers: dict[str, str],
            timeout: float,
            cancellation: CancellationToken,
        ) -> AsyncIterator[str]:
            try:
                if cancel_phase == "output":
                    yield '{"message":{"content":"partial"}}'
                yield "synthetic malformed provider payload"
            finally:
                self.closed = True
                if cancel_phase == "cleanup":
                    token.cancel()
                raise ConnectionError("synthetic cleanup failure")

    transport = ClosingTransport(())
    wrapper = FailoverModel((OllamaAdapter(model="synthetic", transport=transport),))
    chunks: list[ModelChunk] = []
    failure = None
    try:
        async for chunk in wrapper.stream(ModelRequest("synthetic", "g"), token):
            chunks.append(chunk)
            token.cancel()
    except ValueError as error:
        failure = error
    assert transport.closed
    assert not any(c.kind == "finished" for c in chunks)
    if cancel_phase != "none":
        assert failure is None
        assert token.cancelled
        assert [c.text for c in chunks] == (["partial"] if cancel_phase == "output" else [])
    else:
        assert type(failure).__name__ == "ProviderResponseInvalid"
        assert getattr(failure, "__notes__", ()) == ["siro: provider stream cleanup failed"]


@pytest.mark.asyncio
async def test_nonstream_ollama_error_envelope_is_not_success() -> None:
    class ErrorTransport:
        async def post(
            self, url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
        ) -> dict[str, object]:
            return {"error": "synthetic private provider detail"}

    adapter = OllamaAdapter(model="synthetic", transport=ErrorTransport())
    with pytest.raises(ValueError) as failure:
        _ = [c async for c in adapter.stream(ModelRequest("hello", "g"), CancellationToken())]
    assert type(failure.value).__name__ == "ProviderResponseInvalid"
    assert str(failure.value) == "provider returned an error response"


@pytest.mark.asyncio
@pytest.mark.parametrize("cancelled", [False, True])
@pytest.mark.parametrize("failure_kind", ["json", "unicode"])
async def test_nonstream_transport_decode_failure_is_safe_and_cancellable(
    cancelled: bool, failure_kind: str
) -> None:
    token = CancellationToken()

    class ErrorTransport:
        async def post(
            self, url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
        ) -> dict[str, object]:
            if cancelled:
                token.cancel()
            if failure_kind == "json":
                raise json.JSONDecodeError("synthetic detail", "synthetic private response", 0)
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "synthetic detail")

    adapter = OllamaAdapter(model="synthetic", transport=ErrorTransport())
    if cancelled:
        assert [c async for c in adapter.stream(ModelRequest("hello", "g"), token)] == []
        assert token.cancelled
    else:
        with pytest.raises(ValueError) as failure:
            _ = [c async for c in adapter.stream(ModelRequest("hello", "g"), token)]
        assert type(failure.value).__name__ == "ProviderResponseInvalid"
        assert "synthetic" not in str(failure.value)
        assert failure.value.__context__ is failure.value.__cause__ is None


@pytest.mark.asyncio
async def test_real_nonstream_decode_failure_after_cancel_stays_cancelled() -> None:
    token = CancellationToken()

    class CancelAfterRead(UrllibJsonTransport):
        async def post(
            self, url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
        ) -> dict[str, object]:
            try:
                return await super().post(url, payload, headers, timeout)
            finally:
                token.cancel()

    async with provider_server((b"synthetic malformed reply",)) as (url, requests):
        adapter = OllamaAdapter(
            base_url=url, model="synthetic", transport=CancelAfterRead(), timeout=2
        )
        assert [c async for c in adapter.stream(ModelRequest("hello", "g"), token)] == []
    assert token.cancelled
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_protocol_failure_leaves_conversation_ready_for_next_turn(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "synthetic.db")
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="Synthetic companion",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        now=datetime.now(UTC),
    )
    signals: list[ConversationSignal] = []

    async def capture(signal: ConversationSignal) -> None:
        signals.append(signal)

    async with provider_server(
        (b"synthetic malformed reply\n", b'{"message":{"content":"recovered"},"done":true}\n')
    ) as (url, requests):
        engine = ConversationEngine(
            FailoverModel((OllamaAdapter(base_url=url, model="synthetic", timeout=2),)),
            SQLiteConversationRepository(store),
            on_signal=capture,
        )
        failed = await engine.respond("session", "siro", "first")
        recovered = await engine.respond("session", "siro", "second")
    assert failed.state is TurnState.FAILED
    assert failed.error == "ProviderResponseInvalid"
    assert recovered.state is TurnState.COMPLETED
    assert recovered.text == "recovered"
    assert len(requests) == 2
    assert [s.state for s in signals if s.kind == "terminal"] == [
        TurnState.FAILED,
        TurnState.COMPLETED,
    ]
    states = await store.run_transaction(
        lambda connection: [
            row[0] for row in connection.execute("SELECT state FROM turns ORDER BY rowid")
        ]
    )
    assert states == ["failed", "completed"]


@pytest.mark.asyncio
async def test_cloud_additional_attempt_budget_is_per_generation() -> None:
    cloud = ScriptModel(fail_first=True)
    wrapper = FailoverModel(
        (cloud,), backoff_seconds=0, cloud_indices=frozenset({0}), cloud_request_budget=1
    )
    for generation in ("one", "two"):
        chunks = [
            c
            async for c in wrapper.stream(
                ModelRequest("synthetic", generation, Privacy.CLOUD_ALLOWED), CancellationToken()
            )
        ]
        assert chunks[0].text == "recovered"
    assert len(cloud.requests) == 4
    assert cloud.requests[0].generation_id == "one"
    assert cloud.requests[2].generation_id == "two"
    assert cloud.requests[1].generation_id != "one"
    assert cloud.requests[3].generation_id != "two"
