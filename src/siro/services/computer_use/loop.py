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
import math
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
    VerifyResult,
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
AUTONOMOUS_WAIT_SECONDS = 0.2
AUTONOMOUS_SETTLE_SECONDS = 0.15
SETTLE_ENV = "SIRO_COMPUTER_SETTLE"
WAIT_ENV = "SIRO_COMPUTER_WAIT"
DECIDE_TIMEOUT_SECONDS = 120.0  # local VLM on a busy 8GB GPU often needs >90s; soft-retry still applies
MAX_DECIDE_SOFT_FAILS = 3  # bounded runs only; endless autonomous keeps re-observing
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
        "Map: click only a reachable next node once; if the map description repeats, try another node. "
        "Do not reuse the same vague 'seen' sentence — describe what is new (combat/map/event/reward)."
    )


_CLICK_RE = re.compile(r"^click\((-?\d+),(-?\d+)")
SAME_CLICK_RADIUS = 80  # ban near-miss repeats (model often drifts ~50px on same wrong guess)
SAME_CLICK_LOOKBACK = 3  # any recent unresolved click near this spot counts
SCENE_STALL_LOOKBACK = 4  # same scene without an effective act ⇒ no progress


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
    if (
        action is not None
        and action.kind in {"move", "click"}
        and action.x is not None
        and action.y is not None
    ):
        xy = _normalize_image_xy(observation, action.x, action.y)
        if xy is not None:
            return f"{action.kind}({xy[0]},{xy[1]},{action.button})"
        return _describe(action)
    if action is not None:
        return _describe(action)
    return _describe(fallback)


def _last_real_click(history: Sequence[StepRecord]) -> StepRecord | None:
    for step in reversed(history):
        if step.action.startswith("("):
            continue
        if _parse_click_xy(step.action) is None:
            continue
        return step
    return None


def _click_ineffective_same_spot(
    history: Sequence[StepRecord],
    x: int,
    y: int,
    *,
    radius: int = SAME_CLICK_RADIUS,
    lookback: int = SAME_CLICK_LOOKBACK,
) -> bool:
    """Ban re-clicking near a recent unresolved click (ineffective / unconfirmed / etc.).

    Only a confirmed effective act after that miss clears the neighborhood ban.
    """
    checked = 0
    for step in reversed(history):
        if step.action.startswith("("):
            continue
        point = _parse_click_xy(step.action)
        if point is None:
            continue
        if step.outcome == "effective":
            return False
        unresolved = step.outcome in {
            "ineffective",
            "unconfirmed",
            "visual_change",
            "sent",
            "invalid:repeat_click",
        } or (step.outcome == "ok" and step.screen_changed is False)
        if not unresolved:
            checked += 1
            if checked >= lookback:
                return False
            continue
        px, py = point
        if (x - px) * (x - px) + (y - py) * (y - py) <= radius * radius:
            return True
        checked += 1
        if checked >= lookback:
            break
    return False


def _norm_label(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())[:80]


def _scene_not_advancing(history: Sequence[StepRecord], *, lookback: int = SCENE_STALL_LOOKBACK) -> bool:
    """True when several recent acts stay on the same scene without a confirmed expect."""
    acts = [s for s in history if not s.action.startswith("(") and s.scene.strip()]
    if len(acts) < lookback:
        return False
    recent = acts[-lookback:]
    if any(s.outcome == "effective" for s in recent):
        return False
    scenes = {_norm_label(s.scene) for s in recent}
    if len(scenes) != 1:
        return False
    # Same button spam: identical click strings while still unresolved.
    clicks = [s.action for s in recent if s.action.startswith("click")]
    if len(clicks) >= lookback - 1 and len(set(clicks)) == 1:
        return True
    return next(iter(scenes)) in {"menu", "pause", "unknown", "map", "shop"}


