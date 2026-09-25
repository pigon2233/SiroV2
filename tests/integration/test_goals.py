from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from siro.core.cognition import Goal, GoalService, GoalState
from siro.persistence.goals import SQLiteGoalRepository
from siro.persistence.sqlite import SQLiteStore

pytestmark = pytest.mark.asyncio


@dataclass
class FakeClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


async def goal_service(path: Path) -> tuple[GoalService, SQLiteGoalRepository, FakeClock]:
    store = SQLiteStore(path)
    await store.initialize()
    repository = SQLiteGoalRepository(store)
    clock = FakeClock(datetime(2026, 9, 24, tzinfo=UTC))
    return GoalService(repository, clock), repository, clock


async def test_goal_lifecycle_budget_and_revision_are_persistent(tmp_path: Path) -> None:
    service, repository, clock = await goal_service(tmp_path / "goals.sqlite3")
    goal = Goal(
        "goal-1",
        GoalState.PROPOSED,
        "first step",
        clock.now() + timedelta(minutes=2),
        max_steps=2,
        max_cost=3,
    )
    await service.propose(goal)
    ready = await service.transition(goal.goal_id, GoalState.READY)
    running = await service.transition(goal.goal_id, GoalState.RUNNING)
    assert (ready.revision, running.revision) == (2, 3)

    first = await service.spend(goal.goal_id, cost=1)
    second = await service.spend(goal.goal_id, cost=1)
    assert (first.steps_used, second.steps_used) == (1, 2)
    failed = await service.spend(goal.goal_id, cost=1)
    assert failed.state is GoalState.FAILED
    restored = await repository.get(goal.goal_id)
    assert restored == failed


async def test_deadline_and_illegal_transition_use_injected_clock(tmp_path: Path) -> None:
    service, _, clock = await goal_service(tmp_path / "goals.sqlite3")
    deadline = clock.now() + timedelta(seconds=1)
    await service.propose(Goal("goal-2", GoalState.PROPOSED, "step", deadline))
    with pytest.raises(ValueError, match="invalid goal transition"):
        await service.transition("goal-2", GoalState.COMPLETED)
    await service.transition("goal-2", GoalState.READY)
    await service.transition("goal-2", GoalState.RUNNING)
    clock.value = deadline
    expired = await service.spend("goal-2", cost=0)
    assert expired.state is GoalState.FAILED
