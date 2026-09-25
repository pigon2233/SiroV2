from __future__ import annotations

import asyncio
from typing import Any

import pytest

from siro.adapters.models.failover import FailoverModel
from siro.adapters.models.http import HttpxStreamingTransport
from siro.adapters.models.mock import MockModel
from siro.adapters.models.ollama import OllamaAdapter
from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.ports.models import CancellationToken, ModelRequest, Privacy, ToolDefinition


class FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    async def post(
        self, url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
    ) -> dict[str, object]:
        del timeout
        self.calls.append((url, payload, headers))
        return self.response


class FakeStreamingTransport:
    def __init__(self, lines: tuple[str, ...]) -> None:
        self.lines = lines
        self.payload: dict[str, object] | None = None

    async def stream_lines(
        self,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout: float,
        cancellation: CancellationToken,
    ) -> Any:
        del url, headers, timeout
        self.payload = payload
        for line in self.lines:
            if cancellation.cancelled:
                return
            await asyncio.sleep(0)
            yield line


async def collect(adapter: Any, request: ModelRequest) -> list[str]:
    return [
        chunk.text
        async for chunk in adapter.stream(request, CancellationToken())
        if chunk.kind == "text"
    ]


async def collect_chunks(adapter: Any, request: ModelRequest) -> list[Any]:
    return [chunk async for chunk in adapter.stream(request, CancellationToken())]


@pytest.mark.asyncio
async def test_openai_adapter_requires_cloud_authorization() -> None:
    transport = FakeTransport({"choices": [{"message": {"content": "cloud"}}]})
    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid", api_key="x", model="test", transport=transport
    )
    with pytest.raises(PermissionError):
        await collect(adapter, ModelRequest("private", "g1"))
    assert not transport.calls
    assert await collect(adapter, ModelRequest("allowed", "g2", Privacy.CLOUD_ALLOWED)) == ["cloud"]


@pytest.mark.asyncio
async def test_ollama_adapter_accepts_local_only() -> None:
    transport = FakeTransport(
        {"message": {"content": "local"}, "prompt_eval_count": 1, "eval_count": 2}
    )
    adapter = OllamaAdapter(model="test", transport=transport)
    assert await collect(adapter, ModelRequest("private", "g1")) == ["local"]
    assert transport.calls[0][0].endswith("/api/chat")


class BrokenModel:
    name = "broken"

    def __init__(self) -> None:
        self.generations: list[str] = []

    async def stream(self, request: Any, cancellation: Any) -> Any:
        del cancellation
        self.generations.append(request.generation_id)
        if False:
            yield None
        raise ConnectionError("offline")


@pytest.mark.asyncio
async def test_failover_uses_second_backend_before_text_is_visible() -> None:
    broken = BrokenModel()
    fallback = RecordingModel()
    adapter = FailoverModel((broken, fallback))
    assert await collect(adapter, ModelRequest("hello", "g1")) == ["fallback"]
    assert broken.generations == ["g1"]
    assert len(fallback.generations) == 1
    assert fallback.generations[0] != "g1"


class RecordingModel(MockModel):
    def __init__(self) -> None:
        super().__init__(("fallback",))
        self.generations: list[str] = []

    async def stream(self, request: Any, cancellation: Any) -> Any:
        self.generations.append(request.generation_id)
        async for chunk in super().stream(request, cancellation):
            yield chunk


@pytest.mark.asyncio
async def test_both_adapters_map_tool_requests_and_usage() -> None:
    tool = ToolDefinition("weather", "Get weather", {"type": "object"})
    openai = OpenAICompatibleAdapter(
        base_url="https://provider.invalid",
        api_key="x",
        model="test",
        transport=FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "function": {
                                        "name": "weather",
                                        "arguments": '{"city":"Taipei"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"total_tokens": 7},
            }
        ),
    )
    ollama = OllamaAdapter(
        model="test",
        transport=FakeTransport(
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "weather", "arguments": {"city": "Taipei"}}}
                    ],
                },
                "prompt_eval_count": 4,
                "eval_count": 3,
            }
        ),
    )
    request = ModelRequest("weather?", "g1", Privacy.CLOUD_ALLOWED, tools=(tool,))
    for adapter in (openai, ollama):
        chunks = await collect_chunks(adapter, request)
        tool_chunk = next(chunk for chunk in chunks if chunk.kind == "tool_request")
        usage_chunk = next(chunk for chunk in chunks if chunk.kind == "usage")
        assert tool_chunk.tool_call is not None
        assert tool_chunk.tool_call.name == "weather"
        assert tool_chunk.tool_call.arguments == {"city": "Taipei"}
        assert usage_chunk.usage_tokens == 7


def test_model_request_enforces_output_budget() -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        ModelRequest("hello", "g1", max_output_tokens=0)


@pytest.mark.asyncio
async def test_openai_and_ollama_emit_real_stream_deltas() -> None:
    openai_transport = FakeStreamingTransport(
        (
            'data: {"choices":[{"delta":{"content":"hel"}}]}',
            'data: {"choices":[{"delta":{"content":"lo"}}]}',
            'data: {"choices":[],"usage":{"total_tokens":4}}',
            "data: [DONE]",
        )
    )
    openai = OpenAICompatibleAdapter(
        base_url="https://provider.invalid",
        api_key="x",
        model="test",
        transport=openai_transport,
    )
    openai_chunks = await collect_chunks(openai, ModelRequest("hello", "g1", Privacy.CLOUD_ALLOWED))
    assert [chunk.text for chunk in openai_chunks if chunk.kind == "text"] == ["hel", "lo"]
    assert openai_transport.payload is not None and openai_transport.payload["stream"] is True

    ollama_transport = FakeStreamingTransport(
        (
            '{"message":{"content":"lo"},"done":false}',
            '{"message":{"content":"cal"},"done":false}',
            '{"message":{"content":""},"done":true,"prompt_eval_count":2,"eval_count":2}',
        )
    )
    ollama = OllamaAdapter(model="test", transport=ollama_transport)
    ollama_chunks = await collect_chunks(ollama, ModelRequest("hello", "g2"))
    assert [chunk.text for chunk in ollama_chunks if chunk.kind == "text"] == ["lo", "cal"]
    assert ollama_transport.payload is not None and ollama_transport.payload["stream"] is True


@pytest.mark.asyncio
async def test_http_stream_cancellation_closes_stalled_request() -> None:
    connected = asyncio.Event()
    handlers: set[asyncio.Task[None]] = set()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        handlers.add(task)
        try:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n"
            )
            await writer.drain()
            connected.set()
            await asyncio.sleep(5)
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    cancellation = CancellationToken()

    async def consume() -> None:
        async for _ in HttpxStreamingTransport().stream_lines(
            f"http://127.0.0.1:{port}", {}, {}, 10, cancellation
        ):
            pass

    consumer = asyncio.create_task(consume())
    await asyncio.wait_for(connected.wait(), 1)
    cancellation.cancel()
    await asyncio.wait_for(consumer, 0.5)
    server.close()
    await server.wait_closed()
    for handler in tuple(handlers):
        handler.cancel()
    await asyncio.gather(*handlers, return_exceptions=True)
