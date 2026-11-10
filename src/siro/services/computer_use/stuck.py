"""Pure bounded no-progress/re-click strategies; no provider or input access."""

from __future__ import annotations

import re
from collections.abc import Sequence

from siro.services.computer_use.interface import Decision, StepRecord

_CLICK_RE = re.compile(r"^click\((-?\d+),(-?\d+)")
SAME_CLICK_RADIUS = 80
SAME_CLICK_LOOKBACK = 3
SCENE_STALL_LOOKBACK = 4


def _parse_click_xy(action: str) -> tuple[int, int] | None:
    match = _CLICK_RE.match(action)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


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


def _scene_not_advancing(
    history: Sequence[StepRecord], *, lookback: int = SCENE_STALL_LOOKBACK
) -> bool:
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
