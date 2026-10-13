from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from siro.contracts.events import (
    ActionResultEvent,
    ActionResultPayload,
    GoalTransitionEvent,
    GoalTransitionPayload,
    MemoryCorrectedEvent,
    MemoryCorrectedPayload,
    Priority,
    Privacy,
)
from siro.core.cognition import ActionCandidate, AttentionSignal, Planner
from siro.persistence.affect import SQLiteAffectRepository
from siro.persistence.planning import SQLitePlanningRepository
from siro.persistence.relationships import SQLiteRelationshipRepository
from siro.persistence.sqlite import SQLiteStore
from siro.services.affect.coordinator import AffectCoordinator, AffectOutcomeReporter
from siro.services.affect.planner import (
    AffectAwareAttention,
    AffectAwarePlanner,
    AffectDecisionLoop,
)

pytestmark = pytest.mark.asyncio


class FixedClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def envelope() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "event_id": uuid4(),
        "source": "test.executor",
        "occurred_at": now,
        "received_at": now,
        "trace_id": str(uuid4()),
        "session_id": "browser",
        "sequence": 0,
        "priority": Priority.INTERACTIVE,
        "privacy": Privacy.LOCAL_ONLY,
    }


async def coordinator(path: Path) -> tuple[AffectCoordinator, SQLiteStore]:
    store = SQLiteStore(path)
    await store.initialize()
    await store.run_transaction(
        lambda connection: connection.execute(
            "INSERT INTO identities(identity_id, core_json, core_version, created_at) "
            "VALUES ('siro', '{}', 1, '2026-09-28T00:00:00+00:00')"
        )
    )
    return (
        AffectCoordinator(
            store,
            SQLiteAffectRepository(store),
            SQLiteRelationshipRepository(store),
        ),
        store,
    )


async def test_verified_action_readback_drives_guilt_and_repair(tmp_path: Path) -> None:
    service, store = await coordinator(tmp_path / "siro.db")
    event = ActionResultEvent.model_validate(
        {
            **envelope(),
            "type": "action.result.v1",
            "payload": ActionResultPayload(
                action_id=uuid4(),
                outcome="mismatch",
                importance=1.0,
                controllability=0.9,
                expected="on",
                observed="off",
            ),
        }
    )
    result = await service.ingest(event)
    assert result.state.emotion == "guilt"
    assert result.coping.strategy == "repair"
    row = await store.run_transaction(
        lambda connection: connection.execute(
            "SELECT event_id, appraisal_json FROM appraisal_records"
        ).fetchone()
    )
    assert row[0] == str(event.event_id)
    assert str(event.event_id) in str(row[1])
    assert "siro-affect-cpm-1" in str(row[1])
    assert "episode_tau_hours" in str(row[1])


async def test_verified_goal_completion_drives_pride(tmp_path: Path) -> None:
    service, _ = await coordinator(tmp_path / "siro.db")
    event = GoalTransitionEvent.model_validate(
        {
            **envelope(),
            "type": "goal.transition.v1",
            "payload": GoalTransitionPayload(
                goal_id="goal-1",
                previous_state="running",
                state="completed",
                importance=1.0,
            ),
        }
    )
    result = await service.ingest(event)
    assert result.state.emotion == "pride"
    assert result.coping.strategy == "savor"


async def test_executor_reporter_accepts_domain_action_id_and_persists_event(
    tmp_path: Path,
) -> None:
    service, store = await coordinator(tmp_path / "siro.db")
    reporter = AffectOutcomeReporter(service, source="siro.room", session_id="automation:room")
    await reporter.report_action(
        "room-light:domain-id",
        "confirmed",
        occurred_at=datetime.now(UTC),
        importance=0.4,
        controllability=0.8,
        expected=True,
        observed=True,
    )
    rows = await store.run_transaction(
        lambda connection: connection.execute(
            "SELECT type FROM events WHERE type = 'action.result.v1'"
        ).fetchall()
    )
    assert len(rows) == 1


