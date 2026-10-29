from __future__ import annotations

import pytest

from siro.services.computer_use.safety import ControlGate, InputAction


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _gate(clock: Clock | None = None, enabled: bool = True) -> ControlGate:
    return ControlGate(clock=clock or Clock(), enabled=enabled)


def test_default_off_even_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIRO_COMPUTER_CONTROL_ENABLED", raising=False)
    decision = ControlGate().check(InputAction("click", x=1, y=1))
    assert not decision.allowed and decision.reason == "control_disabled"


def test_env_flag_enables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_CONTROL_ENABLED", "1")
    assert ControlGate().check(InputAction("click", x=1, y=1)).allowed


def test_trip_latches_until_owner_enables() -> None:
    gate = _gate()
    gate.trip()
    assert gate.check(InputAction("click", x=1, y=1)).reason == "emergency_stop"
    gate.disable()
    assert gate.check(InputAction("click", x=1, y=1)).reason == "emergency_stop"
    gate.enable()
    assert gate.check(InputAction("click", x=1, y=1)).allowed


@pytest.mark.parametrize("kind", ["drag", "shell", "launch", ""])
def test_unknown_kinds_denied(kind: str) -> None:
    assert _gate().check(InputAction(kind)).reason == "action_not_allowed"


def test_bounds_and_missing_coordinates() -> None:
    gate = _gate()
    assert gate.check(InputAction("click", x=5000, y=5)).reason == "out_of_bounds"
    assert gate.check(InputAction("click", x=-1, y=5)).reason == "out_of_bounds"
    assert gate.check(InputAction("click")).reason == "missing_coordinates"
    assert gate.check(InputAction("click", x=10, y=10, button="middle")).reason == (
        "button_not_allowed"
    )


@pytest.mark.parametrize("combo", ["Alt+F4", "control+alt+del", "WIN+L", ""])
def test_blocked_keys(combo: str) -> None:
    assert _gate().check(InputAction("key", key=combo)).reason == "key_blocked"


def test_normal_key_allowed() -> None:
    assert _gate().check(InputAction("key", key="space")).allowed


def test_typing_secrets_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_SERVICE_TOKEN", "canary-value-123456")
    gate = _gate()
    assert gate.check(InputAction("type", text="hi", focus_is_secret=True)).reason == (
        "secret_field"
    )
    assert gate.check(InputAction("type", text="sk-" + "a" * 24)).reason == "secret_text"
    assert gate.check(InputAction("type", text="x canary-value-123456")).reason == ("secret_text")
    assert gate.check(InputAction("type", text="a" * 201)).reason == "text_length"
    assert gate.check(InputAction("type", text="hello")).allowed


def test_rate_limits() -> None:
    clock = Clock()
    gate = _gate(clock)
    results = [gate.check(InputAction("move", x=1, y=1)).allowed for _ in range(6)]
    assert results == [True] * 5 + [False]
    clock.now += 1.1
    assert gate.check(InputAction("move", x=1, y=1)).allowed
    # Sustained 4/s stays under the per-second cap but hits the 120/minute cap.
    allowed = 0
    for _ in range(200):
        clock.now += 0.25
        if gate.check(InputAction("move", x=1, y=1)).allowed:
            allowed += 1
    assert allowed < 200
