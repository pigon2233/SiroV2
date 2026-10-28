from datetime import UTC, datetime, timedelta

from siro.core.sensor_reactions import SensorReactions

T0 = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)


def test_arrival_greets_once_per_gap() -> None:
    rules = SensorReactions(greeting_gap=timedelta(minutes=30))
    assert rules.handle("motion_detected", None, T0) == ["greet"]
    assert rules.handle("motion_detected", None, T0 + timedelta(minutes=5)) == []
    assert rules.handle("motion_cleared", None, T0 + timedelta(minutes=6)) == []
    assert rules.handle("motion_detected", None, T0 + timedelta(minutes=31)) == ["greet"]


def test_dark_enters_quiet_mode_and_suppresses_greeting_and_listen() -> None:
    rules = SensorReactions()
    assert rules.handle("light_update", 2.0, T0) == ["quiet_on"]
    assert rules.quiet
    assert rules.handle("light_update", 1.0, T0) == []
    assert rules.handle("motion_detected", None, T0) == []
    assert rules.handle("button_pressed", None, T0) == []


def test_light_on_restores_with_hysteresis_and_allows_greeting() -> None:
    rules = SensorReactions(dark_lux=5, bright_lux=15)
    rules.handle("light_update", 2.0, T0)
    assert rules.handle("light_update", 10.0, T0) == []
    assert rules.quiet
    assert rules.handle("light_update", 200.0, T0) == ["quiet_off"]
    assert not rules.quiet
    assert rules.handle("motion_detected", None, T0) == ["greet"]


def test_button_starts_listening_when_not_quiet() -> None:
    assert SensorReactions().handle("button_pressed", None, T0) == ["listen"]
