"""Backend-independent decision prompts and policy; one shared Decider result type."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from siro.services.computer_use.interface import Decision, StepRecord
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.stuck import _last_real_click, _recovery_hint

KEEP_GROUNDED_ACT_ENV = "SIRO_COMPUTER_KEEP_GROUNDED_ACT"


def keep_grounded_act_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Owner opt-in; default OFF. Keeps a complete act when uncertainty is set."""
    return (os.environ if env is None else env).get(KEEP_GROUNDED_ACT_ENV, "0") == "1"


def _is_grounded_act(decision: Decision) -> bool:
    """True when the model already supplied a complete action, not a missing target."""
    action = decision.action
    if decision.kind != "act" or action is None:
        return False
    if action.kind in {"click", "move"}:
        return action.x is not None and action.y is not None
    if action.kind == "key":
        return bool(action.key.strip())
    if action.kind == "type":
        return bool(action.text)
    if action.kind == "scroll":
        return action.amount != 0
    return False


def decision_goal(
    task: str,
    strategy: str,
    step: int,
    observation: Observation,
    history: Sequence[StepRecord],
    *,
    refresh_every: int,
) -> str:
    decide_goal = task
    if not strategy or step == 1 or step % refresh_every == 0:
        decide_goal += '\n\nThis turn: set JSON "strategy" to a short plan for this scene.'
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
    return decide_goal


def decision_policy(
    decision: Decision,
    *,
    autonomous: bool,
    min_confidence: float,
    keep_grounded_act: bool | None = None,
) -> tuple[Decision, str, str]:
    if keep_grounded_act is None:
        keep_grounded_act = keep_grounded_act_enabled()
    if decision.kind == "ask":
        if not autonomous:
            return decision, "needs_owner", decision.reason.strip()[:300]
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
        if not autonomous:
            return decision, "decider_stuck", ""
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
    # Default: any non-empty uncertainty forces wait, including a complete
    # click whose uncertainty is only about other UI (2026-11-14 STS2 title).
    # Opt-in keeps the grounded act; model-chosen waits and incomplete acts
    # still wait. This is not a safety-gate change.
    if (
        decision.uncertainty.strip()
        and decision.kind == "act"
        and not (keep_grounded_act and _is_grounded_act(decision))
    ):
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
    if decision.confidence < min_confidence and decision.kind != "wait":
        if not autonomous:
            return decision, "low_confidence", ""
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
    return decision, "", ""
