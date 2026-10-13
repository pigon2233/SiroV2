from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.relationships import RelationshipEvent, RelationshipSystem
from siro.persistence.relationships import SQLiteRelationshipRepository
from siro.persistence.sqlite import SQLiteStore

pytestmark = pytest.mark.asyncio


async def test_relationship_rupture_and_slow_repair_are_sourced_and_persistent(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    await store.run_transaction(
        lambda connection: connection.execute(
            "INSERT INTO identities(identity_id, core_json, core_version, created_at) "
            "VALUES ('siro', '{}', 1, '2026-09-28T00:00:00+00:00')"
        )
    )
    repository = SQLiteRelationshipRepository(store)
    state = await repository.current("siro", "owner")
    initial_trust = state.trust

    async def source(text: str) -> str:
        now = datetime.now(UTC)
        event = UserTextEvent(
            event_id=uuid4(),
            type="conversation.user_text.v1",
            source="test",
            occurred_at=now,
            received_at=now,
            trace_id=str(uuid4()),
            session_id="browser",
            turn_id=str(uuid4()),
            sequence=0,
            priority=Priority.INTERACTIVE,
            privacy=Privacy.LOCAL_ONLY,
            payload=UserTextPayload(text=text, language="zh-Hant"),
        )
        await store.record_event(event)
        return str(event.event_id)

    conflict = RelationshipSystem.update(
        state, RelationshipEvent.CONFLICT, await source("conflict")
    )
    await repository.record("siro", "owner", conflict)
    repair = RelationshipSystem.update(
        conflict.state, RelationshipEvent.REPAIR, await source("repair")
    )
    await repository.record("siro", "owner", repair)

    restored = await SQLiteRelationshipRepository(SQLiteStore(store.path)).current("siro", "owner")
    assert restored == repair.state
    assert restored.trust < initial_trust
    assert restored.rupture > 0
    assert restored.repair_history == 1


async def test_relationship_rejects_unknown_source(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    await store.run_transaction(
        lambda connection: connection.execute(
            "INSERT INTO identities(identity_id, core_json, core_version, created_at) "
            "VALUES ('siro', '{}', 1, '2026-09-28T00:00:00+00:00')"
        )
    )
    repository = SQLiteRelationshipRepository(store)
    update = RelationshipSystem.update(
        await repository.current("siro", "owner"), RelationshipEvent.SUPPORT, "missing"
    )
    with pytest.raises(ValueError, match="source event"):
        await repository.record("siro", "owner", update)
