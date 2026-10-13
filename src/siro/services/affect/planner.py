"""Planner facade that consumes persisted affect without weakening gates."""

from __future__ import annotations

from siro.core.cognition import (
    ActionCandidate,
    AttentionSignal,
    Planner,
    PlanningDecision,
    affect_attention_signals,
    apply_affect_to_candidates,
    select_attention,
)
from siro.persistence.affect import SQLiteAffectRepository


class AffectDecisionLoop:
    """Canonical product boundary for attention and action selection.

    Product event loops call this facade instead of combining the core
    selectors themselves.  A missing attention winner produces no action;
    explicit stop/cancel remains the first-class winner in core attention.
    """

    def __init__(
        self,
        planner: AffectAwarePlanner,
        attention: AffectAwareAttention,
    ) -> None:
        self._planner = planner
        self._attention = attention

    async def decide(
        self,
        session_id: str,
        trace_id: str,
        signals: tuple[AttentionSignal, ...],
        candidates: tuple[ActionCandidate, ...],
        do_nothing: ActionCandidate,
    ) -> tuple[AttentionSignal, PlanningDecision] | None:
        attended = await self._attention.select(session_id, signals)
        if attended is None:
            return None
        eligible = () if attended.control in {"stop", "cancel"} else candidates
        decision = await self._planner.plan(session_id, trace_id, eligible, do_nothing)
        return attended, decision


class AffectAwarePlanner:
    def __init__(
        self,
        planner: Planner,
        affect: SQLiteAffectRepository,
        *,
        identity_id: str = "siro",
    ) -> None:
        self._planner = planner
        self._affect = affect
        self._identity_id = identity_id

    async def plan(
        self,
        session_id: str,
        trace_id: str,
        candidates: tuple[ActionCandidate, ...],
        do_nothing: ActionCandidate,
    ) -> PlanningDecision:
        coping = await self._affect.latest_coping(self._identity_id, session_id)
        adjusted = candidates if coping is None else apply_affect_to_candidates(candidates, coping)
        return await self._planner.plan(trace_id, adjusted, do_nothing)


class AffectAwareAttention:
    def __init__(
        self,
        affect: SQLiteAffectRepository,
        *,
        identity_id: str = "siro",
        threshold: float = 0.35,
    ) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("attention threshold must be within [0, 1]")
        self._affect = affect
        self._identity_id = identity_id
        self._threshold = threshold

    async def select(
        self, session_id: str, external: tuple[AttentionSignal, ...]
    ) -> AttentionSignal | None:
        mood, drives = await self._affect.dynamics(self._identity_id, session_id)
        internal = () if mood is None or drives is None else affect_attention_signals(drives, mood)
        return select_attention((*external, *internal), threshold=self._threshold)
