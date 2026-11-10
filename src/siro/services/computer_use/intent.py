# ruff: noqa: RUF001
"""Match an explicit order to play/operate the PC (not chatter about games).

Used only as a shortcut when ``computer.play`` is available: the local chat model calls tools
unreliably, so a clear command goes straight to the tool. Anything that is a question, a
negation, a past-tense remark or just talk about wanting to play is NOT matched. Two shapes
count as an order: a command form (幫我玩 / 開始玩 …) or a short message that names a program on
the owner's control allowlist together with a play verb (操控UNDERTALE、玩UNDERTALE 通關).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Sequence

from siro.ports.models import ToolDefinition
from siro.services.computer_use.perception import allowed_processes
from siro.services.computer_use.process_names import mentions_process, normalization_enabled

MAX_LENGTH = 80
_FILLER = r"(?:好[啊吧啦]?|那|就|現在|請|麻煩|你|可以|先|再|[，,、\s])*"
_ORDER = re.compile(
    rf"^{_FILLER}(?:(?:幫我|幫忙|替我|給我|來|去|開始|繼續)\s*(?:玩|遊玩|操控|操作)"
    r"|(?:打開|開啟|啟動)\s*\S+\s*(?:然後|並且|並|再)?\s*開始\s*(?:玩|遊玩))"
)
_BLOCK = re.compile(
    r"不要|不用|別|不必|不能|停止|停下|暫停|取消|嗎|呢|\?|？|沒|"
    r"玩過|打過|看過|試過|聽過|去過|想玩|想要玩|希望|可能|如果|以前|昨天|剛才|剛剛|之前|曾經|已經|了嗎"
)
_VERB = re.compile(r"玩|遊玩|操控|操作|通關|過關|打")


def names_program(stem: str, text: str) -> bool:
    """``text`` (lower-cased) mentions this program: 3+ chars, not inside a longer ASCII word."""
    if normalization_enabled():
        return mentions_process(stem,text)
    return (
        len(stem) >= 3
        and re.search(rf"(?<![a-z0-9]){re.escape(stem)}(?![a-z0-9])", text) is not None
    )


def _allowed_stems() -> list[str]:
    return [p.removesuffix(".exe") for p in sorted(allowed_processes())]


def play_goal(text: str, programs: Iterable[str] | None = None) -> str | None:
    """Return the goal to hand to computer.play when ``text`` is a clear order, else None.

    ``programs`` are program stems the owner allows (default: the allowlist from the environment).
    """
    cleaned = text.strip()
    if not cleaned or len(cleaned) > MAX_LENGTH or _BLOCK.search(cleaned):
        return None
    if _ORDER.match(cleaned):
        return cleaned
    stems = _allowed_stems() if programs is None else list(programs)
    lowered = cleaned.lower()
    if _VERB.search(cleaned) and any(names_program(stem, lowered) for stem in stems):
        return cleaned
    return None


def narrow_for_play_order(text: str, tools: Sequence[ToolDefinition]) -> tuple[ToolDefinition, ...]:
    """For a clear order to play, offer the model only ``computer.play``.

    With a dozen tools the local model often answers in plain text instead of calling one; with a
    single obvious tool it calls it (probe: 3/3 with real history). Everything else is unchanged.
    """
    play = [t for t in tools if t.name == "computer.play"]
    if play and play_goal(text) is not None:
        return (play[0],)
    return tuple(tools)


UNAVAILABLE_HINT = (
    "主人剛才明確要你操作電腦或玩遊戲，但電腦操控目前是關閉或已緊急停止，所以你現在不能操作。"
    "請簡短告訴主人：到托盤（隱藏圖示裡的「SIRO 桌寵」）點「電腦操控」開啟，之後再說一次；"
    "不要假裝已經開始，也不要說你正在操作。 [source:computer-control]"
)


def unavailable_hint(text: str, tools: Sequence[ToolDefinition]) -> str | None:
    """A context line for the model when the owner orders play but control is off/stopped.

    Only when the feature is configured at all (a token exists) and ``computer.play`` is not
    offered this turn; keyword orders only (the cloud judge is not asked for a "no").
    """
    if not os.environ.get("SIRO_COMPUTER_TOKEN") or any(t.name == "computer.play" for t in tools):
        return None
    return UNAVAILABLE_HINT if play_goal(text) is not None else None
