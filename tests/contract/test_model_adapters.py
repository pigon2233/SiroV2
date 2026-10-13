from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from siro.adapters.models.failover import FailoverModel
from siro.adapters.models.http import HttpxStreamingTransport
from siro.adapters.models.mock import MockModel
from siro.adapters.models.ollama import OllamaAdapter
from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.ports.models import (
    CancellationToken,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
    ToolDefinition,
)


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
async def test_adapters_preserve_native_tool_message_pairing() -> None:
    messages = (
        ModelMessage("system", "Use tools when needed."),
        ModelMessage("user", "Read notes.txt"),
        ModelMessage(
            "assistant",
            tool_calls=(ToolCall("call-7", "file.read", {"path": "notes.txt"}),),
        ),
        ModelMessage("tool", "hello", tool_call_id="call-7"),
    )
    openai_transport = FakeTransport({"choices": [{"message": {"content": "done"}}]})
    ollama_transport = FakeTransport({"message": {"content": "done"}})
    openai = OpenAICompatibleAdapter(
        base_url="https://provider.invalid",
        api_key="x",
        model="test",
        transport=openai_transport,
    )
    ollama = OllamaAdapter(model="test", transport=ollama_transport)

    await collect(openai, ModelRequest("", "g1", Privacy.CLOUD_ALLOWED, messages=messages))
    await collect(ollama, ModelRequest("", "g2", messages=messages))

    openai_messages = openai_transport.calls[0][1]["messages"]
    ollama_messages = ollama_transport.calls[0][1]["messages"]
    assert isinstance(openai_messages, list) and isinstance(ollama_messages, list)
    assert openai_messages[2]["tool_calls"][0]["id"] == "call-7"
    assert openai_messages[3]["tool_call_id"] == "call-7"
    assert ollama_messages[2]["tool_calls"][0]["function"]["name"] == "file.read"
    assert ollama_messages[3]["tool_call_id"] == "call-7"


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
@pytest.mark.parametrize("content", [None, ""])
async def test_openai_rejects_empty_nonstream_reply_without_fallback(content: str | None) -> None:
    transport = FakeTransport({"choices": [{"message": {"content": content}}]})
    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid", api_key="x", model="test", transport=transport
    )
    fallback = RecordingModel()
    with pytest.raises(ValueError, match="provider returned no usable reply"):
        await collect(
            FailoverModel((adapter, fallback), backoff_seconds=0),
            ModelRequest("hello", "g1", Privacy.CLOUD_ALLOWED),
        )
    assert len(transport.calls) == 1
    assert not fallback.generations


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_reason", ["length", "stop"])
async def test_openai_rejects_empty_stream_reply_without_fallback(finish_reason: str) -> None:
    transport = FakeStreamingTransport(
        (
            'data: {"choices":[{"delta":{"role":"assistant","content":""}}]}',
            'data: {"choices":[],"usage":{"total_tokens":512}}',
            f'data: {{"choices":[{{"delta":{{}},"finish_reason":"{finish_reason}"}}]}}',
            "data: [DONE]",
        )
    )
    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid", api_key="x", model="test", transport=transport
    )
    fallback = RecordingModel()
    chunks = []
    with pytest.raises(ValueError, match="provider returned no usable reply") as failure:
        async for chunk in FailoverModel((adapter, fallback), backoff_seconds=0).stream(
            ModelRequest("hello", "g1", Privacy.CLOUD_ALLOWED), CancellationToken()
        ):
            chunks.append(chunk)
    assert [chunk.kind for chunk in chunks] == ["usage"]
    assert type(failure.value).__name__ == (
        "ProviderOutputTruncated" if finish_reason == "length" else "ValueError"
    )
    assert not fallback.generations


@pytest.mark.asyncio
async def test_openai_stream_accepts_tools_only_reply() -> None:
    transport = FakeStreamingTransport(
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call-1",'
            '"function":{"name":"weather","arguments":"{\\"city\\":\\"Taipei\\"}"}}]}}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
            "data: [DONE]",
        )
    )
    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid", api_key="x", model="test", transport=transport
    )
    chunks = await collect_chunks(adapter, ModelRequest("weather?", "g1", Privacy.CLOUD_ALLOWED))
    assert [chunk.kind for chunk in chunks] == ["tool_request", "finished"]
    assert chunks[0].tool_call == ToolCall("call-1", "weather", {"city": "Taipei"})


