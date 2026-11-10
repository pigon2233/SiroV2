"""Perceive -> decide -> gate -> act -> re-perceive, with hard stops instead of guessing.

The loop never trusts a decision blindly: coordinates must lie in the focused window, the window
must be on the owner's allowlist, "done" needs proof confirmed on a second fresh observation, an
unchanged screen after an action counts toward "stuck", and an unknown outcome halts (no resend).
"""

from __future__ import annotations

import asyncio
import math
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace

from siro.services.computer_use.batch import BatchPlan, execute_batch
from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decide import decision_goal, decision_policy
from siro.services.computer_use.demos import DemoRecorder, DemoRun
from siro.services.computer_use.execute import _describe as _describe
from siro.services.computer_use.execute import _history_action as _history_action
from siro.services.computer_use.execute import _inside as _inside
from siro.services.computer_use.execute import _normalize_image_xy as _normalize_image_xy
from siro.services.computer_use.execute import checked_action
from siro.services.computer_use.intent import names_program
from siro.services.computer_use.interface import (
    CloudScreenNotAllowed as CloudScreenNotAllowed,
)
from siro.services.computer_use.interface import (
    Decider as Decider,
)
from siro.services.computer_use.interface import (
    Decision as Decision,
)
from siro.services.computer_use.interface import (
    DecisionError as DecisionError,
)
from siro.services.computer_use.interface import (
    StepRecord as StepRecord,
)
from siro.services.computer_use.interface import (
    VerifyResult as VerifyResult,
)
from siro.services.computer_use.observe import _pixel_digest as _pixel_digest
from siro.services.computer_use.observe import _same_target as _same_target
from siro.services.computer_use.observe import _screen_changed as _screen_changed
from siro.services.computer_use.observe import wait_for_same_screen
from siro.services.computer_use.perception import (
    Observation,
    allowed_processes,
    is_fresh,
)
from siro.services.computer_use.playbook import PlaybookStore, notes_block
from siro.services.computer_use.safety import InputAction
from siro.services.computer_use.stuck import (
    _click_ineffective_same_spot as _click_ineffective_same_spot,
)
from siro.services.computer_use.stuck import _last_real_click as _last_real_click
from siro.services.computer_use.stuck import _norm_label as _norm_label
from siro.services.computer_use.stuck import _parse_click_xy as _parse_click_xy
from siro.services.computer_use.stuck import _recovery_hint as _recovery_hint
from siro.services.computer_use.stuck import _scene_not_advancing as _scene_not_advancing
from siro.services.computer_use.verify import verify_expect, verify_step

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
AUTONOMOUS_WAIT_SECONDS = 0.2
AUTONOMOUS_SETTLE_SECONDS = 0.15
SETTLE_ENV = "SIRO_COMPUTER_SETTLE"
WAIT_ENV = "SIRO_COMPUTER_WAIT"
DECIDE_TIMEOUT_SECONDS = (
    120.0  # local VLM on a busy 8GB GPU often needs >90s; soft-retry still applies
)
MAX_DECIDE_SOFT_FAILS = 3  # bounded runs only; endless autonomous keeps re-observing
STRATEGY_REFRESH_EVERY = 8  # ask the model to refresh the short plan this often
SCREEN_MATCH_WAIT_SECONDS = 30.0
SCREEN_MATCH_POLL_SECONDS = 0.4
AUTONOMOUS_FLAG = "SIRO_COMPUTER_AUTONOMOUS"  # 1 = never stop to ask the owner
ENDLESS_FLAG = "SIRO_COMPUTER_ENDLESS"


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


def _optional_run_limit(name: str, default: int, maximum: int, *, unlimited_ok: bool) -> int | None:
    """Return None for no limit when endless play allows 0/unlimited."""
    raw = os.environ.get(name)
    if unlimited_ok and (raw is None or raw in {"0", "unlimited", "none"}):
        return None
    if raw is None:
        return default
    return _configured_limit(name, default, maximum)


