"""Synthetic SQLite preservation phases, imported only from the owned source copy."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from siro.core.cognition import Goal, GoalState
from siro.persistence.goals import SQLiteGoalRepository
from siro.persistence.sqlite import SQLiteStore, load_migrations

PHASE, PROJECT_TEXT, FIXTURE_TEXT, OUTPUT_TEXT = sys.argv[1:]
PROJECT, FIXTURE, OUTPUT = Path(PROJECT_TEXT), Path(FIXTURE_TEXT), Path(OUTPUT_TEXT)
DATABASE = FIXTURE / "synthetic.db"
SOURCE = FIXTURE / "workspace" / "checklist.md"
EXPECTED_LEGACY = {
    "goal_id": "synthetic-legacy-goal",
    "state": "waiting_external",
    "next_step": "preserve-legacy-next-step",
    "deadline": "2026-10-16T00:00:00+00:00",
    "steps_used": 2,
    "max_steps": 8,
    "cost_used": 0.0,
    "max_cost": 0.0,
    "revision": 3,
}


def legacy_fields(goal: Goal) -> dict[str, object]:
    return {
        "goal_id": goal.goal_id,
        "state": goal.state.value,
        "next_step": goal.next_step,
        "deadline": goal.deadline.isoformat() if goal.deadline else None,
        "steps_used": goal.steps_used,
        "max_steps": goal.max_steps,
        "cost_used": float(goal.cost_used),
        "max_cost": float(goal.max_cost),
        "revision": goal.revision,
    }


def snapshot() -> tuple[str, dict[str, object]]:
    with sqlite3.connect(f"{DATABASE.as_uri()}?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        dump = "\n".join(connection.iterdump()) + "\n"
        migrations = connection.execute(
            "SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()
        columns = [row[1] for row in connection.execute("PRAGMA table_info(goals)")]
        legacy_task = connection.execute(
            "SELECT task_json FROM goals WHERE goal_id=?", (EXPECTED_LEGACY["goal_id"],)
        ).fetchone()[0]
        tasks = connection.execute(
            "SELECT goal_id, task_json FROM goals WHERE task_json IS NOT NULL"
        ).fetchall()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        planning = connection.execute("SELECT count(*) FROM planning_decisions").fetchone()[0]
    assert [row[0] for row in migrations] == list(range(1, 15))
    assert "task_json" in columns and legacy_task is None
    assert len(tasks) == 1 and integrity == "ok" and planning == 1
    task_id, task_json = tasks[0]
    facts: dict[str, object] = {
        "actual_schema": 14,
        "applied_migration_rows": migrations,
        "goal_columns": columns,
        "legacy_task_json": legacy_task,
        "typed_task_goal_id": task_id,
        "task_json": json.loads(task_json),
        "task_json_sha256": hashlib.sha256(task_json.encode()).hexdigest(),
        "sql_dump_sha256": hashlib.sha256(dump.encode()).hexdigest(),
        "integrity_check": integrity,
        "planning_decisions": planning,
    }
    return dump, facts


async def main() -> None:
    import siro.core.cognition as cognition_module
    import siro.persistence.goals as goals_module
    import siro.persistence.sqlite as sqlite_module

    origins = {
        name: str(Path(module.__file__).resolve())
        for name, module in (
            ("cognition", cognition_module),
            ("goals", goals_module),
            ("sqlite", sqlite_module),
        )
    }
    assert all(Path(value).is_relative_to(PROJECT / "src") for value in origins.values())
    store = SQLiteStore(DATABASE)
    repository = SQLiteGoalRepository(store)
    if PHASE == "initialize":
        from siro.core.goal_tasks import GoalTask
        from siro.services.agent.goal_tasks import ReadTaskOwner
        from siro.services.tools.execution import ExecutionContext

        class ActualFixtureWorkspace:
            root = SOURCE.parent
            reads = 0
            available = True

            async def execute(
                self, capability: str, arguments: dict[str, object], context: ExecutionContext
            ) -> object:
                context.check()
                assert capability == "filesystem.read" and arguments == {"path": SOURCE.name}
                self.reads += 1
                text = await asyncio.to_thread(SOURCE.read_text, encoding="utf-8")
                context.check()
                return {"text": text}

        await store.initialize()
        await repository.add(
            Goal(
                goal_id=str(EXPECTED_LEGACY["goal_id"]),
                state=GoalState.WAITING_EXTERNAL,
                next_step=str(EXPECTED_LEGACY["next_step"]),
                deadline=datetime(2026, 10, 16, tzinfo=UTC),
                steps_used=2,
                max_steps=8,
                cost_used=0,
                max_cost=0,
                revision=3,
            )
        )
        workspace = ActualFixtureWorkspace()
        owner = ReadTaskOwner(store, workspace, busy=lambda: False, allowed=lambda: True)
        try:
            await owner.start()
            proposed = await owner.propose("synthetic-owner", (SOURCE.name,))
            task_id = str(proposed["goal_id"])
            assert workspace.reads == 0
            await owner.approve("synthetic-owner", task_id, int(proposed["revision"]))
            async with asyncio.timeout(10):
                while owner.busy:
                    await asyncio.sleep(0.01)
            goal = await repository.get(task_id)
            assert goal is not None and goal.state is GoalState.COMPLETED
            assert isinstance(goal.task, GoalTask) and len(goal.task.observations) == 1
            observation = goal.task.observations[0]
            assert observation.status == "completed"
            assert observation.sha256 == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
            assert observation.read_at.tzinfo is not None and goal.task.approved_at is not None
            assert workspace.reads == 1 and goal.steps_used == 1
        finally:
            # This is the rehearsal's explicit operator withdrawal before source reversal.
            os.environ["SIRO_GOAL_TASKS_ENABLED"] = "0"
            await owner.close()
        assert os.environ["SIRO_GOAL_TASKS_ENABLED"] == "0" and not owner.busy
        assert owner._work is None and owner._context is None and owner._active is None
        withdrawal: dict[str, object] = {
            "feature_setting_before_source_reverse": os.environ["SIRO_GOAL_TASKS_ENABLED"],
            "caller_close_awaited": True,
            "owned_task_context_active_cleared": True,
            "asyncio_children_joined": all(
                task is asyncio.current_task() or task.done() for task in asyncio.all_tasks()
            ),
            "actual_fixture_reads": workspace.reads,
            "source_sha256": observation.sha256,
            "read_at": observation.read_at.isoformat(),
            "approval_at": goal.task.approved_at.isoformat(),
            "source_lines": [item.model_dump() for item in observation.matches],
            "read_adapter": "actual bounded synthetic file IO through ReadTaskOwner; no Rust claim",
        }
    else:
        assert os.environ["SIRO_GOAL_TASKS_ENABLED"] == "0"
        await store.initialize()
        withdrawal = {"feature_setting": "0", "new_caller_started": False}

    legacy = await repository.get(str(EXPECTED_LEGACY["goal_id"]))
    assert legacy is not None and legacy_fields(legacy) == EXPECTED_LEGACY
    dump, facts = snapshot()
    task_goal = await repository.get(str(facts["typed_task_goal_id"]))
    assert task_goal is not None and task_goal.state is GoalState.COMPLETED
    loaded_count = len(load_migrations())
    if PHASE == "reversed":
        assert loaded_count == 13 and not hasattr(legacy, "task")
        assert not hasattr(task_goal, "task")
        assert not (PROJECT / "src/siro/core/goal_tasks.py").exists()
        assert not (PROJECT / "src/siro/services/agent/goal_tasks.py").exists()
        assert not (PROJECT / "src/siro/persistence/migrations/014_goal_tasks.sql").exists()
    else:
        from siro.core.goal_tasks import GoalTask

        assert loaded_count == 14 and legacy.task is None
        assert isinstance(task_goal.task, GoalTask)
        assert task_goal.task.model_dump(mode="json") == facts["task_json"]
    if PHASE != "initialize":
        assert dump == (OUTPUT / "schema14-before.sql").read_text(encoding="utf-8")
        expected = json.loads((OUTPUT / "database-initialize.json").read_text())
        assert facts == expected["database"]

    filename = "before" if PHASE == "initialize" else PHASE
    (OUTPUT / f"schema14-{filename}.sql").write_text(dump, encoding="utf-8")
    receipt = {
        "status": "PASS",
        "phase": PHASE,
        "loaded_origins": origins,
        "loaded_source_migrations": loaded_count,
        "legacy_repository_fields": legacy_fields(legacy),
        "legacy_goal_has_task_attribute": hasattr(legacy, "task"),
        "completed_task_goal_has_task_attribute": hasattr(task_goal, "task"),
        "database": facts,
        "withdrawal": withdrawal,
        "database_downmigration_drop_restore_performed": False,
        "source_proof_is_signed_release_authorization": False,
    }
    (OUTPUT / f"database-{PHASE}.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