@pytest.mark.asyncio
async def test_openai_stream_cancels_without_empty_reply_error() -> None:
    token = CancellationToken()
    transport = FakeStreamingTransport(
        ('data: {"choices":[],"usage":{"total_tokens":3}}', "data: [DONE]")
    )
    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid", api_key="x", model="test", transport=transport
    )
    chunks = []
    async for chunk in adapter.stream(ModelRequest("hello", "g1", Privacy.CLOUD_ALLOWED), token):
        chunks.append(chunk)
        token.cancel()
    assert [chunk.kind for chunk in chunks] == ["usage"]


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("reason", ["length", "content_filter", "unknown"])
@pytest.mark.parametrize("with_tools", [False, True])
async def test_openai_incomplete_output_preserves_text_without_tools_or_retry(
    streaming: bool, reason: str, with_tools: bool
) -> None:
    message: dict[str, object] = {"content": "synthetic partial"}
    if with_tools:
        message["tool_calls"] = [
            {"index": 0, "id": "intent", "function": {"name": "weather", "arguments": "{}"}}
        ]
    if streaming:
        transport: FakeTransport | FakeStreamingTransport = FakeStreamingTransport(
            (
                "data: " + json.dumps({"choices": [{"delta": message}]}),
                # A terminal choice need not contain delta; a later stop cannot erase failure.
                "data: " + json.dumps({"choices": [{"finish_reason": reason}]}),
                'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
                "data: [DONE]",
            )
        )
    else:
        transport = FakeTransport({"choices": [{"message": message, "finish_reason": reason}]})
    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid",
        api_key="synthetic",  # pragma: allowlist secret
        model="test",
        transport=transport,
    )
    fallback = RecordingModel()
    chunks = []
    with pytest.raises(ValueError, match="provider output"):
        async for chunk in FailoverModel((adapter, fallback), backoff_seconds=0).stream(
            ModelRequest("synthetic", "g", Privacy.CLOUD_ALLOWED), CancellationToken()
        ):
            chunks.append(chunk)
    assert [chunk.text for chunk in chunks if chunk.kind == "text"] == ["synthetic partial"]
    assert not any(chunk.kind in {"tool_request", "finished"} for chunk in chunks)
    assert not fallback.generations


@pytest.mark.asyncio
@pytest.mark.parametrize("with_tools", [False, True])
async def test_openai_bare_eof_is_incomplete_and_never_retries_buffered_intents(
    with_tools: bool,
) -> None:
    delta: dict[str, object] = {"content": "partial"}
    if with_tools:
        delta = {
            "tool_calls": [
                {"index": 0, "id": "intent", "function": {"name": "weather", "arguments": "{}"}}
            ]
        }
    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid",
        api_key="synthetic",  # pragma: allowlist secret
        model="test",
        transport=FakeStreamingTransport(("data: " + json.dumps({"choices": [{"delta": delta}]}),)),
    )
    fallback = RecordingModel()
    chunks = []
    with pytest.raises(ValueError, match="provider output"):
        async for chunk in FailoverModel((adapter, fallback), backoff_seconds=0).stream(
            ModelRequest("synthetic", "g", Privacy.CLOUD_ALLOWED), CancellationToken()
        ):
            chunks.append(chunk)
    assert not any(chunk.kind in {"tool_request", "finished"} for chunk in chunks)
    assert not fallback.generations


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason,done_marker",
    [(None, True), ("stop", False), ("stop", True), ("tool_calls", False), ("tool_calls", True)],
)
async def test_openai_successful_termination_compatibility(
    reason: str | None, done_marker: bool
) -> None:
    delta: dict[str, object] = {"content": "complete"}
    if reason == "tool_calls":
        delta = {
            "tool_calls": [
                {"index": 0, "id": "intent", "function": {"name": "weather", "arguments": "{}"}}
            ]
        }
    lines = ["data: " + json.dumps({"choices": [{"delta": delta}]})]
    if reason:
        lines.append("data: " + json.dumps({"choices": [{"finish_reason": reason}]}))
        lines.append('data: {"choices":[],"usage":{"total_tokens":2}}')
    if done_marker:
        lines.append("data: [DONE]")
    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid",
        api_key="synthetic",  # pragma: allowlist secret
        model="test",
        transport=FakeStreamingTransport(tuple(lines)),
    )
    chunks = await collect_chunks(adapter, ModelRequest("synthetic", "g", Privacy.CLOUD_ALLOWED))
    assert chunks[-1].kind == "finished"
    if reason == "tool_calls":
        assert next(c.tool_call for c in chunks if c.kind == "tool_request") == ToolCall(
            "intent", "weather", {}
        )
    else:
        assert "".join(c.text for c in chunks if c.kind == "text") == "complete"


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_cancel_after_partial_text_precedes_output_limit_error(streaming: bool) -> None:
    choice = {"delta": {"content": "partial"}, "finish_reason": "length"}
    transport: FakeTransport | FakeStreamingTransport
    if streaming:
        transport = FakeStreamingTransport(("data: " + json.dumps({"choices": [choice]}),))
    else:
        transport = FakeTransport(
            {"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]}
        )
    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid",
        api_key="synthetic",  # pragma: allowlist secret
        model="test",
        transport=transport,
    )
    token = CancellationToken()
    chunks = []
    async for chunk in adapter.stream(ModelRequest("synthetic", "g", Privacy.CLOUD_ALLOWED), token):
        chunks.append(chunk)
        token.cancel()
    assert [c.kind for c in chunks] == ["text"]


