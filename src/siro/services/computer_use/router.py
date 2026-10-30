# ruff: noqa: RUF001
"""Haiku as a tool judge: is this message an order to operate the PC or play a game?

Keyword matching (intent.py) catches clear orders; this covers free phrasing ("你自己去玩一下吧")
without making a cloud model her brain. Only the user's short message and the last two user
messages are sent (scrubbed of secret-looking text), never her persona, memories or screen. It runs
only while ``computer.play`` is offered (control switched on) and the message looks relevant.
Any failure or timeout means "no": chat then continues on the local model unchanged.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import Any

from siro.ports.models import ToolDefinition
from siro.services.computer_use.intent import narrow_for_play_order
from siro.services.computer_use.perception import _SECRET, allowed_processes
from siro.services.tools.claude import ClaudeUnavailable, ask_claude, claude_binary
from siro.services.tools.execution import execute_bounded_argv

ROUTER_FLAG = "SIRO_COMPUTER_ROUTER"  # "0" turns the cloud judge off
MAX_TEXT = 120
RECENT_USER_MESSAGES = 2
RECENT_CHARS = 80
CALL_TIMEOUT = 15.0
_RELEVANT = re.compile(
    r"玩|操控|操作|遊戲|游戲|通關|過關|電腦|螢幕|畫面|點|按|打開|開啟|啟動|繼續|game|play|click",
    re.I,
)
PROMPT = (
    "你是桌面寵物 SIRO 的「工具判斷員」。使用者對 SIRO 說了一句話。判斷他是不是在要求 SIRO "
    "操作這台電腦或玩遊戲（SIRO 會看螢幕並用鍵盤滑鼠執行，例如「幫我玩 Undertale」「你自己操控"
    "遊戲去通關」「繼續玩」「去點那個按鈕」）。閒聊、詢問、談論遊戲、過去的事、只是想玩但沒要"
    "SIRO 做、否定句，都不是。可操作的程式：{programs}。\n"
    "最近的使用者訊息（舊到新）：{recent}\n使用者現在說：{text}\n"
    '只回 JSON，不要多餘文字：{{"operate": true 或 false, "goal": "一句話目標，不是就空字串"}}'
)
Runner = Callable[..., Awaitable[dict[str, object]]]


def recent_user_texts(messages: Iterable[Any] | None) -> tuple[str, ...]:
    """Last few user lines from the restored dialogue (ModelMessage-like), shortened."""
    users = [str(m.content)[:RECENT_CHARS] for m in (messages or ()) if m.role == "user"]
    return tuple(users[-RECENT_USER_MESSAGES:])


def _scrub(text: str) -> str:
    return _SECRET.sub("[redacted]", " ".join(text.split()))


def parse_verdict(answer: str) -> tuple[bool, str]:
    match = re.search(r"\{.*\}", answer, re.DOTALL)
    try:
        raw = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        raw = None
    if not isinstance(raw, dict) or raw.get("operate") is not True:
        return False, ""
    goal = raw.get("goal")
    return True, goal.strip()[:300] if isinstance(goal, str) else ""


class PlayRouter:
    def __init__(
        self,
        *,
        run: Runner = execute_bounded_argv,
        model: str | None = None,
        enabled: bool | None = None,
        timeout: float = CALL_TIMEOUT,
    ) -> None:
        flag = os.environ.get(ROUTER_FLAG, "1") != "0"
        self._enabled = flag if enabled is None else enabled
        self._run = run
        self._model = model
        self._timeout = timeout

    async def decide(self, text: str, recent_user: Sequence[str] = ()) -> str | None:
        """The goal when Haiku judges the message an operate/play order, else None."""
        if not self._enabled:
            return None
        prompt = PROMPT.format(
            programs=", ".join(sorted(allowed_processes())) or "(未設定)",
            recent=" | ".join(_scrub(t) for t in recent_user) or "(無)",
            text=_scrub(text)[:MAX_TEXT],
        )

        async def bounded(argv: tuple[str, ...], **kwargs: Any) -> dict[str, object]:
            kwargs["timeout"] = self._timeout
            return await self._run(argv, **kwargs)

        options: dict[str, Any] = {"search": False, "prefix": "", "limit": 2000, "run": bounded}
        if self._model:
            options["model"] = self._model
        try:
            answer = await asyncio.wait_for(
                ask_claude({"task": prompt}, **options), timeout=self._timeout + 5
            )
        except (ClaudeUnavailable, ValueError, OSError, TimeoutError):
            return None
        operate, goal = parse_verdict(str(answer.get("answer", "")))
        return (goal or text.strip()) if operate else None


_DEFAULT: PlayRouter | None = None


def default_router() -> PlayRouter | None:
    global _DEFAULT
    if _DEFAULT is None and claude_binary() is not None:
        _DEFAULT = PlayRouter()
    return _DEFAULT


def _worth_asking(text: str, recent_user: Sequence[str]) -> bool:
    if not text.strip() or len(text) > MAX_TEXT:
        return False
    return bool(_RELEVANT.search(text)) or any(_RELEVANT.search(t) for t in recent_user)


async def route_tools(
    text: str,
    tools: Sequence[ToolDefinition],
    recent_user: Sequence[str] = (),
    router: PlayRouter | None = None,
) -> tuple[ToolDefinition, ...]:
    """Offer only ``computer.play`` for an order to play (keywords, then Haiku for free talk)."""
    narrowed = narrow_for_play_order(text, tools)
    if narrowed != tuple(tools):
        return narrowed
    play = [t for t in tools if t.name == "computer.play"]
    if not play or not _worth_asking(text, recent_user):
        return tuple(tools)
    judge = router or default_router()
    if judge is None or await judge.decide(text, recent_user) is None:
        return tuple(tools)
    return (play[0],)
