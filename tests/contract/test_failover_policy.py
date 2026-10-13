from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest

from siro.adapters.models.failover import FailoverModel
from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
)


class ScriptModel:
    name = "synthetic-policy"

    def __init__(self, steps: tuple[ModelChunk | Exception, ...]) -> None:
        self.steps = steps
        self.requests: list[ModelRequest] = []
        self.entered = asyncio.Event()

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        self.entered.set()
        for step in self.steps:
            if isinstance(step, Exception):
                raise step
            yield step


def status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://synthetic.invalid")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("synthetic status", request=request, response=response)


async def consume(
    model: FailoverModel, request: ModelRequest, token: CancellationToken | None = None
) -> list[ModelChunk]:
    return [chunk async for chunk in model.stream(request, token or CancellationToken())]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        ConnectionError(),
        TimeoutError(),
        status_error(429),
        status_error(503),
        httpx.ReadTimeout("synthetic"),
    ],
)
async def test_max_two_attempts_and_request_preservation(error: Exception) -> None:
    first = ScriptModel((error,))
    second = ScriptModel((error,))
    third = ScriptModel((ModelChunk("text", "must never run"),))
    request = ModelRequest(
        "goal", "original", messages=(ModelMessage("user", "raw goal"),), max_output_tokens=9
    )
    model = FailoverModel((first, second, third), backoff_seconds=0)
    with pytest.raises(type(error)):
        await consume(model, request)
    assert len(first.requests) == len(second.requests) == 1 and not third.requests
    assert first.requests[0] is request
    assert second.requests[0].generation_id != "original"
    assert second.requests[0].messages == request.messages
    assert (
        second.requests[0].privacy is request.privacy and second.requests[0].max_output_tokens == 9
    )


@pytest.mark.asyncio
async def test_single_backend_retry_is_bounded() -> None:
    model = ScriptModel((ConnectionError(),))
    with pytest.raises(ConnectionError):
        await consume(FailoverModel((model,), backoff_seconds=0), ModelRequest("goal", "g"))
    assert (
        len(model.requests) == 2
        and model.requests[0].generation_id != model.requests[1].generation_id
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "chunk",
    [
        ModelChunk("text", "partial"),
        ModelChunk("tool_request", tool_call=ToolCall("t", "computer.execute", {})),
        ModelChunk("tool_request"),
        ModelChunk("finished"),
    ],
)
async def test_emission_prevents_fallback(chunk: ModelChunk) -> None:
    primary = ScriptModel((chunk, ConnectionError()))
    fallback = ScriptModel((ModelChunk("text", "wrong success"),))
    with pytest.raises(ConnectionError):
        await consume(
            FailoverModel((primary, fallback), backoff_seconds=0), ModelRequest("goal", "g")
        )
    assert len(primary.requests) == 1 and not fallback.requests


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [ValueError(), PermissionError(), status_error(400), status_error(401), status_error(403)],
)
async def test_permanent_errors_do_not_retry(error: Exception) -> None:
    primary = ScriptModel((error,))
    fallback = ScriptModel((ModelChunk("text", "wrong success"),))
    with pytest.raises(type(error)):
        await consume(
            FailoverModel((primary, fallback), backoff_seconds=0), ModelRequest("goal", "g")
        )
    assert len(primary.requests) == 1 and not fallback.requests


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "privacy,budget,allowed",
    [
        (Privacy.LOCAL_ONLY, 1, False),
        (Privacy.CLOUD_ALLOWED, 0, False),
        (Privacy.CLOUD_ALLOWED, 1, True),
    ],
)
async def test_cloud_fallback_privacy_and_explicit_budget(
    privacy: Privacy, budget: int, allowed: bool
) -> None:
    primary = ScriptModel((ConnectionError(),))
    cloud = ScriptModel((ModelChunk("text", "cloud answer"),))
    wrapper = FailoverModel(
        (primary, cloud),
        backoff_seconds=0,
        cloud_indices=frozenset({1}),
        cloud_request_budget=budget,
    )
    if allowed:
        chunks = await consume(wrapper, ModelRequest("goal", "g", privacy))
        assert chunks[0].text == "cloud answer"
    else:
        with pytest.raises(ConnectionError):
            await consume(wrapper, ModelRequest("goal", "g", privacy))
    assert len(cloud.requests) == int(allowed)


@pytest.mark.asyncio
async def test_cloud_primary_no_unbudgeted_extra_request() -> None:
    cloud = ScriptModel((status_error(429),))
    wrapper = FailoverModel((cloud,), backoff_seconds=0, cloud_indices=frozenset({0}))
    with pytest.raises(httpx.HTTPStatusError):
        await consume(wrapper, ModelRequest("goal", "g", Privacy.CLOUD_ALLOWED))
    assert len(cloud.requests) == 1
    with pytest.raises(PermissionError):
        await consume(wrapper, ModelRequest("private", "g2"))
    assert len(cloud.requests) == 1


