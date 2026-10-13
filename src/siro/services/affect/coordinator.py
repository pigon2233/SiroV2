"""Convert verified domain outcomes into persistent affect updates."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from siro.contracts.events import (
    ActionResultEvent,
    ActionResultPayload,
    GoalTransitionEvent,
    MemoryCorrectedEvent,
    Priority,
    Privacy,
)
from siro.core.affect import AffectResult, AffectSystem, OutcomeKind
from siro.core.outcomes import ActionOutcome
from siro.core.relationships import RelationshipRepository
from siro.persistence.affect import SQLiteAffectRepository
from siro.persistence.sqlite import SQLiteStore


class AffectCoordinator:
    def __init__(
        self,
        store: SQLiteStore,
        repository: SQLiteAffectRepository,
        relationships: RelationshipRepository,
        system: AffectSystem | None = None,
    ) -> None:
        self._store = store
        self._repository = repository
        self._relationships = relationships
        self._system = system or AffectSystem()

    async def ingest(
        self, event: ActionResultEvent | GoalTransitionEvent | MemoryCorrectedEvent
    ) -> AffectResult:
        if event.session_id is None:
            raise ValueError("affect outcome events require a session")
        await self._store.record_event(event)
        previous = await self._repository.state("siro", event.session_id)
        mood, drives = await self._repository.dynamics("siro", event.session_id)
        if previous is not None:
            self._system.restore(event.session_id, previous, mood, drives)
            elapsed = await self._repository.elapsed_hours(
                "siro", event.session_id, event.occurred_at.astimezone(UTC)
            )
            self._system.advance_time(event.session_id, elapsed)
        relationship = await self._relationships.current("siro", "owner")
        if isinstance(event, MemoryCorrectedEvent):
            outcome = OutcomeKind.MEMORY_CORRECTED
            importance = event.payload.importance
            controllability = 0.9
        elif isinstance(event, GoalTransitionEvent):
            outcome = (
                OutcomeKind.GOAL_COMPLETED
                if event.payload.state == "completed"
                else OutcomeKind.GOAL_FAILED
            )
            importance = event.payload.importance
            controllability = 0.7 if event.payload.state == "failed" else 0.8
        else:
            outcome = {
                "confirmed": OutcomeKind.ACTION_CONFIRMED,
                "mismatch": OutcomeKind.ACTION_MISMATCH,
                "denied": OutcomeKind.ACTION_DENIED,
                "unavailable": OutcomeKind.ACTION_DENIED,
                "error": OutcomeKind.ACTION_MISMATCH,
            }[event.payload.outcome]
            importance = event.payload.importance
            controllability = event.payload.controllability
        result = self._system.appraise_outcome(
            event.session_id,
            str(event.event_id),
            outcome,
            importance=importance,
            relationship_significance=relationship.significance,
            controllability=controllability,
        )
        source_id = str(event.event_id)
        await self._repository.record("siro", event.session_id, result.state, source_id)
        await self._repository.record_result(
            "siro",
            event.session_id,
            result,
            source_id,
            algorithm_config=self._system.configuration(),
        )
        return result


class AffectOutcomeReporter:
    """Create sourced result events for an executor and feed the coordinator."""

    def __init__(
        self,
        coordinator: AffectCoordinator,
        *,
        source: str,
        session_id: str,
        privacy: Privacy = Privacy.LOCAL_ONLY,
    ) -> None:
        self._coordinator = coordinator
        self._source = source
        self._session_id = session_id
        self._privacy = privacy

    async def report_action(
        self,
        action_id: str,
        outcome: ActionOutcome,
        *,
        occurred_at: datetime,
        importance: float,
        controllability: float,
        expected: object | None = None,
        observed: object | None = None,
    ) -> None:
        try:
            action_uuid = UUID(action_id)
        except ValueError:
            action_uuid = uuid5(NAMESPACE_URL, action_id)
        event = ActionResultEvent(
            event_id=uuid4(),
            type="action.result.v1",
            source=self._source,
            occurred_at=occurred_at,
            received_at=datetime.now(UTC),
            trace_id=str(uuid4()),
            session_id=self._session_id,
            sequence=0,
            priority=Priority.BACKGROUND,
            privacy=self._privacy,
            payload=ActionResultPayload(
                action_id=action_uuid,
                outcome=outcome,
                importance=importance,
                controllability=controllability,
                expected=expected,
                observed=observed,
            ),
        )
        await self._coordinator.ingest(event)
