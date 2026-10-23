"""Native thinking mode, bounded context and reasoning isolation at the provider boundary."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from siro.adapters.models.ollama import OllamaAdapter
from siro.adapters.models.openai_compatible import ProviderOutputIncomplete
from siro.ports.models import CancellationToken, ModelRequest


class Transport:
    def __init__(self) -> None:
        self.payload: dict[str, object] = {}

    async def post(
        self, url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
    ) -> dict[str, object]:
        self.payload = payload
        return {
            "message": {"content": "synthetic answer", "thinking": "must not enter answer"},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 20,
        }


@pytest.mark.asyncio
async def test_native_mode_is_not_forced_off() -> None:
    transport = Transport()
    chunks = [
        chunk
        async for chunk in OllamaAdapter(model="synthetic", transport=transport).stream(
            ModelRequest("synthetic", "g"), CancellationToken()
        )
    ]
    assert "think" not in transport.payload
    assert [chunk.text for chunk in chunks if chunk.kind == "text"] == ["synthetic answer"]


@pytest.mark.asyncio
@pytest.mark.parametrize("thinking", [True, False])
async def test_explicit_mode_and_context_never_raise_request_output_budget(thinking: bool) -> None:
    transport = Transport()
    chunks = [
        chunk
        async for chunk in OllamaAdapter(
            model="synthetic", transport=transport, thinking=thinking, context_length=8192
        ).stream(ModelRequest("synthetic", "g", max_output_tokens=123), CancellationToken())
    ]
    assert transport.payload["think"] is thinking
    assert transport.payload["options"] == {"num_predict": 123, "num_ctx": 8192}
    assert [chunk.usage_tokens for chunk in chunks if chunk.kind == "usage"] == [30]
    assert [chunk.text for chunk in chunks if chunk.kind == "text"] == ["synthetic answer"]


@pytest.mark.parametrize("value", [True, 511, 32769, 4096.5, "8192"])
def test_invalid_context_is_rejected(value: Any) -> None:
    with pytest.raises(ValueError):
        OllamaAdapter(model="synthetic", context_length=value)


@pytest.mark.parametrize("value", [0, 1, "true"])
def test_thinking_requires_actual_boolean(value: Any) -> None:
    with pytest.raises(ValueError):
        OllamaAdapter(model="synthetic", thinking=value)


@pytest.mark.asyncio
async def test_cancel_during_reasoning_never_releases_late_answer_or_tool() -> None:
    class Stream:
        async def stream_lines(
            self,
            url: str,
            payload: dict[str, object],
            headers: dict[str, str],
            timeout: float,
            cancellation: CancellationToken,
        ) -> AsyncIterator[str]:
            yield json.dumps({"message": {"thinking": "synthetic internal step"}})
            cancellation.cancel()
            yield json.dumps(
                {
                    "message": {
                        "content": "late answer",
                        "tool_calls": [{"function": {"name": "must-not-run", "arguments": {}}}],
                    },
                    "done": True,
                }
            )

    chunks = [
        chunk
        async for chunk in OllamaAdapter(
            model="synthetic", transport=Stream(), thinking=True
        ).stream(ModelRequest("synthetic", "g"), CancellationToken())
    ]
    assert chunks == []


@pytest.mark.asyncio
async def test_reasoning_without_answer_cannot_count_as_completion() -> None:
    class ThinkingOnly(Transport):
        async def post(
            self, url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
        ) -> dict[str, object]:
            return {"message": {"thinking": "synthetic internal step"}, "done": True}

    with pytest.raises(ProviderOutputIncomplete):
        _ = [
            chunk
            async for chunk in OllamaAdapter(
                model="synthetic", transport=ThinkingOnly(), thinking=True
            ).stream(ModelRequest("synthetic", "g"), CancellationToken())
        ]
