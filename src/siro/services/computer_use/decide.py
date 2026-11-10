"""Backend-independent decision prompts and policy; one shared Decider result type."""

from __future__ import annotations

from collections.abc import Sequence

from siro.services.computer_use.interface import Decision, StepRecord
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.stuck import _last_real_click, _recovery_hint


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
    decision: Decision, *, autonomous: bool, min_confidence: float
) -> tuple[Decision, str, str]:
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
