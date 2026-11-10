"""Fresh observation identity, fingerprints and optional pre-input pixel guard."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import io
from collections.abc import Callable
from typing import Protocol

from PIL import Image

from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.perception import Observation, is_fresh


class ObservationContext(Protocol):
    _bridge: ComputerBridge
    _clock: Callable[[], float]
    _allowed: frozenset[str]
    _max_seconds: float | None
    phase: str


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


async def wait_for_same_screen(
    context: ObservationContext,
    original: Observation,
    started: float,
    stop_generation: int,
    *,
    wait_seconds: float,
    poll_seconds: float,
) -> tuple[Observation | None, str]:
    """Reobserve before an unexecuted action; never resend an ambiguous action."""
    digest = await asyncio.to_thread(_pixel_digest, original)
    if digest is None or not _same_target(original, original):
        return None, "screen_guard_unavailable"
    context.phase = "waiting_for_matching_screen"
    watch_start = context._clock()
    while True:
        if context._bridge.stop_generation != stop_generation or context._bridge.gate.tripped:
            return None, "emergency_stop"
        if not context._bridge.gate.enabled:
            return None, "control_disabled"
        elapsed = context._clock() - started
        guard_left = wait_seconds - (context._clock() - watch_start)
        if context._max_seconds is None:
            remaining = guard_left
            hit_time_limit = False
        else:
            remaining = min(context._max_seconds - elapsed, guard_left)
            hit_time_limit = elapsed >= context._max_seconds
        if remaining <= 0:
            return None, "time_limit" if hit_time_limit else "screen_not_restored"
        try:
            async with asyncio.timeout(remaining):
                current, error = await context._bridge.observe()
        except TimeoutError:
            timed_out = (
                context._max_seconds is not None
                and context._clock() - started >= context._max_seconds
            )
            return None, "time_limit" if timed_out else "screen_not_restored"
        if context._bridge.stop_generation != stop_generation or context._bridge.gate.tripped:
            return None, "emergency_stop"
        if current is None:
            return None, error
        if current.blocked_reason:
            return None, current.blocked_reason
        if current.process not in context._allowed or not _same_target(original, current):
            return None, "window_changed"
        if not is_fresh(current, context._clock()):
            return None, "stale_observation"
        current_digest = await asyncio.to_thread(_pixel_digest, current)
        if context._bridge.stop_generation != stop_generation or context._bridge.gate.tripped:
            return None, "emergency_stop"
        if not context._bridge.gate.enabled:
            return None, "control_disabled"
        if context._max_seconds is not None and context._clock() - started >= context._max_seconds:
            return None, "time_limit"
        if context._clock() - watch_start >= wait_seconds:
            return None, "screen_not_restored"
        if not is_fresh(current, context._clock()):
            return None, "stale_observation"
        if current_digest is None:
            return None, "screen_guard_unavailable"
        if current_digest == digest:
            return current, ""
        await asyncio.sleep(min(poll_seconds, remaining))
