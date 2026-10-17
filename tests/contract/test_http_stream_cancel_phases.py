from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from siro.adapters.models.failover import FailoverModel
from siro.adapters.models.http import HttpxStreamingTransport
from siro.adapters.models.mock import MockModel
from siro.adapters.models.ollama import OllamaAdapter
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest


@asynccontextmanager
async def stalled_provider(
    send_headers: bool,
) -> AsyncIterator[tuple[str, asyncio.Event, asyncio.Event]]:
    received, disconnected = asyncio.Event(), asyncio.Event()
    handlers: set[asyncio.Task[None]] = set()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        handlers.add(task)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.partition(b":")[2])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            await reader.readexactly(length)
            if send_headers:
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/x-ndjson\r\n"
                    b"Transfer-Encoding: chunked\r\n\r\n"
                )
                await writer.drain()
            received.set()
            assert await reader.read() == b""
            disconnected.set()
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}", received, disconnected
    finally:
        server.close()
        await server.wait_closed()
        for handler in tuple(handlers):
            handler.cancel()
        await asyncio.gather(*tuple(handlers), return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("send_headers", [False, True])
async def test_model_token_cancel_closes_owned_socket_before_or_after_headers(
    send_headers: bool,
) -> None:
    token = CancellationToken()
    chunks: list[str] = []
    async with stalled_provider(send_headers) as (url, received, disconnected):

        async def consume() -> None:
            async for line in HttpxStreamingTransport().stream_lines(
                url, {"synthetic": True}, {}, 10, token
            ):
                chunks.append(line)

        consumer = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(received.wait(), 1)
            token.cancel()
            # Preserve the existing transport cancellation deadline.
            await asyncio.wait_for(asyncio.shield(consumer), 0.5)
            await asyncio.wait_for(disconnected.wait(), 0.5)
            assert consumer.done() and chunks == []
        finally:
            if not consumer.done():
                consumer.cancel()
            await asyncio.gather(consumer, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "status", "timeout"])
async def test_cancel_at_response_open_wins_same_tick_result_or_error(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    token = CancellationToken()
    requests: list[httpx.Request] = []
    closed = False

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"must-not-emit\n"

        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        token.cancel()
        if outcome == "timeout":
            raise httpx.ReadTimeout("synthetic sensitive timeout", request=request)
        return httpx.Response(503 if outcome == "status" else 200, stream=Body())

    original = httpx.AsyncClient
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    chunks = [
        line
        async for line in HttpxStreamingTransport().stream_lines(
            "https://synthetic.invalid/private-must-not-log",
            {"synthetic": True},
            {},
            10,
            token,
        )
    ]
    assert chunks == [] and len(requests) == 1
    if outcome != "timeout":
        assert closed


@pytest.mark.asyncio
async def test_external_task_cancel_joins_owned_body_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reading, exited = asyncio.Event(), asyncio.Event()
    closed = False
    body_reads: set[asyncio.Task[object]] = set()

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            task = asyncio.current_task()
            assert task is not None
            body_reads.add(task)
            try:
                reading.set()
                await asyncio.Event().wait()
                yield b"must-not-emit\n"
            finally:
                exited.set()
                body_reads.discard(task)

        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, stream=Body()))
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )

    async def consume() -> None:
        async for _ in HttpxStreamingTransport().stream_lines(
            "https://synthetic.invalid", {}, {}, 10, CancellationToken()
        ):
            pytest.fail("a stalled body cannot emit output")

    consumer = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(reading.wait(), 1)
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
        await asyncio.wait_for(exited.wait(), 0.5)
        assert closed
    finally:
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
        for body_read in tuple(body_reads):
            body_read.cancel()
        await asyncio.gather(*tuple(body_reads), return_exceptions=True)


class RecordingFallback(MockModel):
    def __init__(self) -> None:
        super().__init__(("must-not-fallback",))
        self.requests = 0

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests += 1
        async for chunk in super().stream(request, cancellation):
            yield chunk


@pytest.mark.asyncio
async def test_cancelled_request_open_timeout_never_retries_or_exposes_payload(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    token = CancellationToken()
    calls = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        token.cancel()
        raise httpx.ReadTimeout("synthetic-private-timeout-body", request=request)

    original = httpx.AsyncClient
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    fallback = RecordingFallback()
    adapter = FailoverModel((OllamaAdapter(model="synthetic"), fallback), backoff_seconds=0)
    chunks = [chunk async for chunk in adapter.stream(ModelRequest("synthetic", "g"), token)]
    assert chunks == [] and calls == 1 and fallback.requests == 0
    assert "synthetic-private-timeout-body" not in caplog.text
