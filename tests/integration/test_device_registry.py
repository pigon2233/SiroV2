from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from siro.adapters.devices import SimulatedCamera, SimulatedLight, SimulatedSensor
from siro.core.devices import DeviceAvailability, DeviceRegistry
from siro.core.world import WorldModel, WorldStatus
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteWorldRepository


@pytest.mark.asyncio
async def test_t26_cross_brand_actions_availability_and_conservative_presence(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()
    repository = SQLiteDeviceRepository(store)
    registry = DeviceRegistry(repository, WorldModel(SQLiteWorldRepository(store)))
    now = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)

    first = SimulatedLight("light-a", "brand_a", "bedroom")
    second = SimulatedLight("light-b", "brand_b", "bedroom")
    presence = SimulatedSensor("presence-a", "sim_presence", "presence", "boolean", "bedroom")
    unlocated = SimulatedSensor("presence-x", "sim_presence", "presence", "boolean", None)
    temperature = SimulatedSensor(
        "temperature-a", "sim_temperature", "temperature", "number", "bedroom", "C"
    )
    for descriptor in (
        first.descriptor,
        second.descriptor,
        presence.descriptor,
        unlocated.descriptor,
        temperature.descriptor,
    ):
        await registry.register(descriptor)

    await registry.record_property("light-a", "power", False, observed_at=now)
    await registry.record_property("light-b", "power", False, observed_at=now)
    lights = await registry.devices_for_action("light.set", now=now)
    assert [item.descriptor.adapter for item in lights] == ["brand_a", "brand_b"]
    assert first.set_power("command-1", True)
    assert first.set_power("command-1", True)
    with pytest.raises(ValueError, match="reused"):
        first.set_power("command-1", False)

    await registry.record_property("presence-x", "presence", True, observed_at=now)
    unknown = await registry.room_presence("bedroom", now=now)
    assert unknown.status is WorldStatus.UNKNOWN
    assert unknown.present is None

    await registry.record_property("presence-a", "presence", True, observed_at=now)
    known = await registry.room_presence("bedroom", now=now)
    assert known.status is WorldStatus.KNOWN and known.present is True
    assert known.source_device_ids == ("presence-a",)
    expired = await registry.room_presence("bedroom", now=now + timedelta(seconds=30))
    assert expired.status is WorldStatus.UNKNOWN and expired.present is None
    stale = await registry.available("presence-a", now=now + timedelta(seconds=30))
    assert stale is not None and stale.availability is DeviceAvailability.STALE

    await registry.record_property("temperature-a", "temperature", 24.5, observed_at=now)


def test_t26_camera_is_owner_enabled_and_on_demand_only() -> None:
    camera = SimulatedCamera("camera-a", "entry")
    assert camera.capture_count == 0
    with pytest.raises(PermissionError, match="owner"):
        camera.capture()
    camera.owner_enabled = True
    assert camera.capture() == b"simulated-on-demand-frame"
    assert camera.capture_count == 1
