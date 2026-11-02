from __future__ import annotations

from typing import Any

import httpx
import pytest

from siro.services.computer_use.decision import (
    GroqVisionDecider,
    make_decider,
)
from siro.services.computer_use.perception import Observation

CLOUD = {"SIRO_COMPUTER_CLOUD_SCREEN": "1"}


def _obs() -> Observation:
    return Observation(
        seq=1,
        taken_at=0.0,
        window_title="Game",
        process="game.exe",
        window_rect=(0, 0, 800, 600),
        screen=(800, 600),
        fingerprint="menu",
        image_png_b64="AAAA",
        image_size=(800, 600),
        image_rect=(0, 0, 800, 600),
        window_id="1",
        pid=1,
    )


class _Client:
    def __init__(self, status: int = 200, content: str | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.status = status
        self.content = content

    async def post(self, url: str, json: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        self.calls.append({"url": url, "json": json, "headers": headers})
        body = {"choices": [{"message": {"role": "assistant", "content": self.content}}]}
        return httpx.Response(self.status, json=body)


@pytest.mark.asyncio
async def test_groq_vision_decider_sends_openai_image_and_parses() -> None:
    client = _Client(
        content=(
            '{"kind":"act","seen":"menu","action":{"kind":"click","x":10,"y":20,'
            '"button":"left"},"expect":"open","reason":"play","confidence":0.8,'
            '"evidence":""}'
        )
    )
    decider = GroqVisionDecider(
        client=client, api_key="k", base_url="https://groq.test/openai", env=dict(CLOUD)
    )
    decision = await decider.decide("win", [], _obs())
    assert decision.action is not None
    assert (decision.action.x, decision.action.y) == (10, 20)
    call = client.calls[0]
    assert call["url"] == "https://groq.test/openai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer k"
    assert call["json"]["model"] == "qwen/qwen3.8-27b"
    assert call["json"]["response_format"] == {"type": "json_object"}
    parts = call["json"]["messages"][0]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_groq_server_error_soft_recovers_to_wait() -> None:
    client = _Client(status=500)
    decider = GroqVisionDecider(client=client, api_key="k", env=dict(CLOUD))
    decision = await decider.decide("win", [], _obs())
    assert decision.kind == "wait"
    assert len(client.calls) == 2


def test_make_decider_selects_groq() -> None:
    decider = make_decider({"SIRO_COMPUTER_DECIDER": "groq", "SIRO_OPENAI_API_KEY": "k"})
    assert isinstance(decider, GroqVisionDecider)
