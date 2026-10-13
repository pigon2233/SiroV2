from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from siro.contracts.events import SystemHealthEvent
from siro.persistence.sqlite import (
    Migration,
    MigrationError,
    SQLiteStore,
    apply_migrations,
    load_migrations,
)


def make_event(number: int = 1) -> SystemHealthEvent:
    timestamp = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)
    return SystemHealthEvent.model_validate(
        {
            "schema_version": 1,
            "event_id": f"00000000-0000-0000-0000-{number:012d}",
            "type": "system.health.v1",
            "source": "test.persistence",
            "occurred_at": timestamp,
            "received_at": timestamp,
            "trace_id": f"trace-{number}",
            "sequence": number,
            "priority": "background",
            "privacy": "local_only",
            "payload": {
                "component": "persistence",
                "state": "healthy",
                "observed_at": timestamp,
            },
        }
    )


@pytest.mark.asyncio
async def test_empty_database_is_migrated_with_wal(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")

    await store.initialize()

    with sqlite3.connect(store.path) as connection:
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations")]
        journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
    foreign_keys = await store.run_transaction(
        lambda connection: int(connection.execute("PRAGMA foreign_keys").fetchone()[0])
    )
    assert versions == [migration.version for migration in load_migrations()]
    assert journal == "wal"
    assert foreign_keys == 1
    assert await store.integrity_check() == "ok"


def test_incremental_migration_and_checksum_guard() -> None:
    connection = sqlite3.connect(":memory:")
    first = Migration(1, "one", "CREATE TABLE one(id INTEGER PRIMARY KEY)", "hash-one")
    second = Migration(2, "two", "CREATE TABLE two(id INTEGER PRIMARY KEY)", "hash-two")

    apply_migrations(connection, [first])
    apply_migrations(connection, [first, second])

    versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations")]
    assert versions == [1, 2]
    modified = Migration(1, "one", first.sql, "different")
    with pytest.raises(MigrationError, match="modified"):
        apply_migrations(connection, [modified, second])


@pytest.mark.asyncio
async def test_event_and_outbox_are_atomic_and_idempotent(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()
    event = make_event()

    assert await store.append_event_with_outbox(event, subject="events.system", payload=b"one")
    assert not await store.append_event_with_outbox(
        event, subject="events.system", payload=b"duplicate"
    )

    pending = await store.pending_outbox()
    assert len(pending) == 1
    assert pending[0].payload == b"one"
    assert await store.mark_outbox_sent(str(event.event_id))
    assert not await store.mark_outbox_sent(str(event.event_id))
    assert await store.pending_outbox() == []


@pytest.mark.asyncio
async def test_transaction_failure_rolls_back(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()

    def fail(connection: sqlite3.Connection) -> None:
        connection.execute(
            "INSERT INTO identities(identity_id, core_json, core_version, created_at) "
            "VALUES ('siro', '{}', 1, 'now')"
        )
        raise RuntimeError("synthetic interruption")

    with pytest.raises(RuntimeError, match="interruption"):
        await store.run_transaction(fail)

    def count(connection: sqlite3.Connection) -> int:
        return int(connection.execute("SELECT count(*) FROM identities").fetchone()[0])

    assert await store.run_transaction(count) == 0


@pytest.mark.asyncio
async def test_inbox_marker_rolls_back_with_consumer_work(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()

    def fail(_connection: sqlite3.Connection) -> None:
        raise RuntimeError("consumer failed")

    with pytest.raises(RuntimeError, match="consumer failed"):
        await store.process_once("projection", "event-1", fail)

    processed, result = await store.process_once(
        "projection",
        "event-1",
        lambda connection: connection.execute("SELECT 42").fetchone()[0],
    )
    duplicate, duplicate_result = await store.process_once(
        "projection", "event-1", lambda _connection: 99
    )
    assert (processed, result) == (True, 42)
    assert (duplicate, duplicate_result) == (False, None)


@pytest.mark.asyncio
async def test_backup_restore_recovers_consistent_state(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    backup = tmp_path / "backups" / "siro.backup.sqlite3"
    await store.initialize()
    first = make_event(1)
    second = make_event(2)
    await store.append_event_with_outbox(first, subject="events.system", payload=b"first")
    await store.backup_to(backup)
    await store.append_event_with_outbox(second, subject="events.system", payload=b"second")

    await store.restore_from(backup)

    pending = await store.pending_outbox()
    assert [record.payload for record in pending] == [b"first"]
    assert await store.integrity_check() == "ok"


@pytest.mark.asyncio
async def test_unusable_parent_path_fails_clearly(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file", encoding="utf-8")
    store = SQLiteStore(blocker / "siro.sqlite3")

    with pytest.raises((FileExistsError, NotADirectoryError)):
        await store.initialize()


@pytest.mark.parametrize("starting_version", [0, 10, 12])
def test_real_schema_upgrade_preserves_data_and_is_idempotent(starting_version: int) -> None:
    connection = sqlite3.connect(":memory:")
    migrations = load_migrations()
    apply_migrations(connection, migrations[:starting_version])
    if starting_version:
        connection.execute(
            "INSERT INTO identities(identity_id, core_json, core_version, created_at) "
            "VALUES ('baseline', '{}', 1, 'synthetic')"
        )
        connection.commit()
    apply_migrations(connection, migrations)
    snapshot = list(connection.execute("SELECT * FROM schema_migrations ORDER BY version"))
    apply_migrations(connection, migrations)
    assert list(connection.execute("SELECT * FROM schema_migrations ORDER BY version")) == snapshot
    assert len(snapshot) >= 12
    for table in ("tool_proposals", "agent_runs", "agent_steps"):
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone() == (table,)
    for index in ("idx_tool_proposals_session_state", "idx_agent_runs_session_updated"):
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index,)
        ).fetchone() == (index,)
    assert {row[1] for row in connection.execute("PRAGMA table_info(agent_steps)")} >= {
        "run_id",
        "step_index",
        "kind",
        "payload_json",
    }
    assert connection.execute("PRAGMA foreign_key_list(agent_steps)").fetchone()[2] == "agent_runs"
    if starting_version:
        assert connection.execute(
            "SELECT core_json FROM identities WHERE identity_id='baseline'"
        ).fetchone() == ("{}",)
    assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    connection.close()
