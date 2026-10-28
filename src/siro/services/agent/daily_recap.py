"""Bedtime recap: a short spoken summary of what was said and done today.

One entry point, `build_recap`, so any trigger (chat command, HTTP, a later ESP32
light-off event) calls the same thing. The summarizer is injected; without one, or when
it fails, a plain local summary is used so the recap never depends on the cloud.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from siro.persistence.sqlite import SQLiteStore

MAX_ITEMS = 40
MAX_FIELD = 160
PROMPT = (
    "你是 SIRO，要在主人睡前用溫柔簡短的口吻，用繁體中文口語說一段今天的回顧。"  # noqa: RUF001
    "只根據下面的紀錄，不要編造；最多 4 句、不超過 120 字，不要列表、不要網址，"  # noqa: RUF001
    "最後說一句晚安。\n\n今天的紀錄：\n"  # noqa: RUF001
)

Summarizer = Callable[[str], Awaitable[str]]


@dataclass(frozen=True)
class RecapItem:
    at: datetime
    goal: str
    state: str
    reply: str


def day_start(now: datetime, zone: str) -> datetime:
    local = now.astimezone(ZoneInfo(zone))
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


async def collect_today(store: SQLiteStore, now: datetime, zone: str) -> list[RecapItem]:
    first = day_start(now, zone)
    start, end = first.isoformat(), (first + timedelta(days=1)).isoformat()

    def read(c: sqlite3.Connection) -> list[RecapItem]:
        rows = c.execute(
            "SELECT r.goal, r.state, r.created_at, j.messages_json FROM agent_runs r "
            "LEFT JOIN run_journal j ON j.run_id=r.run_id "
            "WHERE r.created_at>=? AND r.created_at<? ORDER BY r.created_at DESC LIMIT ?",
            (start, end, MAX_ITEMS),
        ).fetchall()
        items: list[RecapItem] = []
        for row in reversed(rows):
            reply = ""
            try:
                messages = json.loads(row["messages_json"] or "[]")
                last = messages[-1] if messages else {}
                if last.get("role") == "assistant" and isinstance(last.get("content"), str):
                    reply = last["content"]
            except (ValueError, AttributeError, TypeError):
                pass
            items.append(
                RecapItem(
                    datetime.fromisoformat(row["created_at"]),
                    str(row["goal"]),
                    str(row["state"]),
                    reply,
                )
            )
        return items

    return await store.run_transaction(read)


def render_log(items: list[RecapItem], zone: str) -> str:
    tz = ZoneInfo(zone)
    lines = []
    for item in items:
        line = f"{item.at.astimezone(tz):%H:%M} 主人/任務：{item.goal[:MAX_FIELD]}（{item.state}）"  # noqa: RUF001
        if item.reply:
            line += f" → SIRO：{item.reply[:MAX_FIELD]}"  # noqa: RUF001
        lines.append(line.replace("\n", " "))
    return "\n".join(lines)


def local_summary(items: list[RecapItem]) -> str:
    if not items:
        return "今天我們還沒有聊什麼，早點休息，晚安。"  # noqa: RUF001
    done = sum(1 for item in items if item.state == "completed")
    return f"今天我們一起做了 {len(items)} 件事，其中 {done} 件順利完成。辛苦了，晚安。"  # noqa: RUF001


async def build_recap(
    store: SQLiteStore,
    summarize: Summarizer | None,
    *,
    now: datetime | None = None,
    zone: str = "Asia/Taipei",
) -> str:
    items = await collect_today(store, now or datetime.now(UTC), zone)
    if not items or summarize is None:
        return local_summary(items)
    try:
        text = (await summarize(PROMPT + render_log(items, zone))).strip()
    except Exception:
        return local_summary(items)
    return text[:600] or local_summary(items)


class BedtimeTrigger:
    """Fires once a night when the room has been dark for a while and someone still moves in it.

    Switching the light off and leaving never fires: that gives no motion in the dark room.
    """

    def __init__(
        self, *, dark_lux: float = 5.0, settle_seconds: float = 60.0, zone: str = "Asia/Taipei"
    ) -> None:
        self._dark_lux = dark_lux
        self._settle = timedelta(seconds=settle_seconds)
        self._zone = ZoneInfo(zone)
        self._dark_since: datetime | None = None
        self._fired_night: object = None

    def observe(self, event: str, lux: float | None, now: datetime) -> bool:
        if event == "light_update" and lux is not None:
            if lux >= self._dark_lux:
                self._dark_since = None
            elif self._dark_since is None:
                self._dark_since = now
            return False
        if event != "motion_detected" or self._dark_since is None:
            return False
        if now - self._dark_since < self._settle:
            return False
        local = now.astimezone(self._zone)
        if not (local.hour >= 21 or local.hour < 3):
            return False
        night = (local - timedelta(hours=3)).date()
        if night == self._fired_night:
            return False
        self._fired_night = night
        return True
