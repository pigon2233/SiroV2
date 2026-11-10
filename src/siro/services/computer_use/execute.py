"""Coordinate mapping and action validation only; actual input stays in ComputerBridge."""

from __future__ import annotations

from collections.abc import Sequence

from siro.services.computer_use.interface import Decision, StepRecord
from siro.services.computer_use.perception import Observation, image_to_screen
from siro.services.computer_use.safety import InputAction
from siro.services.computer_use.stuck import _click_ineffective_same_spot


def _normalize_image_xy(observation: Observation, x: int, y: int) -> tuple[int, int] | None:
    """Map model x/y into the downscaled screenshot, or None if unusable."""
    size = observation.image_size
    if size is None:
        return None
    if 0 <= x < size[0] and 0 <= y < size[1]:
        return x, y
    full = observation.image_rect
    if full is not None and full[2] > 0 and full[3] > 0 and 0 <= x < full[2] and 0 <= y < full[3]:
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


def checked_action(
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