async def test_memory_correction_drives_guilt_and_repair(tmp_path: Path) -> None:
    service, _ = await coordinator(tmp_path / "siro.db")
    event = MemoryCorrectedEvent.model_validate(
        {
            **envelope(),
            "type": "memory.corrected.v1",
            "payload": MemoryCorrectedPayload(
                memory_id=uuid4(),
                revision=2,
                reason="owner corrected false memory",
                importance=0.9,
            ),
        }
    )
    result = await service.ingest(event)
    assert result.state.emotion == "guilt"
    assert result.coping.strategy == "repair"
    assert result.drives.competence > 0.3


async def test_persisted_repair_coping_changes_real_planner_selection(
    tmp_path: Path,
) -> None:
    service, store = await coordinator(tmp_path / "siro.db")
    reporter = AffectOutcomeReporter(service, source="test.executor", session_id="work")
    await reporter.report_action(
        "failed-action",
        "mismatch",
        occurred_at=datetime.now(UTC),
        importance=1.0,
        controllability=0.9,
        expected="correct",
        observed="wrong",
    )
    affect_repository = SQLiteAffectRepository(store)
    assert await affect_repository.latest_coping("siro", "work") == "repair"
    planner = AffectAwarePlanner(
        Planner(SQLitePlanningRepository(store), FixedClock()), affect_repository
    )
    repair = ActionCandidate(
        "repair", "memory_correct", {}, "fixed", 0, None, 0.55, ("repair error",)
    )
    continue_action = ActionCandidate(
        "continue", "tool_execute", {}, "done", 0, None, 0.60, ("continue",)
    )
    forbidden = ActionCandidate(
        "forbidden",
        "memory_correct",
        {},
        "fixed",
        0,
        None,
        0.95,
        ("unsafe repair",),
        permission_allowed=False,
    )
    nothing = ActionCandidate("none", "none", {}, "wait", 0, None, 0.1, ("wait",))
    decision = await planner.plan(
        "work", "trace-repair", (repair, continue_action, forbidden), nothing
    )
    assert decision.selected_candidate_id == "repair"
    assert ("forbidden", "permission") in decision.rejected


async def test_persisted_drive_pressure_enters_attention_without_overriding_cancel(
    tmp_path: Path,
) -> None:
    service, store = await coordinator(tmp_path / "siro.db")
    reporter = AffectOutcomeReporter(service, source="test.executor", session_id="attention")
    for index in range(7):
        await reporter.report_action(
            f"mismatch-{index}",
            "mismatch",
            occurred_at=datetime.now(UTC),
            importance=0.8,
            controllability=0.7,
        )
    attention = AffectAwareAttention(SQLiteAffectRepository(store))
    selected = await attention.select("attention", ())
    assert selected is not None
    assert selected.signal_id == "affect-drive:safety"
    cancel = AttentionSignal("cancel", 0, 0, 0, 0, 0, control="cancel")
    assert await attention.select("attention", (cancel,)) == cancel


async def test_canonical_decision_loop_requires_attention_and_cancel_forces_no_action(
    tmp_path: Path,
) -> None:
    _, store = await coordinator(tmp_path / "siro.db")
    repository = SQLiteAffectRepository(store)
    loop = AffectDecisionLoop(
        AffectAwarePlanner(Planner(SQLitePlanningRepository(store), FixedClock()), repository),
        AffectAwareAttention(repository),
    )
    candidate = ActionCandidate("execute", "tool_execute", {}, "done", 0, None, 0.9, ("requested",))
    nothing = ActionCandidate("none", "none", {}, "wait", 0, None, 0.1, ("wait",))

    assert await loop.decide("loop", "unattended", (), (candidate,), nothing) is None

    user = AttentionSignal("user", 0, 0, 0, 0, 0, explicit_user_input=True)
    result = await loop.decide("loop", "user-action", (user,), (candidate,), nothing)
    assert result is not None
    attended, decision = result
    assert attended == user
    assert decision.selected_candidate_id == "execute"

    cancel = AttentionSignal("cancel", 0, 0, 0, 0, 0, control="cancel")
    result = await loop.decide("loop", "cancel-action", (user, cancel), (candidate,), nothing)
    assert result is not None
    attended, decision = result
    assert attended == cancel
    assert decision.selected_candidate_id == "none"
