"""Adapter for a local Ollama HTTP backend."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import cast

from siro.adapters.models.http import (
    HttpxStreamingTransport,
    JsonTransport,
    ProviderResponseInvalid,
    StreamingJsonTransport,
    _decode_json_response,
)
from siro.ports.models import CancellationToken, ModelChunk, ModelMessage, ModelRequest, ToolCall


def _serialize_message(message: ModelMessage) -> dict[str, object]:
    serialized: dict[str, object] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        serialized["tool_calls"] = [
            {"function": {"name": call.name, "arguments": call.arguments}}
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        serialized["tool_call_id"] = message.tool_call_id
    return serialized


class OllamaAdapter:
    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str,
        transport: JsonTransport | StreamingJsonTransport | None = None,
        timeout: float = 120,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/api/chat"
        self._model = model
        self._transport = transport or HttpxStreamingTransport()
        self._timeout = timeout

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        if cancellation.cancelled:
            return
        payload: dict[str, object] = {
            "model": self._model,
            "messages": (
                [_serialize_message(message) for message in request.messages]
                if request.messages
                else [{"role": "user", "content": request.prompt}]
            ),
            "stream": hasattr(self._transport, "stream_lines"),
            "think": False,
            "options": {"num_predict": request.max_output_tokens},
        }
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in request.tools
            ]
        if hasattr(self._transport, "stream_lines"):
            async for chunk in self._stream_response(payload, request, cancellation):
                yield chunk
            return
        try:
            response = await self._transport.post(self._url, payload, {}, self._timeout)
        except (json.JSONDecodeError, UnicodeDecodeError, ProviderResponseInvalid):
            response = None
        if response is None:
            if cancellation.cancelled:
                return
            raise ProviderResponseInvalid("provider returned invalid JSON or text encoding")
        if cancellation.cancelled:
            return
        if "error" in response:
            raise ProviderResponseInvalid("provider returned an error response")
        message = response.get("message")
        if not isinstance(message, dict):
            raise ValueError("Ollama response is missing message")
        text = message.get("content")
        if isinstance(text, str) and text:
            yield ModelChunk("text", text)
        tool_calls = message.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            raise ValueError("Ollama tool_calls is not a list")
        for index, raw_call in enumerate(tool_calls):
            if not isinstance(raw_call, dict) or not isinstance(raw_call.get("function"), dict):
                raise ValueError("Ollama tool call is malformed")
            function = raw_call["function"]
            name, arguments = function.get("name"), function.get("arguments")
            if not isinstance(name, str) or not isinstance(arguments, dict):
                raise ValueError("Ollama tool call has invalid name or arguments")
            yield ModelChunk(
                "tool_request",
                tool_call=ToolCall(f"ollama-{request.generation_id}-{index}", name, arguments),
            )
        if not isinstance(text, str) and not tool_calls:
            raise ValueError("Ollama message has neither text nor tool calls")
        prompt_count, output_count = response.get("prompt_eval_count"), response.get("eval_count")
        if isinstance(prompt_count, int) and isinstance(output_count, int):
            yield ModelChunk("usage", usage_tokens=prompt_count + output_count)
        yield ModelChunk("finished")

    async def _stream_response(
        self,
        payload: dict[str, object],
        request: ModelRequest,
        cancellation: CancellationToken,
    ) -> AsyncIterator[ModelChunk]:
        transport = cast(StreamingJsonTransport, self._transport)
        call_index = 0
        lines = transport.stream_lines(self._url, payload, {}, self._timeout, cancellation)
        primary_error: Exception | None = None
        try:
            async for line in lines:
                if cancellation.cancelled:
                    return
                if not line:
                    continue
                event = _decode_json_response(line)
                if not isinstance(event, dict):
                    raise ValueError("Ollama stream event is not an object")
                if "error" in event:
                    raise ProviderResponseInvalid("provider returned an error response")
                message = event.get("message", {})
                if not isinstance(message, dict):
                    raise ValueError("Ollama stream message is invalid")
                content = message.get("content")
                if isinstance(content, str) and content:
                    yield ModelChunk("text", content)
                tool_calls = message.get("tool_calls", [])
                if not isinstance(tool_calls, list):
                    raise ValueError("Ollama stream tool_calls is not a list")
                for raw_call in tool_calls:
                    if not isinstance(raw_call, dict) or not isinstance(
                        raw_call.get("function"), dict
                    ):
                        raise ValueError("Ollama stream tool call is malformed")
                    function = raw_call["function"]
                    name, arguments = function.get("name"), function.get("arguments")
                    if not isinstance(name, str) or not isinstance(arguments, dict):
                        raise ValueError("Ollama stream tool call is invalid")
                    yield ModelChunk(
                        "tool_request",
                        tool_call=ToolCall(
                            f"ollama-{request.generation_id}-{call_index}", name, arguments
                        ),
                    )
                    call_index += 1
                if event.get("done") is True:
                    prompt_count = event.get("prompt_eval_count")
                    output_count = event.get("eval_count")
                    if isinstance(prompt_count, int) and isinstance(output_count, int):
                        yield ModelChunk("usage", usage_tokens=prompt_count + output_count)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if cancellation.cancelled:
                return
            primary_error = ProviderResponseInvalid(
                "provider returned invalid JSON or text encoding"
            )
        except Exception as error:
            primary_error = error
        finally:
            close = getattr(lines, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    if not cancellation.cancelled:
                        if primary_error is None:
                            raise
                        primary_error.add_note("siro: provider stream cleanup failed")
        if cancellation.cancelled:
            return
        if primary_error is not None:
            raise primary_error
        yield ModelChunk("finished")
