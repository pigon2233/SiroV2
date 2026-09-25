"""SQLite goal lifecycle repository."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from siro.core.cognition import Goal, GoalState
from siro.persistence.sqlite import SQLiteStore


class SQLiteGoalRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def add(self, goal: Goal) -> None:
        await self._store.run_transaction(
            lambda connection: connection.execute(
                "INSERT INTO goals(goal_id, state, next_step, deadline, budget_json, revision) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                self._values(goal),
            )
        )

    async def get(self, goal_id: str) -> Goal | None:
        def read(connection: sqlite3.Connection) -> Goal | None:
            row = connection.execute("SELECT * FROM goals WHERE goal_id = ?", (goal_id,)).fetchone()
            if row is None:
                return None
            budget = json.loads(str(row["budget_json"]))
            return Goal(
                goal_id=str(row["goal_id"]),
                state=GoalState(str(row["state"])),
                next_step=row["next_step"],
                deadline=datetime.fromisoformat(str(row["deadline"])) if row["deadline"] else None,
                steps_used=int(budget["steps_used"]),
                max_steps=int(budget["max_steps"]),
                cost_used=float(budget["cost_used"]),
                max_cost=float(budget["max_cost"]),
                revision=int(row["revision"]),
            )

        return await self._store.run_transaction(read)

    async def replace(self, goal: Goal, *, expected_revision: int) -> bool:
        def write(connection: sqlite3.Connection) -> bool:
            return bool(
                connection.execute(
                    "UPDATE goals SET state = ?, next_step = ?, deadline = ?, budget_json = ?, "
                    "revision = ? WHERE goal_id = ? AND revision = ?",
                    (
                        goal.state,
                        goal.next_step,
                        goal.deadline.isoformat() if goal.deadline else None,
                        self._budget(goal),
                        goal.revision,
                        goal.goal_id,
                        expected_revision,
                    ),
                ).rowcount
            )

        return await self._store.run_transaction(write)

    @classmethod
    def _values(cls, goal: Goal) -> tuple[object, ...]:
        return (
            goal.goal_id,
            goal.state,
            goal.next_step,
            goal.deadline.isoformat() if goal.deadline else None,
            cls._budget(goal),
            goal.revision,
        )

    @staticmethod
    def _budget(goal: Goal) -> str:
        return json.dumps(
            {
                "steps_used": goal.steps_used,
                "max_steps": goal.max_steps,
                "cost_used": goal.cost_used,
                "max_cost": goal.max_cost,
            },
            separators=(",", ":"),
        )
