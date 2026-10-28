"""Scenes: a coarse name for what the room is doing now (sleeping, active, away, ...).

Information only: no device is commanded. A scene colours SIRO's own judgement (it is added to
the facts of sensor triggers) and is the input a later actuator stage may use.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from siro.services.agent.routine import (
    ALIVE_WITHIN,
    DARK_LUX,
    DAY_START_HOUR,
    LATE_ACTIVE_WITHIN,
    RoutineView,
)

AWAY_AFTER = timedelta(minutes=45)
WIND_DOWN = 90  # minutes before the usual bedtime
SCENES = ("unknown", "sleeping", "winding_down", "active", "idle", "away")


def detect_scene(view: RoutineView, *, now: datetime, zone: str) -> str:
    if view.last_seen is None or now - view.last_seen > ALIVE_WITHIN:
        return "unknown"  # a silent node says nothing about the room
    tz = ZoneInfo(zone)
    shifted = now.astimezone(tz) - timedelta(hours=DAY_START_HOUR)
    minute = shifted.hour * 60 + shifted.minute
    dark = view.last_lux is not None and view.last_lux <= DARK_LUX
    quiet_for = None if view.last_motion is None else now - view.last_motion
    recent = quiet_for is not None and quiet_for <= LATE_ACTIVE_WITHIN
    bed = view.profile.bed_minute if view.profile else 19 * 60  # 23:00 until history exists
    if dark and not recent and minute >= bed - WIND_DOWN:
        return "sleeping"
    if recent:
        return "winding_down" if minute >= bed - WIND_DOWN else "active"
    if quiet_for is None or quiet_for >= AWAY_AFTER:
        return "away" if not dark else "idle"
    return "idle"
