# ruff: noqa: RUF001
from __future__ import annotations

import pytest

from siro.ports.models import ToolDefinition
from siro.services.computer_use.intent import narrow_for_play_order, play_goal


@pytest.mark.parametrize(
    "text",
    [
        "幫我玩UNDERTALE",
        "幫我玩 Undertale",
        "你來玩遊戲",
        "開始玩Undertale",
        "去玩 Undertale",
        "請你幫我玩一下",
        "好，開始遊玩",
        "就打開undertale 然後開始遊玩",
        "麻煩幫我操控電腦",
        "繼續玩",
    ],
)
def test_clear_orders_match_and_keep_the_text_as_goal(text: str) -> None:
    assert play_goal(text) == text.strip()


@pytest.mark.parametrize(
    "text",
    [
        "我昨天玩了Undertale",
        "你會玩Undertale嗎",
        "你玩過嗎？",
        "Undertale 好玩嗎",
        "我想玩Undertale但是沒時間",
        "他在玩遊戲",
        "不要玩了",
        "別幫我玩",
        "停止遊玩",
        "不用開始玩",
        "今天天氣如何",
        "",
        "幫我玩" + "很長的描述" * 30,
    ],
)
def test_talk_questions_negations_and_noise_do_not_match(text: str) -> None:
    assert play_goal(text) is None


def test_order_narrows_the_tool_list_only_when_play_is_offered() -> None:
    schema: dict[str, object] = {"type": "object"}
    tools = tuple(
        ToolDefinition(n, "d", schema) for n in ("computer.play", "claude.ask", "browser.read")
    )
    assert [t.name for t in narrow_for_play_order("幫我玩UNDERTALE", tools)] == ["computer.play"]
    assert narrow_for_play_order("今天天氣如何", tools) == tools
    assert narrow_for_play_order("你玩過嗎？", tools) == tools
    without_play = tools[1:]
    assert narrow_for_play_order("幫我玩UNDERTALE", without_play) == without_play
