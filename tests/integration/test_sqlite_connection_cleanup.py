from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from siro.adapters.devices import SimulatedLight
from siro.adapters.models.mock import MockModel
from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.conversation import ConversationEngine, TurnState
from siro.core.devices import DeviceRegistry
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryService
from siro.core.world import WorldModel, WorldStatus
from siro.persistence.conversation import SQLiteConversationRepository
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository, SQLiteWorldRepository
from siro.services.devices.mqtt import MqttStateProjector


@pytest.mark.asyncio
async def test_all_existing_connection_pragmas_remain_enabled(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()
    result = await store.run_transaction(
        lambda connection: tuple(
            connection.execute(f"PRAGMA {name}").fetchone()[0]
            for name in ("journal_mode", "synchronous", "busy_timeout", "foreign_keys")
        )
    )
    assert result == ("wal", 1, 5000, 1)


@pytest.mark.asyncio
async def test_wal_reader_and_competing_writer_keep_consistent_snapshots(tmp_path: Path) -> None:
    first = SQLiteStore(tmp_path / "siro.sqlite3")
    second = SQLiteStore(first.path)
    await first.initialize()
    with closing(first._connect()) as reader:
        reader.execute("BEGIN")
        assert reader.execute("SELECT count(*) FROM identities").fetchone()[0] == 0
        await asyncio.wait_for(
            second.run_transaction(
                lambda connection: (
                    connection.execute(
                        "INSERT INTO identities VALUES ('synthetic', '{}', 1, 'fixture')"
                    ).rowcount
                )
            ),
            3,
        )
        assert reader.execute("SELECT count(*) FROM identities").fetchone()[0] == 0
        reader.commit()
        assert reader.execute("SELECT count(*) FROM identities").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_concurrent_mqtt_conversations_and_sourced_memory_use_same_wal_database(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="synthetic",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        now=datetime.now(UTC),
    )
    # Distinct store locks also exercise SQLite's actual inter-connection contention.
    device_store = SQLiteStore(store.path)
    memory_store = SQLiteStore(store.path)
    world = WorldModel(SQLiteWorldRepository(device_store))
    registry = DeviceRegistry(SQLiteDeviceRepository(device_store), world)
    await registry.register(SimulatedLight("esp32-lab-01", "esp32_mqtt", "lab").descriptor)
    projector = MqttStateProjector(registry)
    engine = ConversationEngine(
        MockModel(("synthetic reply",)), SQLiteConversationRepository(store), timeout_seconds=10
    )
    memories = MemoryService(SQLiteMemoryRepository(memory_store))
    now = datetime.now(UTC)

    async def converse_and_remember(index: int) -> None:
        text = f"synthetic conversation {index}"
        result = await engine.respond(f"session-{index}", "siro", text)
        assert result.state is TurnState.COMPLETED
        source = UserTextEvent(
            event_id=uuid4(),
            type="conversation.user_text.v1",
            source="owner",
            occurred_at=now,
            received_at=now,
            trace_id=result.trace_id,
            session_id=f"session-{index}",
            turn_id=result.turn_id,
            sequence=1,
            priority=Priority.INTERACTIVE,
            privacy=Privacy.LOCAL_ONLY,
            payload=UserTextPayload(text=text, language="en"),
        )
        await memories.remember(Memory(uuid4(), "siro", text, (source.event_id,), now), source)

    async with asyncio.timeout(15):
        await asyncio.gather(
            *(converse_and_remember(index) for index in range(20)),
            *(
                projector.handle_state(
                    "esp32-lab-01",
                    json.dumps(
                        {
                            "observed_at_epoch": (now + timedelta(microseconds=index)).timestamp(),
                            "properties": {"power": index % 2 == 0},
                        }
                    ).encode(),
                )
                for index in range(20)
            ),
        )
    counts = await store.run_transaction(
        lambda connection: tuple(
            connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("turns", "memories", "world_observations")
        )
    )
    assert counts == (20, 20, 20)
    current = await world.current("esp32-lab-01", "power", now=now + timedelta(seconds=1))
    assert current.status is WorldStatus.KNOWN and current.observation is not None
    assert current.observation.value is False
    assert await store.integrity_check() == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    ["initialize", "transaction", "failed_transaction", "pending", "quarantine", "integrity"],
)
async def test_owned_connection_is_closed_before_success_or_error_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()
    original = store._connect
    created: list[sqlite3.Connection] = []
    closed: list[sqlite3.Connection] = []

    class TrackedConnection(sqlite3.Connection):
        def close(self) -> None:
            closed.append(self)
            super().close()

    def connect(path: Path | None = None) -> sqlite3.Connection:
        connection = sqlite3.connect(path or store.path, factory=TrackedConnection)
        connection.row_factory = sqlite3.Row
        created.append(connection)
        return connection

    monkeypatch.setattr(store, "_connect", connect)
    if operation == "initialize":
        await store.initialize()
    elif operation == "transaction":
        assert (
            await store.run_transaction(
                lambda connection: connection.execute("SELECT 42").fetchone()[0]
            )
            == 42
        )
    elif operation == "failed_transaction":

        def fail(_connection: sqlite3.Connection) -> None:
            raise RuntimeError("synthetic failure")

        with pytest.raises(RuntimeError, match="synthetic"):
            await store.run_transaction(fail)
    elif operation == "pending":
        assert await store.pending_outbox() == []
    elif operation == "quarantine":
        assert await store.quarantined_outbox() == []
    else:
        assert await store.integrity_check() == "ok"
    assert created and closed == created
    monkeypatch.setattr(store, "_connect", original)


@pytest.mark.parametrize("close_fails", [False, True])
def test_connection_configuration_failure_closes_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, close_fails: bool
) -> None:
    closed = threading.Event()
    real_connect = sqlite3.connect

    class FailingConfiguration(sqlite3.Connection):
        def execute(self, sql: str, parameters: object = ()) -> sqlite3.Cursor:
            raise sqlite3.OperationalError("synthetic pragma failure")

        def close(self) -> None:
            closed.set()
            super().close()
            if close_fails:
                raise RuntimeError("synthetic cleanup failure")

    def connect(path: Path, **kwargs: object) -> sqlite3.Connection:
        return real_connect(path, factory=FailingConfiguration)

    monkeypatch.setattr(sqlite3, "connect", connect)
    with pytest.raises(sqlite3.OperationalError, match="synthetic pragma") as caught:
        SQLiteStore(tmp_path / "siro.sqlite3")._connect()
    assert closed.is_set()
    if close_fails:
        assert caught.value.__notes__ == ["connection cleanup failed: RuntimeError"]
