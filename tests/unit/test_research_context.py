"""Owner report 2026-10-30: SIRO's own research only enters turns that ask about it."""

from __future__ import annotations

import pytest

from siro.core.context import asks_about_research


@pytest.mark.parametrize(
    "text", ["你最近查了什麼", "上次研究的結果呢", "把你看過的論文給我", "what did you look up"]
)
def test_research_questions_bring_her_research_back(text: str) -> None:
    assert asks_about_research(text)


@pytest.mark.parametrize(
    "text", ["操控UNDERTALE 並自己判斷該做甚麼", "通關", "成功了嗎", "早安", "打開 undertale"]
)
def test_commands_and_chat_do_not_carry_her_research(text: str) -> None:
    assert not asks_about_research(text)
