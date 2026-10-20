"""Touches on the desktop character: when one gets a short spoken line, and what it says.

The renderer reports a pat on the head, a burst of pokes or being carried by the window
(``body.touch``). The animation already answers every touch; speech is rare on top of it, never
over another reply, and bounded per day so it never turns into chatter.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from siro.config import ProactivitySettings

TOUCH_KINDS = ("pat", "poke", "carry")
# A slow line is worse than none: past this the reply falls back to a short ready-made line.
TOUCH_REPLY_SECONDS = 6.0
TOUCH_REPLY_TOKENS = 60
# Touches stay in her conversation context this long.
TOUCH_MEMORY = timedelta(minutes=10)

_TEMPLATES = {
    "pat": ("嘿嘿，好舒服。", "被摸頭了，好開心。", "再摸一下也可以喔。"),  # noqa: RUF001
    "poke": ("欸，幹嘛戳我啦。", "好癢，別戳了啦。", "我在這裡，怎麼了嗎？"),  # noqa: RUF001
    "carry": ("哇，要帶我去哪裡？", "新位置不錯耶。", "嚇我一跳，好了好了。"),  # noqa: RUF001
}
_PROSODY = {
    "pat": {"rate": 1.0, "pitch": 0.05, "energy": 0.55},
    "poke": {"rate": 1.05, "pitch": 0.06, "energy": 0.7},
    "carry": {"rate": 1.05, "pitch": 0.08, "energy": 0.65},
}


@dataclass(frozen=True, slots=True)
class TouchChoice:
    speak: bool
    reason: str


@dataclass(frozen=True, slots=True)
class Touch:
    kind: str
    count: int
    at: datetime
    reply: str | None = None


class TouchReplies:
    """Deterministic rules for whether a touch gets a spoken line."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        timezone: str = ProactivitySettings().timezone,
        gap: timedelta = timedelta(seconds=60),
        repeat: dict[str, timedelta] | None = None,
        daily_limit: int = 15,
    ) -> None:
        self._enabled = enabled
        self._zone = ZoneInfo(timezone)
        self._gap = gap
        # Moving the window is often just tidying the desktop: carried rarely gets a word.
        self._repeat = repeat or {
            "pat": timedelta(minutes=3),
            "poke": timedelta(minutes=3),
            "carry": timedelta(minutes=10),
        }
        self._daily_limit = daily_limit
        self._last: datetime | None = None
        self._last_kind: dict[str, datetime] = {}
        self._count: dict[str, int] = {}

    def choose(self, kind: str, now: datetime, *, busy: bool) -> TouchChoice:
        if not self._enabled:
            return TouchChoice(False, "disabled_by_user")
        if busy:
            return TouchChoice(False, "busy")
        if self._count.get(self._day(now), 0) >= self._daily_limit:
            return TouchChoice(False, "daily_limit")
        if self._last is not None and now - self._last < self._gap:
            return TouchChoice(False, "cooldown")
        last = self._last_kind.get(kind)
        if last is not None and now - last < self._repeat[kind]:
            return TouchChoice(False, "repeat_cooldown")
        return TouchChoice(True, "allowed")

    def spoke(self, kind: str, at: datetime) -> None:
        self._last = at
        self._last_kind[kind] = at
        day = self._day(at)
        self._count = {day: self._count.get(day, 0) + 1}

    def _day(self, now: datetime) -> str:
        return now.astimezone(self._zone).date().isoformat()


class TouchMemory:
    """The last few touches, so her next reply in the conversation knows about them."""

    def __init__(self, size: int = 3) -> None:
        self._touches: deque[Touch] = deque(maxlen=size)

    def add(self, touch: Touch) -> None:
        self._touches.append(touch)

    def context(self, now: datetime, zone: ZoneInfo) -> str | None:
        recent = [touch for touch in self._touches if now - touch.at < TOUCH_MEMORY]
        if not recent:
            return None
        parts = []
        for touch in recent:
            local = touch.at.astimezone(zone).strftime("%H:%M")
            part = f"{_ENGLISH[touch.kind](touch.count)} at {local}"
            if touch.reply:
                part += f" (SIRO said: {touch.reply})"
            parts.append(part)
        return (
            "The owner touched SIRO's character on the desktop recently: "
            + "; ".join(parts)
            + ". Mention it only if it fits. [source:body-touch]"
        )


_ENGLISH = {
    "pat": lambda _count: "patted her head",
    "poke": lambda count: f"poked her {count} times",
    "carry": lambda _count: "picked her up and moved her across the screen",
}


def touch_prompt(kind: str, count: int, now: datetime, zone: ZoneInfo) -> str:
    """A one-line ask for the local model: a short spoken reaction in her own voice."""

    what = {
        "pat": "輕輕摸了摸你的頭",
        "poke": f"連續戳了你{count}下",
        "carry": "把你拎起來，移到螢幕上別的地方放下",  # noqa: RUF001
    }[kind]
    if kind == "poke" and count >= 4:
        what += "，戳得有點多，你假裝有點不耐煩，但不是真的生氣"  # noqa: RUF001
    local = now.astimezone(zone)
    return (
        "你是希洛（SIRO），住在主人電腦桌面上的數位夥伴，個性溫暖、有點俏皮。"  # noqa: RUF001
        f"現在是{local.hour}點{local.minute:02d}分，主人剛剛{what}。"  # noqa: RUF001
        "用一句繁體中文口語回應主人，大約十個字，最多二十個字。"  # noqa: RUF001
        "只輸出那一句話本身：不要引號、表情符號、動作描寫、括號或解釋。"  # noqa: RUF001
    )


_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿️]")
_BRACKETED = re.compile(r"[（(\[【*][^）)\]】*]*[）)\]】*]")  # noqa: RUF001


def clean_touch_line(text: str) -> str | None:
    """The model's line as something she can say, or None when it is not one short sentence."""

    line = _BRACKETED.sub("", _EMOJI.sub("", text)).strip()
    line = line.strip(" \"'「」『』“”‘’")  # noqa: RUF001
    line = line.splitlines()[0].strip() if line else ""
    match = re.match(r"^(.+?[。！？!?～~])", line)  # noqa: RUF001
    if match:
        line = match.group(1)
    if not line or len(line) > 24 or re.search(r"[A-Za-z]{4,}", line):
        return None
    return line


def touch_template(kind: str, spoken: int) -> str:
    lines = _TEMPLATES[kind]
    return lines[spoken % len(lines)]


def touch_prosody(kind: str) -> dict[str, float]:
    return dict(_PROSODY[kind])
