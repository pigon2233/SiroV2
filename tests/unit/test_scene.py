from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from siro.services.agent.routine import RoutineView
from siro.services.agent.scene import detect_scene

ZONE = "Asia/Taipei"


def _at(hour: int) -> datetime:
    return datetime(2026, 5, 20, hour, tzinfo=ZoneInfo(ZONE)).astimezone(UTC)


def _scene(hour: int, *, motion_ago: timedelta | None, lux: float | None, seen: bool = True) -> str:
    now = _at(hour)
    last_motion = None if motion_ago is None else now - motion_ago
    view = RoutineView(None, last_motion, lux, now if seen else None)
    return detect_scene(view, now=now, zone=ZONE)


def test_scenes() -> None:
    assert _scene(14, motion_ago=timedelta(minutes=5), lux=90) == "active"
    assert _scene(14, motion_ago=timedelta(hours=2), lux=90) == "away"
    assert _scene(14, motion_ago=timedelta(minutes=30), lux=90) == "idle"
    assert _scene(23, motion_ago=timedelta(minutes=5), lux=90) == "winding_down"
    assert _scene(2, motion_ago=timedelta(hours=3), lux=1) == "sleeping"
    assert _scene(14, motion_ago=timedelta(hours=2), lux=1) == "idle"


def test_silent_node_is_unknown() -> None:
    assert _scene(14, motion_ago=None, lux=None, seen=False) == "unknown"