def _recovery_hint(decision: Decision) -> str:
    scene = (decision.scene or "").lower()
    seen = f"{decision.seen} {decision.targets}".lower()
    if scene == "pause" or "pause" in seen or "paused" in seen:
        return (
            "\n\nScene looks like a PAUSE menu. Click Resume/继续/返回 only. "
            "Do not click map/combat coords through the menu. Do not spam Escape."
        )
    if scene == "shop" or "shop" in seen or "商店" in seen:
        return (
            "\n\nScene looks like a SHOP. Click Leave/Proceed/离开/放弃 once. "
            "Do not re-buy the same item. Do not spam Escape."
        )
    if scene == "combat" or "combat" in seen or "energy" in seen:
        return (
            "\n\nCombat: if energy is 0 or no playable card, click End Turn / 结束回合. "
            "Otherwise play one affordable card and set expect to energy/hand/target change."
        )
    return (
        "\n\nPrevious act was ineffective. Re-identify scene from THIS frame, "
        "name concrete targets, and pick a different control. Do not spam Escape."
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
                changed = _screen_changed(before, observation)
                prev = history[-1]
                scene = prev.scene
                seen = prev.seen
                if changed is False:
                    outcome = "ineffective"
                    detail = f"no visual_change after expect={prev.expect or '-'}"
                    no_change += 1
                elif changed is True:
                    # Fingerprint only proves pixels moved — confirm expect on this frame.
                    outcome = "visual_change"
                    detail = "visual_change; verifying expect"
                    self.phase = "verifying"
                    verify = await self._verify_expect(prev.expect, prev.seen, observation)
                    scene = verify.scene or scene
                    seen = verify.seen or seen
                    if verify.status == "confirmed":
                        outcome = "effective"
                        detail = verify.detail or f"expect confirmed: {prev.expect}"
                        no_change = 0
                    elif verify.status == "denied":
                        outcome = "ineffective"
                        detail = verify.detail or f"expect not met: {prev.expect}"
                        no_change += 1
                    else:
                        outcome = "unconfirmed"
                        detail = verify.detail or "尚未確認"
                        no_change += 1
                else:
                    outcome = "unconfirmed"
                    detail = prev.detail or "尚未確認"
                    no_change += 1
                history[-1] = StepRecord(
                    prev.step,
                    prev.action,
                    prev.expect,
                    outcome,
                    changed,
                    seen,
                    scene,
                    detail,
                )
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
                decide_goal = task
                if not strategy or step == 1 or step % STRATEGY_REFRESH_EVERY == 0:
                    decide_goal += (
                        '\n\nThis turn: set JSON "strategy" to a short plan for this scene.'
                    )
                last_real = _last_real_click(history)
                if history and history[-1].action == "(replan)":
                    decide_goal += (
                        "\n\nREPLAN: previous acts made no visible progress. "
                        "Re-read THIS frame. Set scene/energy/targets/uncertainty carefully. "
                        "If uncertain, kind=wait. Do not spam Escape."
                    )
                elif last_real is not None and last_real.outcome in {
                    "ineffective",
                    "unconfirmed",
                    "visual_change",
                    "sent",
                }:
                    decide_goal += _recovery_hint(
                        Decision(
                            "act",
                            None,
                            last_real.expect,
                            "",
                            0.0,
                            "",
                            last_real.seen,
                            "",
                            last_real.scene,
                        )
                    )
                    decide_goal += (
                        "\nRe-locate the target on THIS frame and re-check screenshot coords "
                        f"(image is {observation.image_size}). Do not claim success without a new expect."
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
                history.append(
                    StepRecord(step, "(strategy)", "", "ok", None, strategy)
                )
            if decision.kind == "ask":
                if not self._autonomous:
                    return end("stopped", "needs_owner", decision.reason.strip()[:300])
                decision = Decision(
                    "wait",
                    None,
                    decision.expect or "reassess without asking",
                    decision.reason,
                    decision.confidence,
                    decision.evidence,
                    decision.seen,
                    decision.strategy,
                    decision.scene,
                    decision.energy,
                    decision.targets,
                    decision.uncertainty,
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
                    decision.scene,
                    decision.energy,
                    decision.targets,
                    decision.uncertainty,
                )
            if decision.uncertainty.strip() and decision.kind == "act":
                # Unreadable UI: observe again instead of guessing coordinates.
                decision = Decision(
                    "wait",
                    None,
                    "wait for a clearer frame; uncertainty set",
                    decision.reason,
                    decision.confidence,
                    decision.evidence,
                    decision.seen,
                    decision.strategy,
                    decision.scene,
                    decision.energy,
                    decision.targets,
                    decision.uncertainty,
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
                        decision.scene,
                        decision.energy,
                        decision.targets,
                        decision.uncertainty,
                    )
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
            if (
                action.x is not None
                and action.y is not None
                and observation.image_size is not None
            ):
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

    async def _verify_expect(
        self, expect: str, before_seen: str, observation: Observation
    ) -> VerifyResult:
        verify = getattr(self._decider, "verify", None)
        if verify is None:
            return VerifyResult("unknown", "尚未確認: no verifier")
        try:
            result = await verify(expect, before_seen, observation)
        except Exception as error:  # noqa: BLE001 — verify must never crash the run
            return VerifyResult("unknown", f"尚未確認: {type(error).__name__}")
        if isinstance(result, VerifyResult):
            return result
        return VerifyResult("unknown", "尚未確認: bad verify result")

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
            # Only block re-clicking the same spot after an ineffective click.
            if history is not None and _click_ineffective_same_spot(history, x, y):
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