def _timing_env(name: str, default: float) -> float:
    """Owner override for settle/wait seconds; invalid values keep the default."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw.strip())
    except ValueError:
        return default
    if not math.isfinite(value) or value < 0 or value > 10:
        return default
    return value


def _autonomous_hint() -> str:
    return (
        "\n\nOwner autonomous mode is ON: never answer kind=ask. Prefer a quick act. "
        "If you see defeat/death/game over/retry/continue/play again, click that button "
        "once immediately and keep playing a new run. Do not stop after a loss. "
        "Do not answer kind=done just because a run ended — click through and continue. "
        "Combat: if energy is 0 or no playable cards, click End Turn / 结束回合 immediately. "
        "Map: click only a reachable next node once; "
        "if the map description repeats, try another node. "
        "Do not reuse the same vague 'seen' sentence — "
        "describe what is new (combat/map/event/reward)."
    )


_CLICK_RE = re.compile(r"^click\((-?\d+),(-?\d+)")
SAME_CLICK_RADIUS = 80  # ban near-miss repeats (model often drifts ~50px on same wrong guess)
SAME_CLICK_LOOKBACK = 3  # any recent unresolved click near this spot counts
SCENE_STALL_LOOKBACK = 4  # same scene without an effective act ⇒ no progress


@dataclass(frozen=True, slots=True)
class LoopReport:
    state: str  # done | stopped | failed
    reason: str
    steps: tuple[StepRecord, ...] = field(default_factory=tuple)
    detail: str = ""  # model's explanation when the owner must decide

    @property
    def success(self) -> bool:
        return self.state == "done"


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
        autonomous: bool | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._bridge = bridge
        self._decider = decider
        self._allowed = allowed_processes() if allowed is None else allowed
        # Owner opt-in: keep playing without needs_owner / low_confidence stops.
        self._autonomous = (
            os.environ.get(AUTONOMOUS_FLAG, "0") == "1" if autonomous is None else autonomous
        )
        self._endless = self._autonomous and os.environ.get(ENDLESS_FLAG, "0") == "1"
        if max_steps is not None:
            self._max_steps: int | None = max_steps
        else:
            self._max_steps = _optional_run_limit(
                "SIRO_COMPUTER_MAX_STEPS",
                MAX_STEPS,
                MAX_CONFIGURED_STEPS,
                unlimited_ok=self._endless,
            )
        if max_seconds is not None:
            self._max_seconds: float | None = float(max_seconds)
        else:
            seconds = _optional_run_limit(
                "SIRO_COMPUTER_MAX_SECONDS",
                int(MAX_SECONDS),
                MAX_CONFIGURED_SECONDS,
                unlimited_ok=self._endless,
            )
            self._max_seconds = None if seconds is None else float(seconds)
        self._min_confidence = min_confidence
        if settle != SETTLE_SECONDS:
            self._settle = settle
        else:
            self._settle = _timing_env(
                SETTLE_ENV,
                AUTONOMOUS_SETTLE_SECONDS if self._autonomous else SETTLE_SECONDS,
            )
        if wait != WAIT_SECONDS:
            self._wait = wait
        else:
            self._wait = _timing_env(
                WAIT_ENV,
                AUTONOMOUS_WAIT_SECONDS if self._autonomous else WAIT_SECONDS,
            )
        self._playbook = playbook
        self._recorder = recorder
        # Talking to SIRO puts the chat in front; bring the allowed game forward once per run.
        self._focus = os.environ.get("SIRO_COMPUTER_FOCUS", "1") != "0" if focus is None else focus
        self._demo: DemoRun | None = None
        self._demo_last: int | None = None
        self.process = ""  # program of the first allowed observation (key of its play notes)
        self.live: list[StepRecord] = []
        self._clock = clock
        self._screen_guard = os.environ.get("SIRO_COMPUTER_SCREEN_GUARD", "0") == "1"
        self.phase = "idle"
        self.strategy = ""  # short plan the model maintains across reactive steps

    @property
    def limits(self) -> dict[str, int | float | bool | None]:
        return {
            "max_steps": self._max_steps,
            "max_seconds": self._max_seconds,
            "autonomous": self._autonomous,
            "endless": self._endless,
        }

    async def run(self, goal: str) -> LoopReport:
        history = self.live = []
        self.phase = "observing"

        def end(state: str, reason: str, detail: str = "") -> LoopReport:
            self.phase = state
            if self._demo is not None:
                self._demo.finish(state, reason)
            return LoopReport(state, reason, tuple(history), detail)

        if not self._allowed:
            return end("stopped", "no_allowed_processes")
        started = self._clock()
        stop_generation = self._bridge.stop_generation
        no_change = invalid = rate_waits = waits = 0
        replan_used = False  # one replan after no-progress; second failure stops
        decide_soft_fails = 0
        task = goal
        if self._autonomous:
            task += _autonomous_hint()
        focus_tried = False
        done_seen = False
        before: Observation | None = None
        wait_before: Observation | None = None
        strategy = self.strategy
        step = 0
        while True:
            step += 1
            self.phase = "observing"
            if self._bridge.stop_generation != stop_generation:
                return end("stopped", "emergency_stop")
            if self._max_steps is not None and step > self._max_steps:
                return end("stopped", "step_limit")
            if self._max_seconds is not None and self._clock() - started > self._max_seconds:
                return end("stopped", "time_limit")
            observation, error = await self._bridge.observe()
            if self._bridge.stop_generation != stop_generation:
                return end("stopped", "emergency_stop")
            wrong_window = error == "window_not_visible" or (
                observation is not None
                and not observation.blocked_reason
                and observation.process not in self._allowed
            )
            if wrong_window:
                # Autonomous: keep bringing the game forward; never act on a non-allowed window.
                # focus_denied must not kill the segment — Windows often blocks SetForegroundWindow.
                if self._autonomous and self._focus:
                    target = self._focus_target(goal)
                    focus_result = await self._bridge.focus(target) if target else None
                    outcome = "ok"
                    seen = "allowed game not focused; bring it forward"
                    if target is None:
                        outcome = "denied:no_focus_target"
                    elif focus_result is not None and not focus_result.ok:
                        outcome = f"denied:{focus_result.error or 'focus_failed'}"
                        seen = f"restore selected target {target}"
                    history.append(
                        StepRecord(
                            step,
                            "(refocus)",
                            "",
                            outcome,
                            None,
                            seen,
                        )
                    )
                    await asyncio.sleep(0.6)
                    continue
                if self._focus and not focus_tried:
                    focus_tried = True
                    target = self._focus_target(goal)
                    if target:
                        focus_result = await self._bridge.focus(target)
                        if focus_result.ok:
                            await asyncio.sleep(0.8)
                            continue
                        history.append(
                            StepRecord(
                                step,
                                "(refocus)",
                                "",
                                f"denied:{focus_result.error or 'focus_failed'}",
                                None,
                                f"restore selected target {target}",
                            )
                        )
                        # One soft retry path: keep observing; do not end(target_focus_failed).
                        await asyncio.sleep(0.6)
                        continue
            if observation is None:
                return end("stopped", error)
            if observation.blocked_reason:
                return end("stopped", observation.blocked_reason)
            if observation.process not in self._allowed:
                return end("stopped", "window_not_allowed")
            if not is_fresh(observation, self._clock()):
                return end("stopped", "stale_observation")
            if wait_before is not None and history and history[-1].action == "(wait)":
                changed = _screen_changed(wait_before, observation)
                previous_wait = history[-1]
                history[-1] = StepRecord(
                    previous_wait.step,
                    previous_wait.action,
                    previous_wait.expect,
                    previous_wait.outcome,
                    changed,
                    previous_wait.seen,
                    previous_wait.scene,
                    previous_wait.detail,
                )
                wait_before = None
            if not self.process:
                self.process = observation.process
                if self._playbook is not None:
                    task = goal + notes_block(self._playbook.texts(self.process))
                    if self._autonomous:
                        task += _autonomous_hint()
                if self._recorder is not None:
                    self._demo = self._recorder.begin(self.process, goal)
            if before is not None and history and history[-1].screen_changed is None:
                updated, unresolved = await verify_step(self, before, observation, history[-1])
                history[-1] = updated
                changed, scene = updated.screen_changed, updated.scene
                no_change = no_change + 1 if unresolved else 0
                if changed is not None and self._demo is not None and self._demo_last is not None:
                    self._demo.set_changed(self._demo_last, changed)
                before = None
                stalled = _scene_not_advancing(history)
                if no_change >= MAX_NO_CHANGE or stalled:
                    why = (
                        "same scene/button without confirmed progress"
                        if stalled
                        else "repeated unresolved acts"
                    )
                    if not replan_used:
                        replan_used = True
                        no_change = 0
                        history.append(
                            StepRecord(
                                step,
                                "(replan)",
                                "",
                                "ok",
                                None,
                                "no confirmed progress; re-observe and replan",
                                scene,
                                why,
                            )
                        )
                        continue
                    return end("stopped", "stuck_no_progress", why)
            self.phase = "deciding"
            deadline = None
            try:
                if self._max_seconds is None:
                    budget = DECIDE_TIMEOUT_SECONDS
                else:
                    budget = self._max_seconds - (self._clock() - started)
                    if budget <= 0:
                        return end("stopped", "time_limit")
                decide_goal = decision_goal(
                    task, strategy, step, observation, history, refresh_every=STRATEGY_REFRESH_EVERY
                )
                async with asyncio.timeout(budget) as deadline:
                    decision = await self._decider.decide(
                        decide_goal, history, observation, strategy=strategy
                    )
            except TimeoutError as error:
                if self._bridge.stop_generation != stop_generation:
                    return end("stopped", "emergency_stop")
                if deadline is not None and deadline.expired():
                    if self._max_seconds is not None:
                        return end("stopped", "time_limit")
                    # Autonomous play: slow local VLMs must not kill the segment after 3 soft tries.
                    keep_trying = self._autonomous or decide_soft_fails < MAX_DECIDE_SOFT_FAILS
                    if keep_trying:
                        decide_soft_fails += 1
                        cap = "∞" if self._autonomous else str(MAX_DECIDE_SOFT_FAILS)
                        history.append(
                            StepRecord(
                                step,
                                "(recover)",
                                "",
                                "ok",
                                None,
                                "decider timeout; re-observe",
                                detail=f"soft {decide_soft_fails}/{cap}",
                            )
                        )
                        await asyncio.sleep(self._settle)
                        continue
                    return end("failed", "decider_error:timeout")
                return end("failed", f"decider_error:{error}")
            except CloudScreenNotAllowed:
                return end("stopped", "cloud_screen_not_allowed")
            except (DecisionError, OSError) as error:
                if self._bridge.stop_generation != stop_generation:
                    return end("stopped", "emergency_stop")
                keep_trying = self._autonomous or decide_soft_fails < MAX_DECIDE_SOFT_FAILS
                if keep_trying:
                    decide_soft_fails += 1
                    cap = "∞" if self._autonomous else str(MAX_DECIDE_SOFT_FAILS)
                    history.append(
                        StepRecord(
                            step,
                            "(recover)",
                            "",
                            "ok",
                            None,
                            f"decider error; re-observe ({error})",
                            detail=f"soft {decide_soft_fails}/{cap}",
                        )
                    )
                    await asyncio.sleep(self._settle)
                    continue
                return end("failed", f"decider_error:{error}")
            if self._bridge.stop_generation != stop_generation:
                return end("stopped", "emergency_stop")
            if self._max_seconds is not None and self._clock() - started >= self._max_seconds:
                return end("stopped", "time_limit")
            decide_soft_fails = 0
            new_strategy = decision.strategy.strip()
            if new_strategy and new_strategy != strategy:
                strategy = new_strategy
                self.strategy = strategy
                history.append(StepRecord(step, "(strategy)", "", "ok", None, strategy))
            decision, stop_reason, detail = decision_policy(
                decision, autonomous=self._autonomous, min_confidence=self._min_confidence
            )
            if stop_reason:
                return end("stopped", stop_reason, detail)
            if decision.kind == "wait":
                self.phase = "waiting"
                done_seen = False
                waits += 1
                history.append(
                    StepRecord(
                        step,
                        "(wait)",
                        decision.expect,
                        "ok",
                        None,
                        decision.seen,
                        decision.scene,
                        decision.uncertainty,
                    )
                )
                self._record(observation, decision, None)
                if waits > MAX_WAITS:
                    return end("stopped", "stuck_waiting", "too many waits without progress")
                before = None
                wait_before = observation
                await asyncio.sleep(self._wait)
                continue
            waits = 0
            if decision.kind == "done":
                if self._autonomous and self._endless:
                    done_seen = False
                    history.append(
                        StepRecord(
                            step,
                            "(keep playing)",
                            "",
                            "ok",
                            None,
                            decision.evidence or decision.seen or "checkpoint",
                            decision.scene,
                        )
                    )
                    await asyncio.sleep(self._settle)
                    continue
                if not decision.evidence.strip():
                    return end("stopped", "done_without_evidence")
                if done_seen:
                    return end("done", decision.evidence)
                done_seen = True
                before = None
                history.append(StepRecord(step, "(confirm done)", "", "ok", None))
                await asyncio.sleep(self._settle)
                continue
            done_seen = False
            action = self._checked_action(decision, observation, history=history)
            if isinstance(action, str):
                invalid += 1
                before = None
                history.append(
                    StepRecord(
                        step,
                        "(rejected)",
                        decision.expect,
                        f"invalid:{action}",
                        None,
                        decision.seen,
                        decision.scene,
                        action,
                    )
                )
                if invalid > MAX_INVALID:
                    if not replan_used:
                        replan_used = True
                        invalid = 0
                        history.append(
                            StepRecord(
                                step,
                                "(replan)",
                                "",
                                "ok",
                                None,
                                "too many invalid decisions; replan",
                                decision.scene,
                                action,
                            )
                        )
                        continue
                    return end(
                        "stopped",
                        "too_many_invalid_decisions",
                        "invalid acts persisted after replan",
                    )
                continue
            invalid = 0
            take_batch = getattr(self._decider, "take_batch", None)
            plan = take_batch(decision) if take_batch is not None else None
            if isinstance(plan, BatchPlan):

                async def batch_guard(original: Observation) -> tuple[Observation | None, str]:
                    return await self._wait_for_same_screen(original, started, stop_generation)

                def translate_batch(
                    item: InputAction, current: Observation, choice: Decision = decision
                ) -> InputAction | str:
                    return self._checked_action(
                        replace(choice, action=item), current, history=history
                    )

                self.phase = "acting_batch"
                batch = await execute_batch(
                    self._bridge,
                    plan,
                    observation,
                    allowed=self._allowed,
                    clock=self._clock,
                    deadline=None if self._max_seconds is None else started + self._max_seconds,
                    translate=translate_batch,
                    # A batch always uses the existing pixel/identity guard before each input.
                    guard=batch_guard,
                )
                before = None
                if batch.error or batch.final is None:
                    history.append(
                        StepRecord(
                            step,
                            "batch",
                            plan.expect,
                            "unknown" if batch.error == "outcome_unknown" else "denied",
                            None,
                            plan.seen,
                            plan.scene,
                            f"sent={len(batch.sent)}; {batch.error}",
                        )
                    )
                    return end("stopped", batch.error or "batch_unconfirmed")
                self.phase = "verifying"
                verify = await self._verify_expect(plan.expect, plan.seen, batch.final)
                if self._bridge.stop_generation != stop_generation or self._bridge.gate.tripped:
                    return end("stopped", "emergency_stop")
                changed = _screen_changed(observation, batch.final)
                confirmed = verify.status == "confirmed" and changed is True
                history.append(
                    StepRecord(
                        step,
                        "batch",
                        plan.expect,
                        "effective" if confirmed else "unconfirmed",
                        changed,
                        verify.seen or plan.seen,
                        verify.scene or plan.scene,
                        f"sent={len(batch.sent)}; " + verify.detail,
                    )
                )
                if not confirmed:
                    return end("stopped", "batch_unconfirmed", verify.detail)
                no_change = rate_waits = 0
                await asyncio.sleep(self._settle)
                continue
            if self._screen_guard:
                fresh, guard_error = await self._wait_for_same_screen(
                    observation, started, stop_generation
                )
                if fresh is None:
                    return end("stopped", guard_error)
                action = self._checked_action(decision, fresh, history=history)
                if isinstance(action, str):
                    return end("stopped", f"invalid:{action}")
            self.phase = "acting"
            result = await self._bridge.act(action)
            logged = _history_action(decision, observation, action)
            if not result.ok:
                if result.error == "rate_limited" and rate_waits < MAX_RATE_WAITS:
                    rate_waits += 1
                    await asyncio.sleep(RATE_WAIT_SECONDS)
                    continue
                if result.error == "outcome_unknown":
                    history.append(
                        StepRecord(
                            step,
                            logged,
                            decision.expect,
                            "unknown",
                            None,
                            decision.seen,
                            decision.scene,
                        )
                    )
                    return end("stopped", "outcome_unknown")
                history.append(
                    StepRecord(
                        step,
                        logged,
                        decision.expect,
                        f"denied:{result.error}",
                        None,
                        decision.seen,
                        decision.scene,
                        result.error,
                    )
                )
                return end("stopped", f"denied:{result.error}")
            rate_waits = 0
            # Delivered only — effectiveness is decided on the next observation.
            # Detail separates model image xy (in action string) from physical screen xy.
            map_detail = ""
            if action.x is not None and action.y is not None and observation.image_size is not None:
                w, h = observation.image_size
                rect = observation.image_rect
                map_detail = (
                    f"img {w}x{h} rect={list(rect) if rect else None} "
                    f"→ screen({action.x},{action.y})"
                )
            history.append(
                StepRecord(
                    step,
                    logged,
                    decision.expect,
                    "sent",
                    None,
                    decision.seen,
                    decision.scene,
                    map_detail,
                )
            )
            self._record(observation, decision, action)
            before = observation
            self.phase = "observing"
            await asyncio.sleep(self._settle)

    async def _wait_for_same_screen(
        self, original: Observation, started: float, stop_generation: int
    ) -> tuple[Observation | None, str]:
        return await wait_for_same_screen(
            self,
            original,
            started,
            stop_generation,
            wait_seconds=SCREEN_MATCH_WAIT_SECONDS,
            poll_seconds=SCREEN_MATCH_POLL_SECONDS,
        )

    async def _verify_expect(
        self, expect: str, before_seen: str, observation: Observation
    ) -> VerifyResult:
        return await verify_expect(self._decider, expect, before_seen, observation)

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

    def _checked_action(
        self,
        decision: Decision,
        observation: Observation,
        *,
        history: Sequence[StepRecord] | None = None,
    ) -> InputAction | str:
        return checked_action(decision, observation, history=history)
