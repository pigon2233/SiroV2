from __future__ import annotations

import asyncio
import socket
import sqlite3
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from nats.js.api import AckPolicy, ConsumerConfig

from siro.contracts.events import Event, validate_event_json
from siro.events.nats import NatsJetStream, OutboxDispatcher
from siro.events.replay import ReplayRunner, ReplayRuntime, ReplaySideEffectError
from siro.persistence.sqlite import SQLiteStore

FIXTURE = Path(__file__).parents[1] / "fixtures/events/user_text.valid.json"
NATS_SERVER = Path.home() / ".local/bin/nats-server"


def unused_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


@pytest.fixture
def nats_url(tmp_path: Path) -> Iterator[str]:
    if not NATS_SERVER.is_file():
        pytest.skip("user-local nats-server is not installed")
    port = unused_port()
    process = subprocess.Popen(
        [
            str(NATS_SERVER),
            "-js",
            "-sd",
            str(tmp_path / "jetstream"),
            "-a",
            "127.0.0.1",
            "-p",
            str(port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.02)
    else:
        process.terminate()
        raise RuntimeError("nats-server did not start")
    yield f"nats://127.0.0.1:{port}"
    process.terminate()
    process.wait(timeout=5)


@pytest.mark.asyncio
async def test_redelivery_is_deduplicated_after_commit_before_ack(
    tmp_path: Path, nats_url: str
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    event = validate_event_json(FIXTURE.read_bytes())
    assert await store.append_event_with_outbox(
        event, subject="siro.events", payload=event.model_dump_json().encode()
    )

    producer = NatsJetStream(nats_url)
    await producer.connect()
    await producer.ensure_stream("SIRO", ["siro.events"])
    assert (await OutboxDispatcher(store, producer).dispatch_once()).sent == 1

    consumer = NatsJetStream(nats_url)
    await consumer.connect()
    subscription = await consumer.jetstream().pull_subscribe(
        "siro.events",
        durable="core-worker",
        stream="SIRO",
        config=ConsumerConfig(
            durable_name="core-worker",
            ack_policy=AckPolicy.EXPLICIT,
            ack_wait=0.2,
            max_deliver=5,
        ),
    )
    await subscription.fetch(1, timeout=2)

    def side_effect(connection: sqlite3.Connection) -> int:
        connection.execute("CREATE TABLE IF NOT EXISTS effects(event_id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO effects(event_id) VALUES (?)", (str(event.event_id),))
        return 1

    processed, _ = await store.process_once("core-worker", str(event.event_id), side_effect)
    assert processed
    await consumer.close()  # crash after DB commit, before ack
    await asyncio.sleep(0.25)

    restarted = NatsJetStream(nats_url)
    await restarted.connect()
    replayed = await restarted.jetstream().pull_subscribe(
        "siro.events", durable="core-worker", stream="SIRO"
    )
    duplicate = (await replayed.fetch(1, timeout=2))[0]
    processed, _ = await store.process_once("core-worker", str(event.event_id), side_effect)
    assert not processed
    await duplicate.ack()
    count = await store.run_transaction(
        lambda connection: int(connection.execute("SELECT count(*) FROM effects").fetchone()[0])
    )
    assert count == 1
    await restarted.close()
    await producer.close()


@pytest.mark.asyncio
async def test_broker_outage_retains_then_quarantines_pending(
    tmp_path: Path, nats_url: str
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    event = validate_event_json(FIXTURE.read_bytes())
    assert await store.append_event_with_outbox(
        event, subject="siro.events", payload=event.model_dump_json().encode()
    )
    disconnected = NatsJetStream(nats_url)
    dispatcher = OutboxDispatcher(store, disconnected, max_attempts=2)

    first = await dispatcher.dispatch_once()
    assert first.failed == 1 and first.quarantined == 0
    assert len(await store.pending_outbox()) == 1
    second = await dispatcher.dispatch_once()
    assert second.failed == 1 and second.quarantined == 1
    quarantined = await store.quarantined_outbox()
    assert len(quarantined) == 1 and quarantined[0].attempts == 2


@pytest.mark.asyncio
async def test_replay_projects_events_and_runtime_is_disabled(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    event = validate_event_json(FIXTURE.read_bytes())
    assert await store.append_event_with_outbox(
        event, subject="siro.events", payload=event.model_dump_json().encode()
    )
    projected: list[str] = []

    async def projector(replayed: Event) -> None:
        projected.append(replayed.type)

    assert await ReplayRunner(store).run(projector) == 1
    assert projected == ["conversation.user_text.v1"]
    with pytest.raises(ReplaySideEffectError):
        await ReplayRuntime().dispatch("computer.shell", {"command": "blocked"})
