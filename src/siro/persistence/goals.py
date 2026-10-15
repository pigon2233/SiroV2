"""SQLite goal lifecycle repository."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from siro.core.cognition import Goal, GoalState
from siro.core.goal_tasks import GoalTask
from siro.persistence.sqlite import SQLiteStore


class SQLiteGoalRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def add(self, goal: Goal) -> None:
        def write(connection: sqlite3.Connection) -> None:
            if goal.task is not None:
                count = connection.execute(
                    "SELECT count(*) FROM goals WHERE task_json IS NOT NULL "
                    "AND json_extract(task_json, '$.profile') = 'document-checklist-v1'"
                ).fetchone()[0]
                if count >= 20:
                    raise OverflowError("task history capacity reached")
            connection.execute(
                "INSERT INTO goals(goal_id, state, next_step, deadline, budget_json, revision, "
                "task_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                self._values(goal),
            )

        await self._store.run_transaction(write)

    async def get(self, goal_id: str) -> Goal | None:
        def read(connection: sqlite3.Connection) -> Goal | None:
            row = connection.execute("SELECT * FROM goals WHERE goal_id = ?", (goal_id,)).fetchone()
            if row is None:
                return None
            return self._goal(row)

        return await self._store.run_transaction(read)

    async def replace(self, goal: Goal, *, expected_revision: int) -> bool:
        def write(connection: sqlite3.Connection) -> bool:
            return bool(
                connection.execute(
                    "UPDATE goals SET state = ?, next_step = ?, deadline = ?, budget_json = ?, "
                    "revision = ?, task_json = ? WHERE goal_id = ? AND revision = ?",
                    (
                        goal.state,
                        goal.next_step,
                        goal.deadline.isoformat() if goal.deadline else None,
                        self._budget(goal),
                        goal.revision,
                        self._task(goal),
                        goal.goal_id,
                        expected_revision,
                    ),
                ).rowcount
            )

        return await self._store.run_transaction(write)

    async def tasks(self, owner_session_id: str | None = None) -> tuple[Goal, ...]:
        def read(connection: sqlite3.Connection) -> tuple[Goal, ...]:
            rows = connection.execute(
                "SELECT * FROM goals WHERE task_json IS NOT NULL "
                "AND json_extract(task_json, '$.profile') = 'document-checklist-v1' "
                "AND (? IS NULL OR json_extract(task_json, '$.owner_session_id') = ?) "
                "ORDER BY rowid DESC LIMIT 21",
                (owner_session_id, owner_session_id),
            ).fetchall()
            if len(rows) > 20:
                raise ValueError("task history exceeds its capacity")
            return tuple(self._goal(row) for row in rows)

        return await self._store.run_transaction(read)

    async def remove_task(self, goal_id: str, owner: str, revision: int) -> bool:
        def remove(connection: sqlite3.Connection) -> bool:
            deleted = connection.execute(
                "DELETE FROM goals WHERE goal_id = ? AND revision = ? "
                "AND state IN ('completed', 'failed', 'cancelled') "
                "AND json_extract(task_json, '$.profile') = 'document-checklist-v1' "
                "AND json_extract(task_json, '$.owner_session_id') = ?",
                (goal_id, revision, owner),
            ).rowcount
            if deleted:
                connection.execute("DELETE FROM planning_decisions WHERE trace_id = ?", (goal_id,))
            return bool(deleted)

        return await self._store.run_transaction(remove)

    @staticmethod
    def _goal(row: sqlite3.Row) -> Goal:
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
            task=GoalTask.model_validate_json(str(row["task_json"])) if row["task_json"] else None,
        )

    @staticmethod
    def _task(goal: Goal) -> str | None:
        if goal.task is None:
            return None
        encoded = GoalTask.model_validate_json(goal.task.model_dump_json()).model_dump_json()
        if len(encoded.encode()) > 65536:
            raise ValueError("task metadata exceeds limit")
        return encoded

    @classmethod
    def _values(cls, goal: Goal) -> tuple[object, ...]:
        return (
            goal.goal_id,
            goal.state,
            goal.next_step,
            goal.deadline.isoformat() if goal.deadline else None,
            cls._budget(goal),
            goal.revision,
            cls._task(goal),
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
