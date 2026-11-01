from __future__ import annotations

from typing import Any

import httpx
import pytest

from siro.services.computer_use.decision import (
    DecisionError,
    OllamaVisionDecider,
    make_decider,
    parse_decision,
    parse_verify,
)
from siro.services.computer_use.perception import Observation


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


@pytest.mark.asyncio
async def test_ollama_vision_decider_parses_chat_content() -> None:
    calls: list[dict[str, Any]] = []

    class Client:
        async def post(self, url: str, json: dict[str, Any]) -> httpx.Response:
            calls.append({"url": url, "json": json})
            body = {
                "message": {
                    "role": "assistant",
                    "content": (
                        '{"kind":"act","seen":"menu","action":{"kind":"click","x":10,"y":20,'
                        '"button":"left"},"expect":"open","reason":"play","confidence":0.8,'
                        '"evidence":""}'
                    ),
                }
            }
            return httpx.Response(200, json=body)

    decider = OllamaVisionDecider(client=Client(), model="gemma4:e4b", base_url="http://ollama.test")
    decision = await decider.decide("win", [], _obs())
    assert decision.kind == "act"
    assert decision.action is not None
    assert (decision.action.x, decision.action.y) == (10, 20)
    assert calls[0]["url"].endswith("/api/chat")
    assert calls[0]["json"]["think"] is False
    assert calls[0]["json"]["messages"][0]["images"] == ["AAAA"]


@pytest.mark.asyncio
async def test_ollama_timeout_soft_recovers_to_wait() -> None:
    class Client:
        async def post(self, url: str, json: dict[str, Any]) -> httpx.Response:
            raise httpx.ReadTimeout("slow")

    decider = OllamaVisionDecider(client=Client(), timeout=0.1)
    decision = await decider.decide("win", [], _obs())
    assert decision.kind == "wait"
    assert "decider_soft:ollama_timeout" in decision.reason


def test_make_decider_defaults_to_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIRO_COMPUTER_DECIDER", raising=False)
    assert type(make_decider({})).__name__ == "OllamaVisionDecider"
    assert type(make_decider({"SIRO_COMPUTER_DECIDER": "claude"})).__name__ == "ClaudeVisionDecider"


def test_parse_decision_still_accepts_wait() -> None:
    d = parse_decision('{"kind":"wait","seen":"loading","confidence":0.7}')
    assert d.kind == "wait"


def test_parse_decision_keeps_strategy_update() -> None:
    d = parse_decision(
        '{"kind":"act","seen":"map","scene":"map","energy":"n/a","targets":"elite node",'
        '"uncertainty":"","strategy":"take the elite path","action":'
        '{"kind":"click","x":1,"y":2,"button":"left"},"expect":"enter combat","reason":"r",'
        '"confidence":0.9,"evidence":""}'
    )
    assert d.strategy == "take the elite path"
    assert d.scene == "map"
    assert d.targets == "elite node"


def test_parse_decision_requires_expect_for_act() -> None:
    with pytest.raises(DecisionError, match="missing_expect"):
        parse_decision(
            '{"kind":"act","seen":"map","action":{"kind":"click","x":1,"y":2,"button":"left"},'
            '"confidence":0.9}'
        )


def test_parse_verify_statuses() -> None:
    assert parse_verify(
        '{"status":"confirmed","seen":"character select","scene":"menu","detail":"menu gone"}'
    ).status == "confirmed"
    assert parse_verify('{"status":"nope"}').status == "unknown"


def test_parse_decision_coerces_common_bad_kinds() -> None:
    d = parse_decision(
        '{"kind":"select","seen":"menu","action":{"kind":"click","x":1,"y":2,"button":"left"},'
        '"expect":"open single player","confidence":0.8}'
    )
    assert d.kind == "act"
    d2 = parse_decision('{"kind":"observe","seen":"loading","confidence":0.7}')
    assert d2.kind == "wait"


@pytest.mark.asyncio
async def test_ollama_soft_recovers_persistent_bad_kind() -> None:
    class Client:
        async def post(self, url: str, json: dict[str, Any]) -> httpx.Response:
            body = {"message": {"role": "assistant", "content": '{"kind":"nope","confidence":0.5}'}}
            return httpx.Response(200, json=body)

    decider = OllamaVisionDecider(client=Client(), model="gemma4:e4b", base_url="http://ollama.test")
    decision = await decider.decide("win", [], _obs())
    assert decision.kind == "wait"
    assert "decider_soft" in decision.reason
