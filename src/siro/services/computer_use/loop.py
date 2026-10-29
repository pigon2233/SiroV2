"""Perceive -> decide -> gate -> act -> re-perceive, with hard stops instead of guessing.

The loop never trusts a decision blindly: coordinates must lie in the focused window, the window
must be on the owner's allowlist, "done" needs proof confirmed on a second fresh observation, an
unchanged screen after an action counts toward "stuck", and an unknown outcome halts (no resend).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import (
    CloudScreenNotAllowed,
    Decider,
    Decision,
    DecisionError,
    StepRecord,
)
from siro.services.computer_use.perception import (
    Observation,
    allowed_processes,
    image_to_screen,
    is_fresh,
)
from siro.services.computer_use.playbook import PlaybookStore, notes_block
from siro.services.computer_use.safety import InputAction

MAX_STEPS = 40
MAX_SECONDS = 600.0
MIN_CONFIDENCE = 0.6
MAX_NO_CHANGE = 3  # consecutive actions that visibly changed nothing
MAX_INVALID = 2  # consecutive decisions rejected before acting
MAX_RATE_WAITS = 5
MAX_WAITS = 6  # consecutive "wait" decisions (transitions) before giving up
WAIT_SECONDS = 1.0
SETTLE_SECONDS = 0.4


@dataclass(frozen=True, slots=True)
class LoopReport:
    state: str  # done | stopped | failed
    reason: str
    steps: tuple[StepRecord, ...] = field(default_factory=tuple)

    @property
    def success(self) -> bool:
        return self.state == "done"


def _describe(action: InputAction) -> str:
    if action.kind in {"move", "click"}:
        return f"{action.kind}({action.x},{action.y},{action.button})"
    if action.kind == "key":
        return f"key({action.key},{action.hold_ms})" if action.hold_ms else f"key({action.key})"
    if action.kind == "scroll":
        return f"scroll({action.amount})"
    return f"type({len(action.text)} chars)"


def _inside(action: InputAction, rect: tuple[int, int, int, int] | None) -> bool:
    if action.x is None or action.y is None:
        return True
    if rect is None:
        return False
    left, top, width, height = rect
    return left <= action.x < left + width and top <= action.y < top + height


class DecisionLoop:
    def __init__(
        self,
        bridge: ComputerBridge,
        decider: Decider,
        *,
        allowed: frozenset[str] | None = None,
        max_steps: int = MAX_STEPS,
        max_seconds: float = MAX_SECONDS,
        min_confidence: float = MIN_CONFIDENCE,
        settle: float = SETTLE_SECONDS,
        wait: float = WAIT_SECONDS,
        playbook: PlaybookStore | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._bridge = bridge
        self._decider = decider
        self._allowed = allowed_processes() if allowed is None else allowed
        self._max_steps = max_steps
        self._max_seconds = max_seconds
        self._min_confidence = min_confidence
        self._settle = settle
        self._wait = wait
        self._playbook = playbook
        self.process = ""  # program of the first allowed observation (key of its play notes)
        self.live: list[StepRecord] = []
        self._clock = clock

    async def run(self, goal: str) -> LoopReport:
        history = self.live = []

        def end(state: str, reason: str) -> LoopReport:
            return LoopReport(state, reason, tuple(history))

        if not self._allowed:
            return end("stopped", "no_allowed_processes")
        started = self._clock()
        no_change = invalid = rate_waits = waits = 0
        task = goal
        done_seen = False
        before: Observation | None = None
        for step in range(1, self._max_steps + 1):
            if self._clock() - started > self._max_seconds:
                return end("stopped", "time_limit")
            observation, error = await self._bridge.observe()
            if observation is None:
                return end("stopped", error)
            if observation.blocked_reason:
                return end("stopped", observation.blocked_reason)
            if observation.process not in self._allowed:
                return end("stopped", "window_not_allowed")
            if not is_fresh(observation, self._clock()):
                return end("stopped", "stale_observation")
            if not self.process:
                self.process = observation.process
                if self._playbook is not None:
                    task = goal + notes_block(self._playbook.texts(self.process))
            if before is not None and history and history[-1].screen_changed is None:
                changed = observation.fingerprint != before.fingerprint
                history[-1] = StepRecord(
                    history[-1].step, history[-1].action, history[-1].expect,
                    history[-1].outcome, changed, history[-1].seen,
                )  # fmt: skip
                no_change = 0 if changed else no_change + 1
                if no_change >= MAX_NO_CHANGE:
                    return end("stopped", "stuck_no_visible_change")
            try:
                decision = await self._decider.decide(task, history, observation)
            except CloudScreenNotAllowed:
                return end("stopped", "cloud_screen_not_allowed")
            except (DecisionError, OSError, TimeoutError) as error:
                return end("failed", f"decider_error:{error}")
            if decision.kind == "wait":
                waits += 1
                history.append(
                    StepRecord(step, "(wait)", decision.expect, "ok", None, decision.seen)
                )
                if waits > MAX_WAITS:
                    return end("stopped", "stuck_waiting")
                before = None
                await asyncio.sleep(self._wait)
                continue
            waits = 0
            if decision.kind == "ask":
                return end("stopped", "needs_owner")
            if decision.kind == "stuck":
                return end("stopped", "decider_stuck")
            if decision.confidence < self._min_confidence:
                return end("stopped", "low_confidence")
            if decision.kind == "done":
                if not decision.evidence.strip():
                    return end("stopped", "done_without_evidence")
                if done_seen:
                    return end("done", decision.evidence)
                done_seen = True  # confirm on the next fresh observation
                before = None
                history.append(StepRecord(step, "(confirm done)", "", "ok", None))
                await asyncio.sleep(self._settle)
                continue
            done_seen = False
            action = self._checked_action(decision, observation)
            if isinstance(action, str):
                invalid += 1
                before = None
                history.append(
                    StepRecord(step, "(rejected)", decision.expect, f"invalid:{action}", None)
                )
                if invalid > MAX_INVALID:
                    return end("stopped", "too_many_invalid_decisions")
                continue
            invalid = 0
            result = await self._bridge.act(action)
            if not result.ok:
                if result.error == "rate_limited" and rate_waits < MAX_RATE_WAITS:
                    rate_waits += 1
                    await asyncio.sleep(1.0)
                    continue
                if result.error == "outcome_unknown":
                    history.append(
                        StepRecord(step, _describe(action), decision.expect, "unknown", None)
                    )
                    return end("stopped", "outcome_unknown")
                history.append(
                    StepRecord(
                        step, _describe(action), decision.expect, f"denied:{result.error}", None
                    )
                )
                return end("stopped", f"denied:{result.error}")
            history.append(
                StepRecord(step, _describe(action), decision.expect, "ok", None, decision.seen)
            )
            before = observation
            await asyncio.sleep(self._settle)
        return end("stopped", "step_limit")

    @staticmethod
    def _checked_action(decision: Decision, observation: Observation) -> InputAction | str:
        action = decision.action
        if action is None:
            return "no_action"
        x, y = action.x, action.y
        if x is not None and y is not None:
            x, y = image_to_screen(observation, x, y)
        scaled = InputAction(action.kind, x=x, y=y)
        if not _inside(scaled, observation.window_rect):
            return "outside_window"
        return InputAction(
            kind=action.kind,
            x=x,
            y=y,
            button=action.button,
            key=action.key,
            text=action.text,
            amount=action.amount,
            hold_ms=action.hold_ms,
            focus_is_secret=observation.focus_is_secret,
        )
