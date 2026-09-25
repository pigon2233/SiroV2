"""Adapter for an authorized OpenAI-compatible cloud endpoint."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import cast

from siro.adapters.models.http import (
    HttpxStreamingTransport,
    JsonTransport,
    StreamingJsonTransport,
)
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall


class OpenAICompatibleAdapter:
    name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        transport: JsonTransport | StreamingJsonTransport | None = None,
        timeout: float = 120,
    ) -> None:
        if not api_key:
            raise ValueError("cloud provider API key is required")
        self._url = f"{base_url.rstrip('/')}/v1/chat/completions"
        self._key = api_key
        self._model = model
        self._transport = transport or HttpxStreamingTransport()
        self._timeout = timeout

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        if request.privacy is not Privacy.CLOUD_ALLOWED:
            raise PermissionError("cloud egress requires cloud_allowed privacy")
        if cancellation.cancelled:
            return
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_output_tokens,
            "stream": hasattr(self._transport, "stream_lines"),
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
            payload["stream_options"] = {"include_usage": True}
            async for chunk in self._stream_response(payload, cancellation):
                yield chunk
            return
        response = await self._transport.post(
            self._url,
            payload,
            {"Authorization": f"Bearer {self._key}"},
            self._timeout,
        )
        if cancellation.cancelled:
            return
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("provider response has no choices")
        first = choices[0]
        if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
            raise ValueError("provider response has no message")
        message = first["message"]
        content = message.get("content")
        if isinstance(content, str) and content:
            yield ModelChunk("text", content)
        tool_calls = message.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            raise ValueError("provider tool_calls is not a list")
        for raw_call in tool_calls:
            if not isinstance(raw_call, dict) or not isinstance(raw_call.get("function"), dict):
                raise ValueError("provider tool call is malformed")
            function = raw_call["function"]
            raw_arguments = function.get("arguments", "{}")
            if not isinstance(raw_arguments, str):
                raise ValueError("provider tool arguments are not JSON text")
            arguments = json.loads(raw_arguments)
            if not isinstance(arguments, dict):
                raise ValueError("provider tool arguments must be an object")
            call_id, name = raw_call.get("id"), function.get("name")
            if not isinstance(call_id, str) or not isinstance(name, str):
                raise ValueError("provider tool call has no id or name")
            yield ModelChunk("tool_request", tool_call=ToolCall(call_id, name, arguments))
        if not isinstance(content, str) and not tool_calls:
            raise ValueError("provider message has neither text nor tool calls")
        usage = response.get("usage")
        if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
            yield ModelChunk("usage", usage_tokens=usage["total_tokens"])
        yield ModelChunk("finished")

    async def _stream_response(
        self, payload: dict[str, object], cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        calls: dict[int, dict[str, str]] = {}
        transport = cast(StreamingJsonTransport, self._transport)
        async for line in transport.stream_lines(
            self._url,
            payload,
            {"Authorization": f"Bearer {self._key}"},
            self._timeout,
            cancellation,
        ):
            if not line or not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if not isinstance(event, dict):
                raise ValueError("provider stream event is not an object")
            usage = event.get("usage")
            if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
                yield ModelChunk("usage", usage_tokens=usage["total_tokens"])
            choices = event.get("choices", [])
            if not isinstance(choices, list):
                raise ValueError("provider stream choices is not a list")
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                if not isinstance(delta, dict):
                    continue
                content = delta.get("content")
                if isinstance(content, str) and content:
                    yield ModelChunk("text", content)
                raw_calls = delta.get("tool_calls", [])
                if not isinstance(raw_calls, list):
                    raise ValueError("provider stream tool_calls is not a list")
                for raw in raw_calls:
                    if not isinstance(raw, dict) or not isinstance(raw.get("index"), int):
                        raise ValueError("provider stream tool call is malformed")
                    call = calls.setdefault(raw["index"], {"id": "", "name": "", "args": ""})
                    if isinstance(raw.get("id"), str):
                        call["id"] += raw["id"]
                    function = raw.get("function")
                    if isinstance(function, dict):
                        if isinstance(function.get("name"), str):
                            call["name"] += function["name"]
                        if isinstance(function.get("arguments"), str):
                            call["args"] += function["arguments"]
        if cancellation.cancelled:
            return
        for index, call in sorted(calls.items()):
            arguments = json.loads(call["args"] or "{}")
            if not isinstance(arguments, dict) or not call["name"]:
                raise ValueError("provider stream tool call is incomplete")
            yield ModelChunk(
                "tool_request",
                tool_call=ToolCall(call["id"] or f"call-{index}", call["name"], arguments),
            )
        yield ModelChunk("finished")
