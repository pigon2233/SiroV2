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
from siro.adapters.models.openai_compatible import (
    _TOOL_INTENT_EMITTED,
    ProviderOutputIncomplete,
    ProviderOutputTruncated,
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


def _completion_error(reason: object) -> ProviderOutputIncomplete | None:
    if reason is None or reason == "stop":
        return None
    if reason == "length":
        return ProviderOutputTruncated(
            "provider returned no usable reply: provider output reached its limit"
        )
    return ProviderOutputIncomplete("provider output has an unsupported termination")


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
        if cancellation.cancelled:
            return
        completion_error = _completion_error(response.get("done_reason"))
        if completion_error is not None:
            raise completion_error
        # Preserve old atomic transports that omit done, but reject explicit incompletion.
        if "done" in response and response["done"] is not True:
            raise ProviderOutputIncomplete("provider output ended without completion")
        tool_calls = message.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            raise ValueError("Ollama tool_calls is not a list")
        calls: list[ToolCall] = []
        for index, raw_call in enumerate(tool_calls):
            if not isinstance(raw_call, dict) or not isinstance(raw_call.get("function"), dict):
                raise ValueError("Ollama tool call is malformed")
            function = raw_call["function"]
            name, arguments = function.get("name"), function.get("arguments")
            if not isinstance(name, str) or not isinstance(arguments, dict):
                raise ValueError("Ollama tool call has invalid name or arguments")
            calls.append(ToolCall(f"ollama-{request.generation_id}-{index}", name, arguments))
        if not (isinstance(text, str) and text) and not calls:
            raise ProviderOutputIncomplete(
                "provider returned no usable reply (no text or tool calls)"
            )
        for call in calls:
            yield ModelChunk("tool_request", tool_call=call)
            if cancellation.cancelled:
                return
        prompt_count, output_count = response.get("prompt_eval_count"), response.get("eval_count")
        if isinstance(prompt_count, int) and isinstance(output_count, int):
            yield ModelChunk("usage", usage_tokens=prompt_count + output_count)
        if cancellation.cancelled:
            return
        yield ModelChunk("finished")

    async def _stream_response(
        self,
        payload: dict[str, object],
        request: ModelRequest,
        cancellation: CancellationToken,
    ) -> AsyncIterator[ModelChunk]:
        transport = cast(StreamingJsonTransport, self._transport)
        calls: list[ToolCall] = []
        has_text = False
        done = False
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
                    has_text = True
                    yield ModelChunk("text", content)
                if cancellation.cancelled:
                    return
                completion_error = _completion_error(event.get("done_reason"))
                if completion_error is not None:
                    raise completion_error
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
                    calls.append(
                        ToolCall(f"ollama-{request.generation_id}-{len(calls)}", name, arguments)
                    )
                if event.get("done") is True:
                    done = True
                    prompt_count = event.get("prompt_eval_count")
                    output_count = event.get("eval_count")
                    if isinstance(prompt_count, int) and isinstance(output_count, int):
                        yield ModelChunk("usage", usage_tokens=prompt_count + output_count)
                    break
            if cancellation.cancelled:
                return
            if not done:
                raise ProviderOutputIncomplete("provider output ended without completion")
            if not has_text and not calls:
                raise ProviderOutputIncomplete(
                    "provider returned no usable reply (no text or tool calls)"
                )
        except (json.JSONDecodeError, UnicodeDecodeError):
            if cancellation.cancelled:
                return
            primary_error = ProviderResponseInvalid(
                "provider returned invalid JSON or text encoding"
            )
        except Exception as error:
            primary_error = error
        finally:
            if primary_error is not None and calls:
                primary_error.add_note(_TOOL_INTENT_EMITTED)
            close = getattr(lines, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception as cleanup_error:
                    if not cancellation.cancelled:
                        if primary_error is None:
                            if calls:
                                cleanup_error.add_note(_TOOL_INTENT_EMITTED)
                            raise
                        primary_error.add_note("siro: provider stream cleanup failed")
        if cancellation.cancelled:
            return
        if primary_error is not None:
            raise primary_error
        for call in calls:
            yield ModelChunk("tool_request", tool_call=call)
            if cancellation.cancelled:
                return
        yield ModelChunk("finished")
