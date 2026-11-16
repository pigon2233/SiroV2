"""P0-6: chat and speech-recognition latency is logged in one structured line per turn."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator

import pytest

from siro.adapters.models.ollama import OllamaAdapter
from siro.core.conversation import ConversationEngine, TurnResult, model_route_label
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest


class _Repository:
    async def start_turn(self, *args: object) -> None:
        return None

    async def finish_turn(self, result: TurnResult) -> None:
        return None


class _SlowFirstToken:
    name = "router"
    last_model_name = "ollama:qwen3:4b"

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        await asyncio.sleep(0.05)
        yield ModelChunk("text", "你好")
        yield ModelChunk("text", "呀")
        yield ModelChunk("finished")


@pytest.mark.asyncio
async def test_chat_reply_logs_first_delta_total_and_served_route(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = ConversationEngine(_SlowFirstToken(), _Repository())
    with caplog.at_level(logging.INFO, logger="siro.core.conversation"):
        result = await engine.respond("s", "siro", "hi")
    assert result.text == "你好呀"
    [line] = [r.getMessage() for r in caplog.records if r.getMessage().startswith("chat reply")]
    assert "route=ollama:qwen3:4b" in line and "state=completed" in line
    first = float(re.search(r"first_delta_seconds=([\d.]+)", line).group(1))  # type: ignore[union-attr]
    total = float(re.search(r"total_seconds=([\d.]+)", line).group(1))  # type: ignore[union-attr]
    assert 0.04 <= first <= total
    assert "chars=3" in line and "tool_calls=0" in line


def test_route_label_prefers_the_provider_that_served() -> None:
    assert model_route_label(OllamaAdapter(model="qwen3:4b")) == "ollama:qwen3:4b"

    class Plain:
        name = "mock"

    assert model_route_label(Plain()) == "mock"
    assert model_route_label(object()) == "object"


class _Transport:
    async def stream_lines(self, *args: object) -> AsyncIterator[str]:
        yield '{"message":{"content":"hi"},"done":false}'
        yield (
            '{"message":{"content":""},"done":true,"done_reason":"stop",'
            '"prompt_eval_count":42,"prompt_eval_duration":1500000000,'
            '"load_duration":10000000,"eval_count":3,"total_duration":2000000000}'
        )


@pytest.mark.asyncio
async def test_ollama_logs_prompt_eval_count_for_prefix_cache_checks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter = OllamaAdapter(model="qwen3:4b", transport=_Transport())  # type: ignore[arg-type]
    with caplog.at_level(logging.INFO, logger="siro.adapters.models.ollama"):
        chunks = [
            chunk async for chunk in adapter.stream(ModelRequest("hi", "g"), CancellationToken())
        ]
    assert chunks[0].text == "hi"
    [line] = [r.getMessage() for r in caplog.records]
    assert "model=qwen3:4b prompt_eval_count=42 prompt_eval_seconds=1.50" in line
    assert "load_seconds=0.01 eval_count=3 total_seconds=2.00" in line
