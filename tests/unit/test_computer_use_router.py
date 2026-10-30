from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from siro.ports.models import ToolDefinition
from siro.services.computer_use import router as router_module
from siro.services.computer_use.router import (
    PlayRouter,
    parse_verdict,
    recent_user_texts,
    route_tools,
)

SCHEMA: dict[str, object] = {"type": "object"}
TOOLS = tuple(
    ToolDefinition(n, "d", SCHEMA) for n in ("computer.play", "claude.ask", "browser.read")
)


class FakeClaude:
    """Stands in for the `claude -p` subprocess; records every prompt it was sent."""

    def __init__(self, verdict: str = '{"operate": true, "goal": "玩 Undertale"}') -> None:
        self.verdict, self.prompts, self.timeouts = verdict, [], []

    async def __call__(self, argv: tuple[str, ...], **kwargs: Any) -> dict[str, object]:
        self.prompts.append(argv[-1])
        self.timeouts.append(kwargs.get("timeout"))
        return {"returncode": 0, "stdout": json.dumps({"result": self.verdict, "is_error": False})}


@pytest.fixture(autouse=True)
def fake_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router_module, "claude_binary", lambda: Path("claude"))
    import siro.services.tools.claude as claude_module

    monkeypatch.setattr(claude_module, "claude_binary", lambda: Path("claude"))
    monkeypatch.setenv("SIRO_COMPUTER_ALLOWED_PROCESSES", "undertale.exe")
    monkeypatch.setattr(router_module, "_DEFAULT", None)


def test_parse_verdict_accepts_only_an_explicit_true() -> None:
    assert parse_verdict('ok {"operate": true, "goal": " 玩 X "}') == (True, "玩 X")
    assert parse_verdict('{"operate": true}') == (True, "")
    for bad in ('{"operate": false, "goal": "x"}', '{"operate": "yes"}', "nope", "{bad json}"):
        assert parse_verdict(bad) == (False, "")


@pytest.mark.asyncio
async def test_router_sends_only_the_short_scrubbed_message_and_recent_user_lines() -> None:
    claude = FakeClaude()
    router = PlayRouter(run=claude, enabled=True, timeout=7)
    goal = await router.decide("你自己去玩一下吧 sk-" + "a" * 24, ("幫我玩UNDERTALE",))
    assert goal == "玩 Undertale"
    prompt = claude.prompts[0]
    assert "sk-" not in prompt and "[redacted]" in prompt and "幫我玩UNDERTALE" in prompt
    assert "undertale.exe" in prompt and claude.timeouts == [7]


@pytest.mark.asyncio
async def test_router_failures_and_off_switch_mean_no() -> None:
    assert await PlayRouter(run=FakeClaude(), enabled=False).decide("玩") is None
    assert (
        await PlayRouter(run=FakeClaude('{"operate": false}'), enabled=True).decide("今天?") is None
    )

    async def broken(argv: tuple[str, ...], **kwargs: Any) -> dict[str, object]:
        return {"returncode": 1, "stdout": ""}

    assert await PlayRouter(run=broken, enabled=True).decide("你去玩遊戲吧") is None

    async def hangs(argv: tuple[str, ...], **kwargs: Any) -> dict[str, object]:
        await asyncio.sleep(30)
        return {}

    assert await PlayRouter(run=hangs, enabled=True, timeout=0.05).decide("你去玩遊戲吧") is None


@pytest.mark.asyncio
async def test_route_tools_keywords_first_then_haiku_only_when_relevant() -> None:
    claude = FakeClaude()
    judge = PlayRouter(run=claude, enabled=True)
    # a clear order never needs the cloud
    assert [t.name for t in await route_tools("幫我玩UNDERTALE", TOOLS, router=judge)] == [
        "computer.play"
    ]
    assert claude.prompts == []
    # free phrasing that looks relevant is judged by Haiku
    assert [t.name for t in await route_tools("你自己去玩一下遊戲吧", TOOLS, router=judge)] == [
        "computer.play"
    ]
    assert len(claude.prompts) == 1
    # chit-chat never leaves the machine
    assert await route_tools("今天天氣如何", TOOLS, router=judge) == TOOLS
    assert len(claude.prompts) == 1
    # a "no" verdict keeps every tool; without computer.play nothing is asked at all
    assert (
        await route_tools(
            "你自己去玩一下遊戲吧",
            TOOLS,
            router=PlayRouter(run=FakeClaude('{"operate": false}'), enabled=True),
        )
        == TOOLS
    )
    assert await route_tools("你自己去玩一下遊戲吧", TOOLS[1:], router=judge) == TOOLS[1:]
    assert len(claude.prompts) == 1


@pytest.mark.asyncio
async def test_recent_dialogue_makes_a_bare_follow_up_relevant() -> None:
    claude = FakeClaude()
    judge = PlayRouter(run=claude, enabled=True)
    assert await route_tools("然後呢", TOOLS, ("幫我玩UNDERTALE",), judge) != TOOLS
    assert await route_tools("然後呢", TOOLS, ("今天天氣",), judge) == TOOLS


def test_recent_user_texts_keeps_the_last_two_user_lines_shortened() -> None:
    class Msg:
        def __init__(self, role: str, content: str) -> None:
            self.role, self.content = role, content

    messages = [
        Msg("user", "一"),
        Msg("assistant", "x"),
        Msg("user", "二"),
        Msg("user", "三" * 200),
    ]
    out = recent_user_texts(messages)
    assert out[0] == "二" and len(out[1]) == 80 and recent_user_texts(None) == ()
