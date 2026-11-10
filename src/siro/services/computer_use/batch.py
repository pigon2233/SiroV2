"""Opt-in bounded turn-based click batches. Every click still passes the real bridge gate."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from siro.services.computer_use.bridge import BridgeResult
from siro.services.computer_use.decision import DecisionError
from siro.services.computer_use.ocr import OcrFrame
from siro.services.computer_use.perception import Observation, is_fresh
from siro.services.computer_use.safety import ControlGate, InputAction

BATCH_ENV = "SIRO_COMPUTER_ACTION_BATCH"
BATCH_PROCESSES_ENV = "SIRO_COMPUTER_BATCH_PROCESSES"
MAX_BATCH = 4


@dataclass(frozen=True, slots=True)
class BatchPlan:
    actions: tuple[InputAction, ...]
    expect: str
    seen: str
    confidence: float
    scene: str = "combat"


def parse_batch(text: str, frame: OcrFrame) -> BatchPlan:
    try:
        raw = json.loads(text)
    except ValueError as error:
        raise DecisionError("batch_not_json") from error
    if not isinstance(raw, dict) or raw.get("scene") != "combat" or raw.get("stable") is not True:
        raise DecisionError("batch_not_turn_based")
    ids = raw.get("ids")
    confidence = raw.get("confidence")
    expect = raw.get("expect")
    if (
        not isinstance(ids, list)
        or not 2 <= len(ids) <= MAX_BATCH
        or any(type(i) is not int for i in ids)
    ):
        raise DecisionError("batch_bad_ids")
    if len(set(ids)) != len(ids):
        raise DecisionError("batch_duplicate")
    if (
        not isinstance(confidence, (float, int))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        raise DecisionError("batch_bad_confidence")
    if not isinstance(expect, str) or not expect.strip():
        raise DecisionError("batch_missing_expect")
    by_id = {b.id: b for b in frame.blocks}
    actions = []
    for ident in ids:
        if ident not in by_id:
            raise DecisionError("batch_unknown_id")
        x, y = by_id[ident].center
        actions.append(InputAction("click", x=x, y=y, button="left"))
    if len({(a.x, a.y) for a in actions}) != len(actions):
        raise DecisionError("batch_duplicate_point")
    return BatchPlan(
        tuple(actions), expect[:300], str(raw.get("seen", ""))[:200], float(confidence)
    )


class BatchBridge(Protocol):
    gate: ControlGate

    @property
    def stop_generation(self) -> int: ...
    async def observe(self) -> tuple[Observation | None, str]: ...
    async def act(self, action: InputAction) -> BridgeResult: ...


@dataclass(frozen=True, slots=True)
class BatchResult:
    sent: tuple[InputAction, ...]
    final: Observation | None
    error: str = ""


def same_window(a: Observation, b: Observation) -> bool:
    return bool(
        a.window_id
        and a.pid
        and a.window_rect
        and a.image_rect
        and a.image_size
        and a.window_id == b.window_id
        and a.pid == b.pid
        and a.process == b.process
        and a.window_rect == b.window_rect
        and a.image_rect == b.image_rect
        and a.screen == b.screen
        and a.image_size == b.image_size
    )


async def execute_batch(
    bridge: BatchBridge,
    plan: BatchPlan,
    initial: Observation,
    *,
    allowed: frozenset[str],
    clock: Callable[[], float] = time.monotonic,
    deadline: float | None = None,
    translate: Callable[[InputAction, Observation], InputAction | str],
    guard: Callable[[Observation], Awaitable[tuple[Observation | None, str]]] | None = None,
) -> BatchResult:
    """No semantic intermediate verify; foreground/freshness/stop/gate remain per-input.

    Unknown delivery, denial, cancellation, rate limit or window change aborts the remainder.
    There is deliberately NO retry path and NO calls to gate.enable().
    """
    if not 2 <= len(plan.actions) <= MAX_BATCH:
        return BatchResult((), None, "batch_size")
    if any(
        a.kind != "click" or a.button != "left" or type(a.x) is not int or type(a.y) is not int
        for a in plan.actions
    ):
        return BatchResult((), None, "batch_kind")
    if len({(a.x, a.y) for a in plan.actions}) != len(plan.actions):
        return BatchResult((), None, "batch_duplicate_point")
    if initial.blocked_reason:
        return BatchResult((), None, initial.blocked_reason)
    generation = bridge.stop_generation
    sent: list[InputAction] = []

    def fence() -> str:
        if bridge.stop_generation != generation or bridge.gate.tripped:
            return "emergency_stop"
        if not bridge.gate.enabled:
            return "control_disabled"
        if deadline is not None and clock() >= deadline:
            return "time_limit"
        return ""

    async def observe() -> tuple[Observation | None, str]:
        error = fence()
        if error:
            return None, error
        budget = 6.0 if deadline is None else min(6.0, max(0.0, deadline - clock()))
        try:
            async with asyncio.timeout(budget):
                current, error = await bridge.observe()
        except TimeoutError:
            return None, "observe_timeout"
        if fence():
            return None, fence()
        if current is None:
            return None, error or "observe_failed"
        if current.blocked_reason:
            return None, current.blocked_reason
        if current.process not in allowed or not same_window(initial, current):
            return None, "window_changed"
        if not is_fresh(current, clock()):
            return None, "stale_observation"
        return current, ""

    for i, action in enumerate(plan.actions):
        current, error = await observe()
        if current is None:
            return BatchResult(tuple(sent), None, error)
        if guard is not None:
            current, error = await guard(initial if i == 0 else current)
            if current is None:
                return BatchResult(tuple(sent), None, error)
            if current.blocked_reason:
                return BatchResult(tuple(sent), None, current.blocked_reason)
            if (
                not same_window(initial, current)
                or current.process not in allowed
                or not is_fresh(current, clock())
            ):
                return BatchResult(tuple(sent), None, "window_changed")
        mapped = translate(action, current)
        if isinstance(mapped, str):
            return BatchResult(tuple(sent), None, "invalid:" + mapped)
        error = fence()
        if error:
            return BatchResult(tuple(sent), None, error)
        # The existing ComputerBridge.act() calls ControlGate.check() before any input queue.
        budget = 12.0 if deadline is None else min(12.0, max(0.0, deadline - clock()))
        try:
            async with asyncio.timeout(budget):
                result = await bridge.act(mapped)
        except TimeoutError:
            return BatchResult(tuple(sent), None, "outcome_unknown")
        if not result.ok:
            return BatchResult(tuple(sent), None, result.error or "denied")
        sent.append(mapped)
    final, error = await observe()
    return BatchResult(tuple(sent), final, error)
