# ruff: noqa: RUF001
from __future__ import annotations

import pytest

from siro.ports.models import ToolDefinition
from siro.services.computer_use.intent import narrow_for_play_order, play_goal, unavailable_hint


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


@pytest.mark.parametrize(
    "text",
    [
        "操控UNDERTALE 並自己判斷該做甚麼",
        "玩UNDERTALE 通關",
        "幫我玩UNDERTALE 目標是過關",
        "UNDERTALE 通關",
    ],
)
def test_messages_naming_an_allowed_program_with_a_play_verb_match(text: str) -> None:
    assert play_goal(text, programs=["undertale"]) == text


@pytest.mark.parametrize(
    "text",
    [
        "通關",  # no program named: the model has to decide from context
        "我想玩UNDERTALE",
        "我昨天玩過UNDERTALE",
        "UNDERTALE 好玩嗎",
        "我剛剛打了UNDERTALE",
        "不要玩UNDERTALE",
        "別操控UNDERTALE",
        "我在玩別的遊戲",
    ],
)
def test_talk_about_the_program_or_other_games_does_not_match(text: str) -> None:
    assert play_goal(text, programs=["undertale"]) is None


def test_default_programs_come_from_the_environment_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_ALLOWED_PROCESSES", "undertale.exe")
    assert play_goal("操控UNDERTALE") == "操控UNDERTALE"
    monkeypatch.setenv("SIRO_COMPUTER_ALLOWED_PROCESSES", "")
    assert play_goal("操控UNDERTALE") is None


def test_unavailable_hint_only_for_orders_when_configured_and_play_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema: dict[str, object] = {"type": "object"}
    others = (ToolDefinition("claude.ask", "d", schema),)
    with_play = (*others, ToolDefinition("computer.play", "d", schema))
    monkeypatch.setenv("SIRO_COMPUTER_TOKEN", "t" * 40)
    hint = unavailable_hint("幫我玩UNDERTALE", others)
    assert hint is not None and "托盤" in hint and "[source:computer-control]" in hint
    assert unavailable_hint("幫我玩UNDERTALE", with_play) is None
    assert unavailable_hint("今天天氣如何", others) is None
    assert unavailable_hint("你會玩Undertale嗎？", others) is None
    monkeypatch.delenv("SIRO_COMPUTER_TOKEN")
    assert unavailable_hint("幫我玩UNDERTALE", others) is None
