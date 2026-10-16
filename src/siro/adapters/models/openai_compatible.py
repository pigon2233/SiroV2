"""Adapter for an authorized OpenAI-compatible cloud endpoint."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import cast

from siro.adapters.models.http import (
    HttpxStreamingTransport,
    JsonTransport,
    StreamingJsonTransport,
    _decode_json_response,
)
from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
)


def _serialize_message(message: ModelMessage) -> dict[str, object]:
    serialized: dict[str, object] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        serialized["tool_calls"] = [
            {
                "id": call.call_id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        serialized["tool_call_id"] = message.tool_call_id
    return serialized


_TOOL_INTENT_EMITTED = "siro: provider tool intent emitted"


class ProviderOutputIncomplete(ValueError):
    """A provider did not confirm a complete supported output."""


class ProviderOutputTruncated(ProviderOutputIncomplete):
    """The provider exhausted its output limit."""


class ProviderOutputFiltered(ProviderOutputIncomplete):
    """The provider filtered its output instead of completing it."""


def _completion_error(reason: object) -> ProviderOutputIncomplete | None:
    if reason is None or reason in ("stop", "tool_calls"):
        return None
    if reason == "length":
        return ProviderOutputTruncated(
            "provider returned no usable reply: provider output reached its limit"
        )
    if reason == "content_filter":
        return ProviderOutputFiltered(
            "provider returned no usable reply: provider output was filtered"
        )
    return ProviderOutputIncomplete("provider output has an unsupported termination")


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

    def request_payload(self, request: ModelRequest) -> dict[str, object]:
        """Use one serializer for preflight measurement and provider dispatch."""
        payload: dict[str, object] = {
            "model": self._model,
            "messages": (
                [_serialize_message(message) for message in request.messages]
                if request.messages
                else [{"role": "user", "content": request.prompt}]
            ),
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
        return payload

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        if request.privacy is not Privacy.CLOUD_ALLOWED:
            raise PermissionError("cloud egress requires cloud_allowed privacy")
        if cancellation.cancelled:
            return
        payload = self.request_payload(request)
        if hasattr(self._transport, "stream_lines"):
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
        if cancellation.cancelled:
            return
        tool_calls = message.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            raise ValueError("provider tool_calls is not a list")
        completion_error = _completion_error(first.get("finish_reason"))
        if completion_error is not None:
            raise completion_error
        if not (isinstance(content, str) and content) and not tool_calls:
            raise ValueError("provider returned no usable reply (no text or tool calls)")
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
            if cancellation.cancelled:
                return
        usage = response.get("usage")
        if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
            yield ModelChunk("usage", usage_tokens=usage["total_tokens"])
            if cancellation.cancelled:
                return
        yield ModelChunk("finished")

    async def _stream_response(
        self, payload: dict[str, object], cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        calls: dict[int, dict[str, str]] = {}
        has_text = False
        done_marker = False
        successful_reason = False
        completion_error: ProviderOutputIncomplete | None = None
        primary_error: Exception | None = None
        transport = cast(StreamingJsonTransport, self._transport)
        lines = transport.stream_lines(
            self._url,
            payload,
            {"Authorization": f"Bearer {self._key}"},
            self._timeout,
            cancellation,
        )
        try:
            async for line in lines:
                if cancellation.cancelled:
                    return
                if not line or not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    done_marker = True
                    break
                event = _decode_json_response(data)
                if not isinstance(event, dict):
                    raise ValueError("provider stream event is not an object")
                usage = event.get("usage")
                if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
                    yield ModelChunk("usage", usage_tokens=usage["total_tokens"])
                    if cancellation.cancelled:
                        return
                choices = event.get("choices", [])
                if not isinstance(choices, list):
                    raise ValueError("provider stream choices is not a list")
                for choice in choices:
                    if not isinstance(choice, dict):
                        continue
                    reason = choice.get("finish_reason")
                    if reason is not None:
                        successful_reason |= reason in ("stop", "tool_calls")
                        completion_error = completion_error or _completion_error(reason)
                    delta = choice.get("delta")
                    if not isinstance(delta, dict):
                        continue
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        has_text = True
                        yield ModelChunk("text", content)
                        if cancellation.cancelled:
                            return
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
                if completion_error is not None and (has_text or calls):
                    raise completion_error
            if cancellation.cancelled:
                return
            if completion_error is not None:
                raise completion_error
            if not has_text and not calls:
                raise ValueError("provider returned no usable reply (no text or tool calls)")
            if not (done_marker or successful_reason):
                raise ProviderOutputIncomplete("provider output ended without completion")
        except Exception as error:
            if cancellation.cancelled:
                return
            primary_error = error
            if calls:
                error.add_note(_TOOL_INTENT_EMITTED)
            raise
        finally:
            close = getattr(lines, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception as cleanup_error:
                    if cancellation.cancelled:
                        return
                    if primary_error is None:
                        if calls:
                            cleanup_error.add_note(_TOOL_INTENT_EMITTED)
                        raise
                    primary_error.add_note("siro: provider stream cleanup failed")
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
            if cancellation.cancelled:
                return
        yield ModelChunk("finished")
