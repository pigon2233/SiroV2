"""Perceive -> decide -> gate -> act -> re-perceive, with hard stops instead of guessing.

The loop never trusts a decision blindly: coordinates must lie in the focused window, the window
must be on the owner's allowlist, "done" needs proof confirmed on a second fresh observation, an
unchanged screen after an action counts toward "stuck", and an unknown outcome halts (no resend).
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import io
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from PIL import Image

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
AUTONOMOUS_WAIT_SECONDS = 0.35
AUTONOMOUS_SETTLE_SECONDS = 0.15
DECIDE_TIMEOUT_SECONDS = 35.0  # per decision when the run itself has no wall clock
STRATEGY_REFRESH_EVERY = 8  # ask the model to refresh the short plan this often
SCREEN_MATCH_WAIT_SECONDS = 30.0
SCREEN_MATCH_POLL_SECONDS = 0.4
AUTONOMOUS_FLAG = "SIRO_COMPUTER_AUTONOMOUS"  # 1 = never stop to ask the owner
ENDLESS_FLAG = "SIRO_COMPUTER_ENDLESS"


def _pixel_digest(observation: Observation) -> bytes | None:
    if not observation.image_png_b64 or not observation.image_size:
        return None
    try:
        raw = base64.b64decode(observation.image_png_b64, validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"PNG", "JPEG"} or image.size != observation.image_size:
                return None
            if image.width * image.height > 16_000_000:
                return None
            image.load()
            return hashlib.sha256(image.convert("RGBA").tobytes()).digest()
    except (binascii.Error, OSError, ValueError, Image.DecompressionBombError):
        return None


def _same_target(a: Observation, b: Observation) -> bool:
    return bool(
        a.window_id
        and a.pid
        and a.window_rect
        and a.image_rect
        and a.window_id == b.window_id
        and a.pid == b.pid
        and a.process == b.process
        and a.window_rect == b.window_rect
        and a.screen == b.screen
        and a.image_rect == b.image_rect
        and a.image_size == b.image_size
        and a.window_title == b.window_title
    )


def _screen_changed(a: Observation, b: Observation) -> bool | None:
    """Compare only observations that identify the same target and have fingerprints."""
    if not _same_target(a, b) or not a.image_size or not a.fingerprint or not b.fingerprint:
        return None
    return a.fingerprint != b.fingerprint


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


def _autonomous_hint() -> str:
    return (
        "\n\nOwner autonomous mode is ON: never answer kind=ask. Prefer a quick act. "
        "If you see defeat/death/game over/retry/continue/play again, click that button "
        "once immediately and keep playing a new run. Do not stop after a loss. "
        "Do not answer kind=done just because a run ended — click through and continue. "
        "Combat: if energy is 0 or no playable cards, click End Turn / 结束回合 immediately. "
        "Map: click only a reachable next node once; if the map description repeats, try another node. "
        "Do not reuse the same vague 'seen' sentence — describe what is new (combat/map/event/reward)."
    )


def _norm_seen(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())[:70]


def _seen_stuck(history: list[StepRecord], *, lookback: int = 3) -> bool:
    """True when recent acts keep repeating the same vague screen description."""
    acts = [s for s in history if not s.action.startswith("(")]
    if len(acts) < lookback:
        return False
    recent = acts[-lookback:]
    texts = [_norm_seen(s.seen) for s in recent if s.seen.strip()]
    if len(texts) < lookback:
        return False
    return len(set(texts)) == 1 and all(s.outcome == "ok" for s in recent)


_CLICK_RE = re.compile(r"^click\((-?\d+),(-?\d+)")
REPEAT_CLICK_RADIUS = 36  # always reject near-identical hammering
STUCK_CLICK_RADIUS = 140  # when seen-text is stuck, ban the whole local region


def _parse_click_xy(action: str) -> tuple[int, int] | None:
    match = _CLICK_RE.match(action)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _normalize_image_xy(
    observation: Observation, x: int, y: int
) -> tuple[int, int] | None:
    """Map model x/y into the downscaled screenshot, or None if unusable."""
    size = observation.image_size
    if size is None:
        return None
    if 0 <= x < size[0] and 0 <= y < size[1]:
        return x, y
    full = observation.image_rect
    if (
        full is not None
        and full[2] > 0
        and full[3] > 0
        and 0 <= x < full[2]
        and 0 <= y < full[3]
    ):
        nx = round(x * size[0] / full[2])
        ny = round(y * size[1] / full[3])
        if 0 <= nx < size[0] and 0 <= ny < size[1]:
            return nx, ny
    return None


def _history_action(decision: Decision, observation: Observation, fallback: InputAction) -> str:
    """Prefer screenshot-pixel click coords (after normalization) for the model history."""
    action = decision.action
    if action is not None and action.kind in {"move", "click"} and action.x is not None and action.y is not None:
        xy = _normalize_image_xy(observation, action.x, action.y)
        if xy is not None:
            return f"{action.kind}({xy[0]},{xy[1]},{action.button})"
        return _describe(action)
    if action is not None:
        return _describe(action)
    return _describe(fallback)


def _recent_ok_clicks(history: Sequence[StepRecord], *, limit: int = 5) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for step in reversed(history):
        if step.outcome != "ok":
            continue
        point = _parse_click_xy(step.action)
        if point is None:
            continue
        points.append(point)
        if len(points) >= limit:
            break
    return points


def _click_too_close(
    history: Sequence[StepRecord], x: int, y: int, *, radius: int = REPEAT_CLICK_RADIUS
) -> bool:
    """Reject hammering the same spot when the model is stuck."""
    for px, py in _recent_ok_clicks(history):
        if (x - px) * (x - px) + (y - py) * (y - py) <= radius * radius:
            return True
    return False


def _overlay_seen(seen: str) -> bool:
    text = seen.lower()
    return any(
        token in text
        for token in (
            "shop",
            "overlay",
            "panel",
            "modal",
            "dialog",
            "popup",
            "商店",
            "面板",
            "弹窗",
            "彈窗",
        )
    )


def _banned_clicks_text(history: Sequence[StepRecord]) -> str:
    points = _recent_ok_clicks(history, limit=4)
    if not points:
        return ""
    joined = ", ".join(f"({x},{y})" for x, y in points)
    return (
        f"\n\nDo NOT click near these recent screenshot spots "
        f"(stay >{STUCK_CLICK_RADIUS}px away): {joined}. "
        "Click a clearly different control (door/node/End Turn/Leave). "
        "If combat with 0 energy, click End Turn / 结束回合."
    )


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
            self._settle = AUTONOMOUS_SETTLE_SECONDS if self._autonomous else SETTLE_SECONDS
        if wait != WAIT_SECONDS:
            self._wait = wait
        else:
            self._wait = AUTONOMOUS_WAIT_SECONDS if self._autonomous else WAIT_SECONDS
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
        stuck_escape_used = False  # at most one forced Escape per run — never spam Esc

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
                if self._autonomous and self._focus:
                    target = self._focus_target(goal)
                    if target:
                        await self._bridge.focus(target)
                    history.append(
                        StepRecord(
                            step,
                            "(refocus)",
                            "",
                            "ok",
                            None,
                            "allowed game not focused; bring it forward",
                        )
                    )
                    await asyncio.sleep(0.6)
                    continue
                if self._focus and not focus_tried:
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
            if wait_before is not None and history and history[-1].action == "(wait)":
                changed = _screen_changed(wait_before, observation)
                previous_wait = history[-1]
                history[-1] = StepRecord(
                    previous_wait.step, previous_wait.action, previous_wait.expect,
                    previous_wait.outcome, changed, previous_wait.seen,
                )  # fmt: skip
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
                changed = _screen_changed(before, observation)
                history[-1] = StepRecord(
                    history[-1].step, history[-1].action, history[-1].expect,
                    history[-1].outcome, changed, history[-1].seen,
                )  # fmt: skip
                if changed is not None and self._demo is not None and self._demo_last is not None:
                    self._demo.set_changed(self._demo_last, changed)
                no_change = no_change + 1 if changed is False else 0
                before = None
                if no_change >= MAX_NO_CHANGE:
                    if self._autonomous:
                        no_change = 0
                        history.append(
                            StepRecord(
                                step,
                                "(unstick)",
                                "",
                                "ok",
                                None,
                                "no visible change; try another act",
                            )
                        )
                        continue
                    return end("stopped", "stuck_no_visible_change")
            if _seen_stuck(history) and (not history or history[-1].action != "(unstick)"):
                history.append(
                    StepRecord(
                        step,
                        "(unstick)",
                        "",
                        "ok",
                        None,
                        "same seen text repeated; re-describe this frame and act differently",
                    )
                )
            self.phase = "deciding"
            deadline = None
            try:
                if self._max_seconds is None:
                    budget = DECIDE_TIMEOUT_SECONDS
                else:
                    budget = self._max_seconds - (self._clock() - started)
                    if budget <= 0:
                        return end("stopped", "time_limit")
                decide_goal = task
                if not strategy or step == 1 or step % STRATEGY_REFRESH_EVERY == 0:
                    decide_goal += (
                        '\n\nThis turn: set JSON "strategy" to a short plan for this scene.'
                    )
                if history and history[-1].action == "(unstick)":
                    decide_goal += (
                        "\n\nIMPORTANT: previous clicks did nothing useful. "
                        "Update seen to match THIS frame. Pick a clearly different control."
                    )
                    decide_goal += _banned_clicks_text(history)
                elif _seen_stuck(history, lookback=2):
                    decide_goal += _banned_clicks_text(history)
                async with asyncio.timeout(budget) as deadline:
                    decision = await self._decider.decide(
                        decide_goal, history, observation, strategy=strategy
                    )
            except TimeoutError as error:
                if self._bridge.stop_generation != stop_generation:
                    return end("stopped", "emergency_stop")
                if deadline is not None and deadline.expired():
                    if self._max_seconds is None:
                        return end("failed", "decider_error:timeout")
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
            if self._max_seconds is not None and self._clock() - started >= self._max_seconds:
                return end("stopped", "time_limit")
            new_strategy = decision.strategy.strip()
            if new_strategy and new_strategy != strategy:
                strategy = new_strategy
                self.strategy = strategy
                history.append(
                    StepRecord(step, "(strategy)", "", "ok", None, strategy)
                )
            if decision.kind == "ask":
                if not self._autonomous:
                    return end("stopped", "needs_owner", decision.reason.strip()[:300])
                # Autonomous: never interrupt the owner — wait and look again.
                decision = Decision(
                    "wait",
                    None,
                    decision.expect or "reassess without asking",
                    decision.reason,
                    decision.confidence,
                    decision.evidence,
                    decision.seen,
                    decision.strategy,
                )
            if decision.kind == "stuck":
                if not self._autonomous:
                    return end("stopped", "decider_stuck")
                decision = Decision(
                    "wait",
                    None,
                    "try a different act after a short wait",
                    decision.reason,
                    decision.confidence,
                    decision.evidence,
                    decision.seen,
                    decision.strategy,
                )
            if (
                decision.confidence < self._min_confidence
                and decision.kind != "wait"
            ):
                if not self._autonomous:
                    return end("stopped", "low_confidence")
                if decision.kind != "act" or decision.action is None:
                    decision = Decision(
                        "wait",
                        None,
                        decision.expect or "uncertain; wait then retry",
                        decision.reason,
                        decision.confidence,
                        decision.evidence,
                        decision.seen,
                        decision.strategy,
                    )
                # else: keep the low-confidence act and execute it below
            if decision.kind == "wait":
                self.phase = "waiting"
                done_seen = False
                waits += 1
                history.append(
                    StepRecord(step, "(wait)", decision.expect, "ok", None, decision.seen)
                )
                self._record(observation, decision, None)
                if waits > MAX_WAITS:
                    if self._autonomous:
                        waits = 0
                    else:
                        return end("stopped", "stuck_waiting")
                before = None
                wait_before = observation
                await asyncio.sleep(self._wait)
                continue
            waits = 0
            if decision.kind == "done":
                if self._autonomous and self._endless:
                    # Open-ended play: treat "done" as a soft checkpoint and keep going.
                    done_seen = False
                    history.append(
                        StepRecord(
                            step,
                            "(keep playing)",
                            "",
                            "ok",
                            None,
                            decision.evidence or decision.seen or "checkpoint",
                        )
                    )
                    await asyncio.sleep(self._settle)
                    continue
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
                    )
                )
                if (
                    action == "repeat_click"
                    and self._autonomous
                    and not stuck_escape_used
                    and _overlay_seen(decision.seen)
                ):
                    # One Escape per run only, and only when the model itself reports a shop/panel.
                    stuck_escape_used = True
                    escape = InputAction(
                        kind="key",
                        key="Escape",
                        focus_is_secret=observation.focus_is_secret,
                    )
                    self.phase = "acting"
                    result = await self._bridge.act(escape)
                    outcome = "ok" if result.ok else f"denied:{result.error}"
                    history.append(
                        StepRecord(
                            step,
                            _describe(escape),
                            "dismiss stuck shop/overlay once",
                            outcome,
                            None,
                            decision.seen,
                        )
                    )
                    if result.ok:
                        invalid = 0
                        before = observation
                        await asyncio.sleep(self._settle)
                        continue
                    if result.error == "outcome_unknown":
                        return end("stopped", "outcome_unknown")
                if invalid > MAX_INVALID:
                    if self._autonomous:
                        invalid = 0
                        continue
                    return end("stopped", "too_many_invalid_decisions")
                continue
            invalid = 0
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
            # History keeps screenshot-pixel coords so the model is not trained on desktop coords.
            logged = _history_action(decision, observation, action)
            if not result.ok:
                if result.error == "rate_limited" and rate_waits < MAX_RATE_WAITS:
                    rate_waits += 1
                    await asyncio.sleep(RATE_WAIT_SECONDS)
                    continue
                if result.error == "outcome_unknown":
                    history.append(
                        StepRecord(step, logged, decision.expect, "unknown", None)
                    )
                    return end("stopped", "outcome_unknown")
                history.append(
                    StepRecord(
                        step, logged, decision.expect, f"denied:{result.error}", None
                    )
                )
                return end("stopped", f"denied:{result.error}")
            rate_waits = 0
            history.append(
                StepRecord(step, logged, decision.expect, "ok", None, decision.seen)
            )
            self._record(observation, decision, action)
            before = observation
            self.phase = "observing"
            await asyncio.sleep(self._settle)

    async def _wait_for_same_screen(
        self, original: Observation, started: float, stop_generation: int
    ) -> tuple[Observation | None, str]:
        """Reobserve before an unexecuted action; never resend an ambiguous action."""
        digest = await asyncio.to_thread(_pixel_digest, original)
        if digest is None or not _same_target(original, original):
            return None, "screen_guard_unavailable"
        self.phase = "waiting_for_matching_screen"
        watch_start = self._clock()
        while True:
            if self._bridge.stop_generation != stop_generation or self._bridge.gate.tripped:
                return None, "emergency_stop"
            if not self._bridge.gate.enabled:
                return None, "control_disabled"
            elapsed = self._clock() - started
            guard_left = SCREEN_MATCH_WAIT_SECONDS - (self._clock() - watch_start)
            if self._max_seconds is None:
                remaining = guard_left
                hit_time_limit = False
            else:
                remaining = min(self._max_seconds - elapsed, guard_left)
                hit_time_limit = elapsed >= self._max_seconds
            if remaining <= 0:
                return None, "time_limit" if hit_time_limit else "screen_not_restored"
            try:
                async with asyncio.timeout(remaining):
                    current, error = await self._bridge.observe()
            except TimeoutError:
                timed_out = (
                    self._max_seconds is not None
                    and self._clock() - started >= self._max_seconds
                )
                return None, "time_limit" if timed_out else "screen_not_restored"
            if self._bridge.stop_generation != stop_generation or self._bridge.gate.tripped:
                return None, "emergency_stop"
            if current is None:
                return None, error
            if current.blocked_reason:
                return None, current.blocked_reason
            if current.process not in self._allowed or not _same_target(original, current):
                return None, "window_changed"
            if not is_fresh(current, self._clock()):
                return None, "stale_observation"
            current_digest = await asyncio.to_thread(_pixel_digest, current)
            if self._bridge.stop_generation != stop_generation or self._bridge.gate.tripped:
                return None, "emergency_stop"
            if not self._bridge.gate.enabled:
                return None, "control_disabled"
            if self._max_seconds is not None and self._clock() - started >= self._max_seconds:
                return None, "time_limit"
            if self._clock() - watch_start >= SCREEN_MATCH_WAIT_SECONDS:
                return None, "screen_not_restored"
            if not is_fresh(current, self._clock()):
                return None, "stale_observation"
            if current_digest is None:
                return None, "screen_guard_unavailable"
            if current_digest == digest:
                return current, ""
            await asyncio.sleep(min(SCREEN_MATCH_POLL_SECONDS, remaining))

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
        action = decision.action
        if action is None:
            return "no_action"
        x, y = action.x, action.y
        if x is not None and y is not None:
            if observation.image_size is None:
                return "no_image_size"
            normalized = _normalize_image_xy(observation, x, y)
            if normalized is None:
                return "outside_image"
            x, y = normalized
            # Ban near-duplicates in screenshot space (same space the model / history use).
            if history is not None:
                radius = (
                    STUCK_CLICK_RADIUS
                    if _seen_stuck(list(history), lookback=2)
                    else REPEAT_CLICK_RADIUS
                )
                if _click_too_close(history, x, y, radius=radius):
                    return "repeat_click"
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