@pytest.mark.asyncio
async def test_transport_cancellation_precedes_simultaneous_error() -> None:
    class CancellingTransport(FakeStreamingTransport):
        async def stream_lines(
            self,
            url: str,
            payload: dict[str, object],
            headers: dict[str, str],
            timeout: float,
            cancellation: CancellationToken,
        ) -> Any:
            yield 'data: {"choices":[{"delta":{"content":"partial"}}]}'
            cancellation.cancel()
            raise ConnectionError("synthetic cancellation race")

    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid",
        api_key="synthetic",  # pragma: allowlist secret
        model="test",
        transport=CancellingTransport(()),
    )
    token = CancellationToken()
    chunks = [
        c
        async for c in adapter.stream(ModelRequest("synthetic", "g", Privacy.CLOUD_ALLOWED), token)
    ]
    assert token.cancelled
    assert [c.kind for c in chunks] == ["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["done", "length", "cancel"])
async def test_adapter_closes_owned_stream_before_returning(ending: str) -> None:
    class OwnedTransport(FakeStreamingTransport):
        closed = False

        async def stream_lines(
            self,
            url: str,
            payload: dict[str, object],
            headers: dict[str, str],
            timeout: float,
            cancellation: CancellationToken,
        ) -> Any:
            try:
                yield 'data: {"choices":[{"delta":{"content":"partial"}}]}'
                if ending == "length":
                    yield 'data: {"choices":[{"finish_reason":"length"}]}'
                yield "data: [DONE]"
            finally:
                self.closed = True

    transport = OwnedTransport(())
    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid",
        api_key="synthetic",  # pragma: allowlist secret
        model="test",
        transport=transport,
    )
    token = CancellationToken()
    chunks = []
    try:
        async for chunk in adapter.stream(
            ModelRequest("synthetic", "g", Privacy.CLOUD_ALLOWED), token
        ):
            chunks.append(chunk)
            if ending == "cancel":
                token.cancel()
    except ValueError:
        assert ending == "length"
    assert transport.closed
    assert (chunks[-1].kind == "finished") == (ending == "done")


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["done", "length", "cancel"])
async def test_cleanup_error_cannot_erase_failure_cancellation_or_tool_intent(ending: str) -> None:
    class ClosingTransport:
        def stream_lines(
            self,
            url: str,
            payload: dict[str, object],
            headers: dict[str, str],
            timeout: float,
            cancellation: CancellationToken,
        ) -> Any:
            values = iter(
                (
                    'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"intent",'
                    '"function":{"name":"weather","arguments":"{}"}}]}}]}',
                    'data: {"choices":[{"finish_reason":"length"}]}'
                    if ending == "length"
                    else "data: [DONE]",
                )
            )

            class Lines:
                def __aiter__(self) -> Any:
                    return self

                async def __anext__(self) -> str:
                    value = next(values, None)
                    if value is None:
                        raise StopAsyncIteration
                    if ending == "cancel" and value == "data: [DONE]":
                        cancellation.cancel()
                    return value

                async def aclose(self) -> None:
                    raise ConnectionError("synthetic cleanup failure")

            return Lines()

    adapter = OpenAICompatibleAdapter(
        base_url="https://provider.invalid",
        api_key="synthetic",  # pragma: allowlist secret
        model="test",
        transport=ClosingTransport(),
    )
    token = CancellationToken()
    fallback = RecordingModel()
    chunks = []
    failure = None
    try:
        async for chunk in FailoverModel((adapter, fallback), backoff_seconds=0).stream(
            ModelRequest("synthetic", "g", Privacy.CLOUD_ALLOWED), token
        ):
            chunks.append(chunk)
    except Exception as error:
        failure = type(error).__name__
    assert not fallback.generations
    assert chunks == []
    assert (
        failure
        == {"done": "ConnectionError", "length": "ProviderOutputTruncated", "cancel": None}[ending]
    )
    assert token.cancelled == (ending == "cancel")


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