@pytest.mark.asyncio
async def test_cancel_during_backoff_prevents_second_attempt() -> None:
    primary = ScriptModel((ConnectionError(),))
    fallback = ScriptModel((ModelChunk("text", "wrong"),))
    token = CancellationToken()
    task = asyncio.create_task(
        consume(
            FailoverModel((primary, fallback), backoff_seconds=5), ModelRequest("goal", "g"), token
        )
    )
    await asyncio.wait_for(primary.entered.wait(), 1)
    await asyncio.sleep(0)  # the provider error has entered cancellation-aware backoff
    token.cancel()
    assert await asyncio.wait_for(task, 0.5) == []
    assert len(primary.requests) == 1 and not fallback.requests


@pytest.mark.asyncio
async def test_task_cancel_and_precancel_never_dispatch_later_backend() -> None:
    primary = ScriptModel((ConnectionError(),))
    fallback = ScriptModel((ModelChunk("text", "wrong"),))
    model = FailoverModel((primary, fallback), backoff_seconds=5)
    task = asyncio.create_task(consume(model, ModelRequest("goal", "g")))
    await primary.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    token = CancellationToken()
    token.cancel()
    assert await consume(model, ModelRequest("goal", "g"), token) == []
    assert len(primary.requests) == 1 and not fallback.requests


class ToolFragmentTransport:
    async def stream_lines(
        self,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout: float,
        cancellation: CancellationToken,
    ) -> AsyncIterator[str]:
        yield (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"x",'
            '"function":{"name":"computer.execute","arguments":"{"}}]}}]}'
        )
        raise httpx.ReadError("interrupted after tool fragment")


@pytest.mark.asyncio
async def test_buffered_openai_tool_fragment_fences_fallback() -> None:
    primary = OpenAICompatibleAdapter(
        base_url="http://synthetic.invalid",
        api_key="synthetic",  # pragma: allowlist secret
        model="synthetic",
        transport=ToolFragmentTransport(),
    )
    fallback = ScriptModel((ModelChunk("text", "wrong"),))
    with pytest.raises(httpx.ReadError):
        await consume(
            FailoverModel((primary, fallback), backoff_seconds=0),
            ModelRequest("goal", "g", Privacy.CLOUD_ALLOWED),
        )
    assert not fallback.requests


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["ollama429", "openai_fragment"])
async def test_real_http_transport_retry_and_fragment_fence(mode: str) -> None:
    from siro.adapters.models.ollama import OllamaAdapter

    bodies: list[bytes] = []
    handlers: set[asyncio.Task[None]] = set()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
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
            bodies.append(await reader.readexactly(length))
            if mode == "ollama429" and len(bodies) == 1:
                body = b"{}"
                writer.write(
                    b"HTTP/1.1 429 Too Many Requests\r\n"
                    b"Content-Length: 2\r\nConnection: close\r\n\r\n" + body
                )
            else:
                if mode == "openai_fragment":
                    body = (
                        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
                        b'"id":"t","function":{"name":"computer.execute","arguments":"{"}}]}}]}\n\n'
                    )
                    content_length = (
                        len(body) + 100
                    )  # force actual premature EOF after a tool delta
                else:
                    body = b'{"message":{"content":"local retry success"},"done":true}\n'
                    content_length = len(body)
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                    + f"Content-Length: {content_length}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    fallback = ScriptModel((ModelChunk("text", "must not fallback"),))
    try:
        if mode == "ollama429":
            wrapper = FailoverModel(
                (OllamaAdapter(model="synthetic", base_url=f"http://127.0.0.1:{port}"),),
                backoff_seconds=0,
            )
            chunks = await consume(wrapper, ModelRequest("synthetic", "g"))
            assert any(c.text == "local retry success" for c in chunks) and len(bodies) == 2
        else:
            wrapper = FailoverModel(
                (
                    OpenAICompatibleAdapter(
                        base_url=f"http://127.0.0.1:{port}",
                        api_key="synthetic",  # pragma: allowlist secret
                        model="synthetic",  # pragma: allowlist secret
                    ),
                    fallback,
                ),
                backoff_seconds=0,
            )
            with pytest.raises(httpx.RemoteProtocolError):
                await consume(wrapper, ModelRequest("synthetic", "g", Privacy.CLOUD_ALLOWED))
            assert len(bodies) == 1 and not fallback.requests
    finally:
        server.close()
        await server.wait_closed()
        await asyncio.gather(*tuple(handlers), return_exceptions=True)


@pytest.mark.asyncio
async def test_selected_provider_name_stays_stable_after_fallback() -> None:
    primary = ScriptModel((ConnectionError(),))
    primary.name = "selected-local"
    fallback = ScriptModel((ModelChunk("text", "fallback"), ModelChunk("finished")))
    fallback.name = "alternate-local"
    model = FailoverModel((primary, fallback), backoff_seconds=0)
    assert model.name == "selected-local"
    assert (await consume(model, ModelRequest("goal", "g")))[0].text == "fallback"
    assert len(primary.requests) == len(fallback.requests) == 1
    assert model.name == "selected-local"
