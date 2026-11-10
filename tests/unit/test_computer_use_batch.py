"""Batch planner/executor contracts: no native input, only fake bridge calls."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from typing import Any

import pytest

from siro.services.computer_use.batch import BatchPlan, execute_batch, parse_batch
from siro.services.computer_use.batch_decision import BatchingDecider, maybe_batch
from siro.services.computer_use.bridge import BridgeResult
from siro.services.computer_use.decision import Decision, DecisionError, VerifyResult
from siro.services.computer_use.loop import DecisionLoop
from siro.services.computer_use.ocr import OcrFrame, TextBlock
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import ControlGate, InputAction

FRAME = OcrFrame(
    "test",
    (100, 100),
    (TextBlock(1, "Defend", (10, 10, 20, 20)), TextBlock(2, "End Turn", (70, 70, 90, 90))),
    0,
    True,
)
REPLY = {
    "scene": "combat",
    "stable": True,
    "ids": [1, 2],
    "confidence": 0.9,
    "expect": "new turn",
    "seen": "combat",
}
PLAN = parse_batch(json.dumps(REPLY), FRAME)


def observation(**kw: Any) -> Observation:
    return replace(
        Observation(
            1,
            10,
            "game",
            "game.exe",
            (0, 0, 100, 100),
            (100, 100),
            "before",
            image_size=(100, 100),
            image_rect=(0, 0, 100, 100),
            window_id="1",
            pid=2,
        ),
        **kw,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"ids": [True, 2]},
        {"ids": [1, 1]},
        {"ids": [1, 999]},
        {"ids": [1]},
        {"ids": [1, 2, 3, 4, 5]},
        {"scene": "shop"},
        {"stable": False},
        {"expect": ""},
        {"confidence": True},
        {"confidence": 2},
    ],
)
def test_strict_batch_parser(changes: dict[str, Any]) -> None:
    with pytest.raises(DecisionError):
        parse_batch(json.dumps(REPLY | changes), FRAME)


def test_centers_and_order() -> None:
    assert [(a.x, a.y) for a in PLAN.actions] == [(15, 15), (80, 80)]


class Bridge:
    def __init__(self, **kw: Any) -> None:
        self.gate = ControlGate(enabled=True, clock=lambda: 10)
        self.stop_generation = 0
        self.sent: list[InputAction] = []
        self.kw = kw
        self.n = 0

    async def observe(self) -> tuple[Observation | None, str]:
        self.n += 1
        return observation(fingerprint=str(len(self.sent)), **self.kw), ""

    async def act(self, action: InputAction) -> BridgeResult:
        verdict = self.gate.check(action)
        if not verdict.allowed:
            return BridgeResult(False, verdict.reason)
        self.sent.append(action)
        return BridgeResult(True)


def run(bridge: Bridge, plan: BatchPlan = PLAN) -> Any:
    return asyncio.run(
        execute_batch(
            bridge,
            plan,
            observation(),
            allowed=frozenset({"game.exe"}),
            clock=lambda: 10,
            translate=lambda a, o: a,
        )
    )


def test_success_no_intermediate_semantic_verify() -> None:
    bridge = Bridge()
    result = run(bridge)
    assert not result.error and len(result.sent) == 2 and bridge.n == 3


@pytest.mark.parametrize(
    "kw,error",
    [
        ({"pid": 3}, "window_changed"),
        ({"window_id": None}, "window_changed"),
        ({"process": "evil.exe"}, "window_changed"),
        ({"taken_at": 0}, "stale_observation"),
        ({"blocked_reason": "secret_field_focused"}, "secret_field_focused"),
        ({"window_rect": (1, 1, 100, 100)}, "window_changed"),
    ],
)
def test_observation_fences(kw: dict[str, Any], error: str) -> None:
    bridge = Bridge(**kw)
    assert run(bridge).error == error
    assert not bridge.sent


def test_default_off_and_extra_batch_subwhitelist() -> None:
    inner = Inner()
    assert maybe_batch(inner, {}) is inner
    assert maybe_batch(inner, {"SIRO_COMPUTER_ACTION_BATCH": "1"}) is inner


@pytest.mark.parametrize("kind", ["stop", "disable", "unknown", "rate", "cancel"])
def test_abort_partial_never_replays(kind: str) -> None:
    class Interrupted(Bridge):
        async def act(self, action: InputAction) -> BridgeResult:
            if kind == "unknown":
                return BridgeResult(False, "outcome_unknown")
            if kind == "rate":
                return BridgeResult(False, "rate_limited")
            if kind == "cancel":
                raise asyncio.CancelledError
            result = await super().act(action)
            if kind == "stop":
                self.stop_generation += 1
                self.gate.trip()
            if kind == "disable":
                self.gate.disable()
            return result

    bridge = Interrupted()
    if kind == "cancel":
        with pytest.raises(asyncio.CancelledError):
            run(bridge)
    else:
        result = run(bridge)
        assert (
            result.error
            == {
                "stop": "emergency_stop",
                "disable": "control_disabled",
                "unknown": "outcome_unknown",
                "rate": "rate_limited",
            }[kind]
        )
        assert len(bridge.sent) <= 1


def test_guard_recheck_cannot_override_blocked_frame() -> None:
    async def guard(o: Observation) -> tuple[Observation | None, str]:
        return observation(blocked_reason="blocked_title"), ""

    bridge = Bridge()
    result = asyncio.run(
        execute_batch(
            bridge,
            PLAN,
            observation(),
            allowed=frozenset({"game.exe"}),
            clock=lambda: 10,
            translate=lambda a, o: a,
            guard=guard,
        )
    )
    assert result.error == "blocked_title" and not bridge.sent


class Inner:
    calls = 0
    verified = 0

    async def decide(self, *a: Any, **kw: Any) -> Decision:
        self.calls += 1
        return Decision("wait")

    async def verify(self, *a: Any) -> VerifyResult:
        self.verified += 1
        return VerifyResult("confirmed")


class Planner:
    async def plan(self, *a: Any) -> BatchPlan:
        return PLAN


def test_pending_identity_and_drain() -> None:
    async def scenario() -> None:
        decider = BatchingDecider(Inner(), Planner(), frozenset({"game.exe"}))  # type: ignore[arg-type]
        decision = await decider.decide("turn", [], observation())
        assert decider.take_batch(replace(decision)) is None
        decision = await decider.decide("turn", [], observation())
        assert decider.take_batch(decision) is PLAN
        assert decider.take_batch(decision) is None

    asyncio.run(scenario())


def test_loop_verifies_exactly_once_at_end(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = Bridge()
    inner = Inner()
    decider = BatchingDecider(inner, Planner(), frozenset({"game.exe"}))  # type: ignore[arg-type]
    loop = DecisionLoop(
        bridge,  # type: ignore[arg-type]
        decider,
        allowed=frozenset({"game.exe"}),
        max_steps=1,
        clock=lambda: 10,
        settle=0,
        wait=0,
        focus=False,
    )

    async def guard(o: Observation, *a: Any) -> tuple[Observation | None, str]:
        assert inner.verified == 0
        return await bridge.observe()

    monkeypatch.setattr(loop, "_wait_for_same_screen", guard)
    result = asyncio.run(loop.run("finish turn"))
    assert result.reason == "step_limit" and inner.verified == 1
    assert len(bridge.sent) == 2 and result.steps[-1].outcome == "effective"
