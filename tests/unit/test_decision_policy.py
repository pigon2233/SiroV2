"""decision_policy: uncertainty must not discard a grounded click when opted in."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from siro.services.computer_use.decide import (
    KEEP_GROUNDED_ACT_ENV,
    _is_grounded_act,
    decision_policy,
    keep_grounded_act_enabled,
)
from siro.services.computer_use.decision import parse_decision
from siro.services.computer_use.interface import Decision
from siro.services.computer_use.safety import InputAction

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "computer_use"
    / "sts2-title-20261114-replies.json"
)


def _act(**kwargs: object) -> Decision:
    values: dict[str, object] = {
        "kind": "act",
        "action": InputAction("click", x=395, y=342),
        "expect": "Menu leaves the title list.",
        "reason": "Enter 单人模式",
        "confidence": 0.8,
        "seen": "Main title with 单人模式",
        "scene": "menu",
        "uncertainty": (
            "Whether 存档1 holds an in-progress run is not visible. "
            "Bottom-right loading text is small and unreadable."
        ),
    }
    values.update(kwargs)
    return Decision(**values)  # type: ignore[arg-type]


def test_keep_grounded_act_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KEEP_GROUNDED_ACT_ENV, raising=False)
    assert keep_grounded_act_enabled() is False
    assert keep_grounded_act_enabled({KEEP_GROUNDED_ACT_ENV: "0"}) is False
    assert keep_grounded_act_enabled({KEEP_GROUNDED_ACT_ENV: "1"}) is True
    assert keep_grounded_act_enabled({KEEP_GROUNDED_ACT_ENV: "true"}) is False


def test_default_policy_converts_uncertain_click_to_wait() -> None:
    decided, stop, detail = decision_policy(
        _act(), autonomous=False, min_confidence=0.6, keep_grounded_act=False
    )
    assert stop == detail == ""
    assert decided.kind == "wait"
    assert decided.action is None
    assert decided.expect == "wait for a clearer frame; uncertainty set"
    assert "存档1" in decided.uncertainty


def test_flag_keeps_grounded_click_with_peripheral_uncertainty() -> None:
    original = _act()
    decided, stop, _ = decision_policy(
        original, autonomous=False, min_confidence=0.6, keep_grounded_act=True
    )
    assert stop == ""
    assert decided.kind == "act"
    assert decided.action == original.action
    assert decided.action is not None and decided.action.x == 395 and decided.action.y == 342
    assert decided.uncertainty == original.uncertainty


def test_flag_still_waits_when_act_has_no_coordinates() -> None:
    decided, stop, _ = decision_policy(
        _act(action=None),
        autonomous=False,
        min_confidence=0.6,
        keep_grounded_act=True,
    )
    assert stop == ""
    assert decided.kind == "wait"
    assert decided.action is None


def test_flag_does_not_rewrite_model_chosen_wait() -> None:
    wait = Decision(
        "wait",
        confidence=0.8,
        seen="title",
        uncertainty="loading",
        expect="clearer frame",
    )
    decided, stop, _ = decision_policy(
        wait, autonomous=False, min_confidence=0.6, keep_grounded_act=True
    )
    assert stop == ""
    assert decided.kind == "wait"
    assert decided.expect == "clearer frame"


def test_empty_uncertainty_act_unchanged_with_or_without_flag() -> None:
    for flag in (False, True):
        decided, stop, _ = decision_policy(
            _act(uncertainty=""),
            autonomous=False,
            min_confidence=0.6,
            keep_grounded_act=flag,
        )
        assert stop == ""
        assert decided.kind == "act" and decided.action is not None


def test_is_grounded_act_rejects_incomplete_click() -> None:
    assert _is_grounded_act(_act()) is True
    assert _is_grounded_act(_act(action=InputAction("click"))) is False
    assert _is_grounded_act(Decision("wait", uncertainty="x")) is False


def test_replay_real_title_replies_default_waits_flag_clicks() -> None:
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(records) == 7
    for row in records:
        parsed = parse_decision(row["raw"])
        assert parsed.kind == "act"
        assert parsed.action is not None
        assert parsed.action.x == 395 and parsed.action.y == 342
        assert parsed.scene == "menu"
        assert parsed.uncertainty.strip()
        assert "单人模式" in parsed.seen or "单人模式" in parsed.targets
        default, _, _ = decision_policy(
            parsed, autonomous=False, min_confidence=0.6, keep_grounded_act=False
        )
        assert default.kind == "wait", row["seq"]
        assert default.action is None
        kept, stop, _ = decision_policy(
            parsed, autonomous=False, min_confidence=0.6, keep_grounded_act=True
        )
        assert stop == ""
        assert kept.kind == "act"
        assert kept.action is not None
        assert kept.action.x == 395 and kept.action.y == 342
        assert kept.confidence >= 0.6
