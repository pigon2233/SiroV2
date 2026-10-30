# ruff: noqa: RUF001
"""Strict match for an explicit order to play/operate the PC (not for chatter about games).

Used only as a shortcut when ``computer.play`` is available: the local chat model calls tools
unreliably, so a clear command goes straight to the tool. Anything that is a question, a
negation, a past-tense remark or just talk about wanting to play is NOT matched.
"""

from __future__ import annotations

import re

MAX_LENGTH = 80
_FILLER = r"(?:好[啊吧啦]?|那|就|現在|請|麻煩|你|可以|先|再|[，,、\s])*"
_ORDER = re.compile(
    rf"^{_FILLER}(?:(?:幫我|幫忙|替我|給我|來|去|開始|繼續)\s*(?:玩|遊玩|操控|操作)"
    r"|(?:打開|開啟|啟動)\s*\S+\s*(?:然後|並且|並|再)?\s*開始\s*(?:玩|遊玩))"
)
_BLOCK = re.compile(r"不要|不用|別|不必|不能|停止|停下|暫停|取消|嗎|呢|\?|？|了嗎|過|沒")


def play_goal(text: str) -> str | None:
    """Return the goal to hand to computer.play when ``text`` is a clear order, else None."""
    cleaned = text.strip()
    if not cleaned or len(cleaned) > MAX_LENGTH or _BLOCK.search(cleaned):
        return None
    return cleaned if _ORDER.match(cleaned) else None
