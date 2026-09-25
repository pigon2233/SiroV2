"""Adapter for a local Ollama HTTP backend."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import cast

from siro.adapters.models.http import (
    HttpxStreamingTransport,
    JsonTransport,
    StreamingJsonTransport,
)
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, ToolCall


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
            "messages": [{"role": "user", "content": request.prompt}],
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
        response = await self._transport.post(
            self._url,
            payload,
            {},
            self._timeout,
        )
        if cancellation.cancelled:
            return
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
        async for line in transport.stream_lines(
            self._url, payload, {}, self._timeout, cancellation
        ):
            if not line:
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("Ollama stream event is not an object")
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
                if not isinstance(raw_call, dict) or not isinstance(raw_call.get("function"), dict):
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
        if not cancellation.cancelled:
            yield ModelChunk("finished")
