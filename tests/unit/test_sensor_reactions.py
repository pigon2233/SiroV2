# ruff: noqa: RUF001
from datetime import UTC, datetime, timedelta

import pytest

from siro.core.sensor_reactions import (
    SensorReactions,
    decide_sensor_line,
    parse_quiet_hours,
)

T0 = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)


def _rules(**kwargs: object) -> SensorReactions:
    return SensorReactions(timezone="UTC", **kwargs)  # type: ignore[arg-type]


def test_arrival_has_cooldown_and_only_fires_on_the_edge() -> None:
    rules = _rules()
    assert rules.handle("motion_detected", None, T0) == ["speak:arrival"]
    assert rules.handle("motion_detected", None, T0 + timedelta(minutes=1)) == []
    assert rules.tick(T0 + timedelta(minutes=20)) == ["speak:departure"]
    # Back within the arrival cooldown: no second arrival trigger.
    assert rules.handle("motion_detected", None, T0 + timedelta(minutes=25)) == []


def test_departure_then_return_reports_time_away() -> None:
    rules = _rules()
    rules.handle("motion_detected", None, T0)
    assert rules.tick(T0 + timedelta(minutes=16)) == ["speak:departure"]
    back = T0 + timedelta(hours=2)
    assert rules.handle("motion_detected", None, back) == ["speak:arrival"]
    assert rules.facts("arrival", back)["away_minutes"] == 120 - 0


def test_global_gap_limits_back_to_back_triggers() -> None:
    rules = _rules()
    assert rules.handle("light_update", 1.0, T0) == ["quiet_on", "speak:dark"]
    rules.handle("light_update", 100.0, T0 + timedelta(minutes=1))
    assert rules.handle("motion_detected", None, T0 + timedelta(minutes=2)) == []


def test_long_active_fires_once_per_cooldown() -> None:
    rules = _rules()
    rules.handle("motion_detected", None, T0)
    for minutes in range(10, 190, 10):
        rules.handle("motion_detected", None, T0 + timedelta(minutes=minutes))
    assert rules.tick(T0 + timedelta(hours=3, minutes=5)) == ["speak:long_active"]
    assert rules.tick(T0 + timedelta(hours=3, minutes=10)) == []


def test_quiet_hours_suppress_speech_but_not_listening() -> None:
    rules = _rules(quiet_hours=parse_quiet_hours("07:00-09:00"))
    assert rules.handle("motion_detected", None, T0) == []
    assert rules.handle("button_pressed", None, T0) == ["listen"]
    late = _rules(quiet_hours=parse_quiet_hours("23:00-07:00"))
    assert late.handle("motion_detected", None, T0) == ["speak:arrival"]


def test_quiet_hours_parsing() -> None:
    assert parse_quiet_hours("23:00-07:00") == (1380, 420)
    assert parse_quiet_hours("") is None
    with pytest.raises(ValueError):
        parse_quiet_hours("late")


def test_dark_quiet_mode_suppresses_until_light_returns() -> None:
    rules = _rules(dark_lux=5, bright_lux=15)
    assert rules.handle("light_update", 2.0, T0) == ["quiet_on", "speak:dark"]
    assert rules.quiet
    assert rules.handle("motion_detected", None, T0 + timedelta(hours=1)) == []
    assert rules.handle("button_pressed", None, T0) == []
    assert rules.handle("light_update", 10.0, T0) == []
    assert rules.handle("light_update", 200.0, T0) == ["quiet_off"]
    assert rules.handle("button_pressed", None, T0) == ["listen"]


@pytest.mark.asyncio
async def test_model_may_stay_silent() -> None:
    async def ask(_prompt: str) -> str | None:
        return "SILENT"

    assert await decide_sensor_line(ask, {"trigger": "arrival"}, 0) is None


@pytest.mark.asyncio
async def test_model_line_is_used_when_it_speaks() -> None:
    async def ask(_prompt: str) -> str | None:
        return "回來啦，辛苦了。"

    assert await decide_sensor_line(ask, {"trigger": "arrival"}, 0) == "回來啦，辛苦了。"


@pytest.mark.asyncio
async def test_failed_model_falls_back_for_arrival_only() -> None:
    async def broken(_prompt: str) -> str | None:
        raise RuntimeError("down")

    async def empty(_prompt: str) -> str | None:
        return None

    assert await decide_sensor_line(broken, {"trigger": "arrival"}, 0) == "早安，今天也請多指教。"
    assert await decide_sensor_line(empty, {"trigger": "arrival"}, 1) == "歡迎回來。"
    assert await decide_sensor_line(broken, {"trigger": "departure"}, 0) is None
