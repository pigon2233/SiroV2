"""Perceive -> decide -> gate -> act -> re-perceive, with hard stops instead of guessing.

The loop never trusts a decision blindly: coordinates must lie in the focused window, the window
must be on the owner's allowlist, "done" needs proof confirmed on a second fresh observation, an
unchanged screen after an action counts toward "stuck", and an unknown outcome halts (no resend).
"""

from __future__ import annotations

import asyncio
import os
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
from siro.services.computer_use.demos import DemoRecorder, DemoRun
from siro.services.computer_use.intent import names_program
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
MAX_CONFIGURED_STEPS = 1200
MAX_CONFIGURED_SECONDS = 7200
MIN_CONFIDENCE = 0.6
MAX_NO_CHANGE = 3  # consecutive actions that visibly changed nothing
MAX_INVALID = 2  # consecutive decisions rejected before acting
MAX_RATE_WAITS = 5
RATE_WAIT_SECONDS = 1.0
MAX_WAITS = 6  # consecutive "wait" decisions (transitions) before giving up
WAIT_SECONDS = 1.0
SETTLE_SECONDS = 0.4


class ComputerLimitError(ValueError):
    """The owner's run limit configuration is malformed or out of bounds."""


def _configured_limit(name: str, default: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if not raw.isascii() or not raw.isdigit() or len(raw) > 5:
        raise ComputerLimitError(f"invalid {name}")
    value = int(raw)
    if not 1 <= value <= maximum:
        raise ComputerLimitError(f"invalid {name}")
    return value


@dataclass(frozen=True, slots=True)
class LoopReport:
    state: str  # done | stopped | failed
    reason: str
    steps: tuple[StepRecord, ...] = field(default_factory=tuple)
    detail: str = ""  # model's explanation when the owner must decide

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
        max_steps: int | None = None,
        max_seconds: float | None = None,
        min_confidence: float = MIN_CONFIDENCE,
        settle: float = SETTLE_SECONDS,
        wait: float = WAIT_SECONDS,
        playbook: PlaybookStore | None = None,
        recorder: DemoRecorder | None = None,
        focus: bool | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._bridge = bridge
        self._decider = decider
        self._allowed = allowed_processes() if allowed is None else allowed
        self._max_steps = (
            _configured_limit("SIRO_COMPUTER_MAX_STEPS", MAX_STEPS, MAX_CONFIGURED_STEPS)
            if max_steps is None
            else max_steps
        )
        self._max_seconds = (
            _configured_limit("SIRO_COMPUTER_MAX_SECONDS", int(MAX_SECONDS), MAX_CONFIGURED_SECONDS)
            if max_seconds is None
            else max_seconds
        )
        self._min_confidence = min_confidence
        self._settle = settle
        self._wait = wait
        self._playbook = playbook
        self._recorder = recorder
        # Talking to SIRO puts the chat in front; bring the allowed game forward once per run.
        self._focus = os.environ.get("SIRO_COMPUTER_FOCUS", "1") != "0" if focus is None else focus
        self._demo: DemoRun | None = None
        self._demo_last: int | None = None
        self.process = ""  # program of the first allowed observation (key of its play notes)
        self.live: list[StepRecord] = []
        self._clock = clock

    @property
    def limits(self) -> dict[str, int | float]:
        return {"max_steps": self._max_steps, "max_seconds": self._max_seconds}

    async def run(self, goal: str) -> LoopReport:
        history = self.live = []

        def end(state: str, reason: str, detail: str = "") -> LoopReport:
            if self._demo is not None:
                self._demo.finish(state, reason)
            return LoopReport(state, reason, tuple(history), detail)

        if not self._allowed:
            return end("stopped", "no_allowed_processes")
        started = self._clock()
        stop_generation = self._bridge.stop_generation
        no_change = invalid = rate_waits = waits = 0
        task = goal
        focus_tried = False
        done_seen = False
        before: Observation | None = None
        for step in range(1, self._max_steps + 1):
            if self._bridge.stop_generation != stop_generation:
                return end("stopped", "emergency_stop")
            if self._clock() - started > self._max_seconds:
                return end("stopped", "time_limit")
            observation, error = await self._bridge.observe()
            if self._bridge.stop_generation != stop_generation:
                return end("stopped", "emergency_stop")
            wrong_window = error == "window_not_visible" or (
                observation is not None
                and not observation.blocked_reason
                and observation.process not in self._allowed
            )
            if wrong_window and self._focus and not focus_tried:
                focus_tried = True
                target = self._focus_target(goal)
                if target and (await self._bridge.focus(target)).ok:
                    await asyncio.sleep(0.8)
                    continue
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
                if self._recorder is not None:
                    self._demo = self._recorder.begin(self.process, goal)
            if before is not None and history and history[-1].screen_changed is None:
                changed = observation.fingerprint != before.fingerprint
                history[-1] = StepRecord(
                    history[-1].step, history[-1].action, history[-1].expect,
                    history[-1].outcome, changed, history[-1].seen,
                )  # fmt: skip
                if self._demo is not None and self._demo_last is not None:
                    self._demo.set_changed(self._demo_last, changed)
                no_change = 0 if changed else no_change + 1
                if no_change >= MAX_NO_CHANGE:
                    return end("stopped", "stuck_no_visible_change")
            deadline = None
            try:
                remaining = self._max_seconds - (self._clock() - started)
                if remaining <= 0:
                    return end("stopped", "time_limit")
                async with asyncio.timeout(remaining) as deadline:
                    decision = await self._decider.decide(task, history, observation)
            except TimeoutError as error:
                if self._bridge.stop_generation != stop_generation:
                    return end("stopped", "emergency_stop")
                if deadline is not None and deadline.expired():
                    return end("stopped", "time_limit")
                return end("failed", f"decider_error:{error}")
            except CloudScreenNotAllowed:
                return end("stopped", "cloud_screen_not_allowed")
            except (DecisionError, OSError) as error:
                if self._bridge.stop_generation != stop_generation:
                    return end("stopped", "emergency_stop")
                return end("failed", f"decider_error:{error}")
            if self._bridge.stop_generation != stop_generation:
                return end("stopped", "emergency_stop")
            if self._clock() - started >= self._max_seconds:
                return end("stopped", "time_limit")
            if decision.kind == "wait":
                done_seen = False
                waits += 1
                history.append(
                    StepRecord(step, "(wait)", decision.expect, "ok", None, decision.seen)
                )
                self._record(observation, decision, None)
                if waits > MAX_WAITS:
                    return end("stopped", "stuck_waiting")
                before = None
                await asyncio.sleep(self._wait)
                continue
            waits = 0
            if decision.kind == "ask":
                return end("stopped", "needs_owner", decision.reason.strip()[:300])
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
                    await asyncio.sleep(RATE_WAIT_SECONDS)
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
            rate_waits = 0
            history.append(
                StepRecord(step, _describe(action), decision.expect, "ok", None, decision.seen)
            )
            self._record(observation, decision, action)
            before = observation
            await asyncio.sleep(self._settle)
        return end("stopped", "step_limit")

    def _focus_target(self, goal: str) -> str | None:
        """The allowed program to bring forward: the one the goal names, else the only one."""
        lowered = goal.lower()
        named = [p for p in sorted(self._allowed) if names_program(p.removesuffix(".exe"), lowered)]
        if len(named) == 1:
            return named[0]
        return next(iter(self._allowed)) if len(self._allowed) == 1 else None

    def _record(
        self, observation: Observation, decision: Decision, action: InputAction | None
    ) -> None:
        if self._demo is None:
            return
        try:
            index = self._demo.step(observation, decision, action)
        except OSError:
            self._demo = None  # a full disk must never stop the run
            return
        self._demo_last = index if action is not None else None

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
