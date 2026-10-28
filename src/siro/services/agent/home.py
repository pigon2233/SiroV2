"""Is the owner home? Fuses room motion, light and recent conversation into one coarse answer.

A silent sensor never proves absence; a recent conversation outranks a quiet room (the owner may
be at the desk without moving, or talking from elsewhere through the app).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.routine import ALIVE_WITHIN, DARK_LUX, RoutineView

CHATTED_WITHIN = timedelta(minutes=15)
MOTION_WITHIN = timedelta(minutes=45)
AWAY_AFTER = timedelta(hours=2)


def judge_home(view: RoutineView, *, last_chat: datetime | None, now: datetime) -> tuple[str, str]:
    """(`home`|`away`|`unknown`, why)."""

    if last_chat is not None and now - last_chat <= CHATTED_WITHIN:
        return "home", "recent_chat"
    if view.last_seen is None or now - view.last_seen > ALIVE_WITHIN:
        return "unknown", "sensor_silent"
    if view.last_motion is not None and now - view.last_motion <= MOTION_WITHIN:
        return "home", "recent_motion"
    if view.last_lux is not None and view.last_lux <= DARK_LUX:
        return "home", "dark_room"  # lights off and quiet reads as asleep, not as gone
    quiet = None if view.last_motion is None else now - view.last_motion
    if quiet is not None and quiet >= AWAY_AFTER:
        return "away", "no_motion_in_lit_room"
    return "unknown", "inconclusive"


async def last_chat_at(store: SQLiteStore) -> datetime | None:
    def read(c: sqlite3.Connection) -> datetime | None:
        row = c.execute("SELECT MAX(created_at) AS at FROM agent_runs").fetchone()
        return datetime.fromisoformat(row["at"]) if row and row["at"] else None

    return await store.run_transaction(read)
