"""Deterministic attention, bounded workspace, and goal/action selection."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from siro.core.affect import CopingStrategy, DriveState, MoodState
from siro.core.goal_tasks import GoalTask


class Clock(Protocol):
    def now(self) -> datetime: ...


class GoalState(StrEnum):
    PROPOSED = "proposed"
    READY = "ready"
    RUNNING = "running"
    WAITING_EXTERNAL = "waiting_external"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Drive:
    drive_id: str
    pressure: float
    reason: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.drive_id or not self.reason or not 0 <= self.pressure <= 1:
            raise ValueError("drives require an id, reason, and normalized pressure")

    def attention_signal(self) -> AttentionSignal | None:
        if not self.enabled:
            return None
        return AttentionSignal(
            signal_id=f"drive:{self.drive_id}",
            urgency=0,
            user_relevance=0,
            novelty=0,
            goal_relevance=0,
            drive_relevance=self.pressure,
        )


@dataclass(frozen=True, slots=True)
class AttentionSignal:
    signal_id: str
    urgency: float
    user_relevance: float
    novelty: float
    goal_relevance: float
    drive_relevance: float
    explicit_user_input: bool = False
    control: str | None = None

    def __post_init__(self) -> None:
        values = (
            self.urgency,
            self.user_relevance,
            self.novelty,
            self.goal_relevance,
            self.drive_relevance,
        )
        if not self.signal_id or any(not 0 <= value <= 1 for value in values):
            raise ValueError("attention signals require an id and normalized scores")

    @property
    def score(self) -> float:
        return (
            0.35 * self.urgency
            + 0.25 * self.user_relevance
            + 0.15 * self.novelty
            + 0.15 * self.goal_relevance
            + 0.10 * self.drive_relevance
        )


@dataclass(frozen=True, slots=True)
class ActionCandidate:
    candidate_id: str
    capability: str
    arguments: dict[str, object]
    expected_result: str
    cost: float
    deadline: datetime | None
    score: float
    reasons: tuple[str, ...]
    permission_allowed: bool = True
    quiet_allowed: bool = True
    busy_allowed: bool = True
    cooldown_allowed: bool = True
    resources_allowed: bool = True

    @property
    def allowed(self) -> bool:
        return all(
            (
                self.permission_allowed,
                self.quiet_allowed,
                self.busy_allowed,
                self.cooldown_allowed,
                self.resources_allowed,
            )
        )


@dataclass(frozen=True, slots=True)
class Selection:
    candidate: ActionCandidate
    rejected: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class PlanningDecision:
    decision_id: str
    trace_id: str
    selected_candidate_id: str
    candidates: tuple[ActionCandidate, ...]
    rejected: tuple[tuple[str, str], ...]
    reasons: tuple[str, ...]
    decided_at: datetime


class PlanningRepository(Protocol):
    async def record(self, decision: PlanningDecision) -> None: ...


class Planner:
    def __init__(self, repository: PlanningRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def plan(
        self,
        trace_id: str,
        candidates: tuple[ActionCandidate, ...],
        do_nothing: ActionCandidate,
    ) -> PlanningDecision:
        if not trace_id:
            raise ValueError("planning requires a trace id")
        selection = select_action(candidates, do_nothing)
        decision = PlanningDecision(
            str(uuid4()),
            trace_id,
            selection.candidate.candidate_id,
            (*candidates, do_nothing),
            selection.rejected,
            selection.candidate.reasons,
            self._clock.now(),
        )
        await self._repository.record(decision)
        return decision


def select_attention(
    signals: tuple[AttentionSignal, ...], *, threshold: float = 0.6
) -> AttentionSignal | None:
    controls = [signal for signal in signals if signal.control in {"stop", "cancel"}]
    if controls:
        return min(controls, key=lambda signal: signal.signal_id)
    eligible = [
        signal for signal in signals if signal.explicit_user_input or signal.score >= threshold
    ]
    return max(eligible, key=lambda signal: (signal.score, signal.signal_id), default=None)


def select_action(
    candidates: tuple[ActionCandidate, ...], do_nothing: ActionCandidate
) -> Selection:
    rejected: list[tuple[str, str]] = []
    allowed: list[ActionCandidate] = []
    gates = (
        ("permission", "permission_allowed"),
        ("quiet", "quiet_allowed"),
        ("busy", "busy_allowed"),
        ("cooldown", "cooldown_allowed"),
        ("resources", "resources_allowed"),
    )
    for candidate in candidates:
        failures = [name for name, attribute in gates if not getattr(candidate, attribute)]
        if failures:
            rejected.append((candidate.candidate_id, ",".join(failures)))
        else:
            allowed.append(candidate)
    allowed.append(do_nothing)
    selected = max(allowed, key=lambda item: (item.score, item.candidate_id))
    return Selection(selected, tuple(rejected))


def affect_attention_signals(drives: DriveState, mood: MoodState) -> tuple[AttentionSignal, ...]:
    """Expose internal needs to attention without overriding explicit control."""
    signals = []
    for name in ("safety", "connection", "competence", "curiosity", "autonomy", "rest"):
        pressure = getattr(drives, name)
        if pressure >= 0.45:
            signals.append(
                AttentionSignal(
                    signal_id=f"affect-drive:{name}",
                    urgency=pressure if name in {"safety", "rest"} else pressure * 0.5,
                    user_relevance=0.0,
                    novelty=0.0,
                    goal_relevance=0.25,
                    drive_relevance=pressure,
                )
            )
    if mood.arousal >= 0.7:
        signals.append(
            AttentionSignal(
                "affect-mood:high-arousal",
                urgency=mood.arousal,
                user_relevance=0.0,
                novelty=0.0,
                goal_relevance=0.2,
                drive_relevance=0.2,
            )
        )
    return tuple(signals)


_COPING_CAPABILITIES: dict[CopingStrategy, frozenset[str]] = {
    CopingStrategy.SEEK_INFORMATION: frozenset({"inspect", "query", "read", "clarify"}),
    CopingStrategy.PROBLEM_SOLVE: frozenset({"fix", "retry", "execute", "act"}),
    CopingStrategy.REPAIR: frozenset({"apologize", "correct", "rollback", "repair"}),
    CopingStrategy.SEEK_SUPPORT: frozenset({"ask", "support", "notify"}),
    CopingStrategy.ACCEPT: frozenset({"wait", "pause", "none"}),
    CopingStrategy.PAUSE: frozenset({"wait", "pause", "none"}),
    CopingStrategy.SAVOR: frozenset({"record", "celebrate", "share"}),
    CopingStrategy.NONE: frozenset(),
}


def apply_affect_to_candidates(
    candidates: tuple[ActionCandidate, ...], strategy: CopingStrategy
) -> tuple[ActionCandidate, ...]:
    """Add a bounded coping bias while preserving every hard gate."""
    preferred = _COPING_CAPABILITIES[strategy]
    adjusted = []
    for candidate in candidates:
        terms = {term for term in candidate.capability.casefold().replace(".", "_").split("_")}
        match = bool(terms & preferred)
        delta = 0.12 if match else 0.0
        adjusted.append(
            ActionCandidate(
                candidate.candidate_id,
                candidate.capability,
                candidate.arguments,
                candidate.expected_result,
                candidate.cost,
                candidate.deadline,
                max(0.0, min(1.0, candidate.score + delta)),
                (*candidate.reasons, f"affect:{strategy.value}" if match else "affect:no_bias"),
                candidate.permission_allowed,
                candidate.quiet_allowed,
                candidate.busy_allowed,
                candidate.cooldown_allowed,
                candidate.resources_allowed,
            )
        )
    return tuple(adjusted)


@dataclass(frozen=True, slots=True)
class Goal:
    goal_id: str
    state: GoalState
    next_step: str | None
    deadline: datetime | None
    steps_used: int = 0
    max_steps: int = 8
    cost_used: float = 0
    max_cost: float = 0
    revision: int = 1
    task: GoalTask | None = None

    @property
    def budget_available(self) -> bool:
        step_ok = self.steps_used < self.max_steps
        cost_ok = self.max_cost == 0 or self.cost_used < self.max_cost
        return step_ok and cost_ok


class GoalRepository(Protocol):
    async def add(self, goal: Goal) -> None: ...

    async def get(self, goal_id: str) -> Goal | None: ...

    async def replace(self, goal: Goal, *, expected_revision: int) -> bool: ...


_GOAL_TRANSITIONS: dict[GoalState, frozenset[GoalState]] = {
    GoalState.PROPOSED: frozenset({GoalState.READY, GoalState.CANCELLED}),
    GoalState.READY: frozenset({GoalState.RUNNING, GoalState.CANCELLED}),
    GoalState.RUNNING: frozenset(
        {
            GoalState.WAITING_EXTERNAL,
            GoalState.COMPLETED,
            GoalState.FAILED,
            GoalState.CANCELLED,
        }
    ),
    GoalState.WAITING_EXTERNAL: frozenset({GoalState.READY, GoalState.FAILED, GoalState.CANCELLED}),
    GoalState.COMPLETED: frozenset(),
    GoalState.FAILED: frozenset(),
    GoalState.CANCELLED: frozenset(),
}


class GoalService:
    def __init__(self, repository: GoalRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def propose(self, goal: Goal) -> None:
        if goal.state is not GoalState.PROPOSED:
            raise ValueError("new goals must be proposed")
        await self._repository.add(goal)

    async def transition(self, goal_id: str, state: GoalState) -> Goal:
        goal = await self._required(goal_id)
        if state not in _GOAL_TRANSITIONS[goal.state]:
            raise ValueError(f"invalid goal transition: {goal.state} -> {state}")
        updated = replace(goal, state=state, revision=goal.revision + 1)
        if not await self._repository.replace(updated, expected_revision=goal.revision):
            raise RuntimeError("goal revision conflict")
        return updated

    async def spend(self, goal_id: str, *, cost: float) -> Goal:
        if cost < 0:
            raise ValueError("goal cost cannot be negative")
        goal = await self._required(goal_id)
        if goal.state is not GoalState.RUNNING:
            raise ValueError("only running goals can consume budget")
        if goal.deadline is not None and self._clock.now() >= goal.deadline:
            return await self.transition(goal_id, GoalState.FAILED)
        if not goal.budget_available or (goal.max_cost and goal.cost_used + cost > goal.max_cost):
            return await self.transition(goal_id, GoalState.FAILED)
        updated = replace(
            goal,
            steps_used=goal.steps_used + 1,
            cost_used=goal.cost_used + cost,
            revision=goal.revision + 1,
        )
        if not await self._repository.replace(updated, expected_revision=goal.revision):
            raise RuntimeError("goal revision conflict")
        return updated

    async def approve_task(self, goal_id: str, *, expected_revision: int) -> Goal:
        goal = await self._required(goal_id)
        if goal.state is not GoalState.PROPOSED or goal.task is None:
            raise ValueError("task is not awaiting approval")
        if goal.revision != expected_revision:
            raise RuntimeError("goal revision conflict")
        task = goal.task.model_copy(update={"approved_at": self._clock.now()})
        updated = replace(goal, state=GoalState.READY, task=task, revision=goal.revision + 1)
        if not await self._repository.replace(updated, expected_revision=goal.revision):
            raise RuntimeError("goal revision conflict")
        return updated

    async def checkpoint_task(self, goal_id: str, task: GoalTask, *, next_step: str | None) -> Goal:
        goal = await self._required(goal_id)
        if goal.task is None or goal.state not in {GoalState.RUNNING, GoalState.WAITING_EXTERNAL}:
            raise ValueError("task cannot be checkpointed")
        task = GoalTask.model_validate_json(task.model_dump_json())
        binding = ("profile", "owner_session_id", "workspace", "paths", "approved_at")
        if any(getattr(task, name) != getattr(goal.task, name) for name in binding):
            raise ValueError("approved task scope cannot change")
        if task.observations[: len(goal.task.observations)] != goal.task.observations:
            raise ValueError("task observations cannot be replaced")
        updated = replace(goal, task=task, next_step=next_step, revision=goal.revision + 1)
        if not await self._repository.replace(updated, expected_revision=goal.revision):
            raise RuntimeError("goal revision conflict")
        return updated

    async def _required(self, goal_id: str) -> Goal:
        goal = await self._repository.get(goal_id)
        if goal is None:
            raise KeyError(goal_id)
        return goal


class Workspace:
    def __init__(self) -> None:
        self.foreground: str | None = None
        self.goals: tuple[Goal, ...] = ()
        self.events: tuple[str, ...] = ()

    def update(
        self, *, foreground: str | None, goals: tuple[Goal, ...], events: tuple[str, ...]
    ) -> None:
        self.foreground = foreground
        self.goals = goals[:3]
        self.events = events[:20]
