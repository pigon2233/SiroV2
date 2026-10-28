from __future__ import annotations

from datetime import UTC, datetime, timedelta

from siro.services.agent.home import judge_home
from siro.services.agent.routine import RoutineView

NOW = datetime(2026, 5, 20, 14, tzinfo=UTC)


def _view(motion_ago: timedelta | None, lux: float | None, seen: bool = True) -> RoutineView:
    return RoutineView(
        None, None if motion_ago is None else NOW - motion_ago, lux, NOW if seen else None
    )


def test_fusion() -> None:
    chat = NOW - timedelta(minutes=3)
    assert judge_home(_view(timedelta(hours=5), 90), last_chat=chat, now=NOW)[0] == "home"
    assert judge_home(_view(timedelta(hours=5), 90, seen=False), last_chat=None, now=NOW) == (
        "unknown",
        "sensor_silent",
    )
    assert judge_home(_view(timedelta(minutes=10), 90), last_chat=None, now=NOW)[0] == "home"
    assert judge_home(_view(timedelta(hours=5), 1), last_chat=None, now=NOW)[0] == "home"
    assert judge_home(_view(timedelta(hours=5), 90), last_chat=None, now=NOW)[0] == "away"
    assert judge_home(_view(timedelta(hours=1), 90), last_chat=None, now=NOW)[0] == "unknown"
