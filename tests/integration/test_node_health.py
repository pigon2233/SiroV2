from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from siro.core.devices import DeviceAvailability
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.node_health import NodeHealthWatcher
from siro.services.devices.mqtt_subscriber import mqtt_sensor_descriptor


@pytest.mark.asyncio
async def test_offline_then_back(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteDeviceRepository(store)
    await repo.upsert(mqtt_sensor_descriptor("n1"))
    watcher = NodeHealthWatcher(repo)
    t0 = datetime(2026, 5, 20, 12, tzinfo=UTC)
    assert await watcher.check(t0) == []  # never seen
    await repo.set_availability("n1", DeviceAvailability.ONLINE, t0)
    assert await watcher.check(t0 + timedelta(seconds=5)) == []
    await repo.set_availability("n1", DeviceAvailability.OFFLINE, t0 + timedelta(minutes=1))
    assert await watcher.check(t0 + timedelta(minutes=5)) == []  # grace period
    (down,) = await watcher.check(t0 + timedelta(minutes=12))
    assert down["trigger"] == "node_offline" and down["device"] == "n1"
    assert await watcher.check(t0 + timedelta(minutes=30)) == []  # not repeated at once
    back_at = t0 + timedelta(minutes=40)
    await repo.set_availability("n1", DeviceAvailability.ONLINE, back_at)
    (back,) = await watcher.check(back_at + timedelta(seconds=1))
    assert back["trigger"] == "node_back"


@pytest.mark.asyncio
async def test_grouped_transports_count_as_one_node(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteDeviceRepository(store)
    await repo.upsert(mqtt_sensor_descriptor("http-side"))
    await repo.upsert(mqtt_sensor_descriptor("mqtt-side"))
    groups = {"http-side": "node", "mqtt-side": "node"}
    t0 = datetime(2026, 5, 20, 12, tzinfo=UTC)
    await repo.set_availability("http-side", DeviceAvailability.ONLINE, t0)
    await repo.set_availability("mqtt-side", DeviceAvailability.ONLINE, t0 + timedelta(hours=1))
    now = t0 + timedelta(hours=1, seconds=5)
    # Ungrouped, the idle fallback device raises a false node_offline.
    ungrouped = await NodeHealthWatcher(repo).check(now)
    assert [f["device"] for f in ungrouped] == ["http-side"]
    # Grouped, the live MQTT side keeps the whole node online.
    assert await NodeHealthWatcher(repo, groups=groups).check(now) == []
