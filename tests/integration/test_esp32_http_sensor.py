"""The existing ESP32 HTTP event shape can project conservative World observations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from siro.core.devices import DeviceRegistry
from siro.core.world import WorldModel, WorldStatus
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteWorldRepository
from siro.services.devices.http_sensor import Esp32HttpSensorProjector, http_sensor_descriptor


@pytest.mark.asyncio
async def test_existing_http_events_project_with_source_and_expiry(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "sensor.sqlite3")
    await store.initialize()
    world = WorldModel(SQLiteWorldRepository(store))
    registry = DeviceRegistry(SQLiteDeviceRepository(store), world)
    await registry.register(http_sensor_descriptor("siro-node-01", location="lab"))
    projector = Esp32HttpSensorProjector(registry, device_id="siro-node-01")
    now = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)

    await projector.handle(b'{"device":"siro-node-01","event":"light_update","lux":235.8}', now=now)
    await projector.handle(b'{"device":"siro-node-01","event":"motion_detected"}', now=now)
    await projector.handle(b'{"device":"siro-node-01","event":"button_pressed"}', now=now)
    for property_name, expected in (
        ("illuminance", 235.8),
        ("motion", True),
        ("last_button_press_at", now.isoformat()),
    ):
        current = await world.current("siro-node-01", property_name, now=now + timedelta(seconds=1))
        assert current.status is WorldStatus.KNOWN
        assert current.observation is not None
        assert current.observation.value == expected
        assert current.observation.source_id == "device:siro-node-01:esp32_http"
        assert current.observation.observed_at == now
        expired = await world.current(
            "siro-node-01", property_name, now=now + timedelta(seconds=20)
        )
        assert expired.status is WorldStatus.UNKNOWN

    await projector.handle(
        b'{"device":"siro-node-01","event":"motion_cleared"}',
        now=now + timedelta(seconds=2),
    )
    motion = await world.current("siro-node-01", "motion", now=now + timedelta(seconds=3))
    assert motion.observation is not None and motion.observation.value is False
    presence = await registry.room_presence("lab", now=now + timedelta(seconds=3))
    assert presence.status is WorldStatus.UNKNOWN and presence.present is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"[]",
        b'{"device":"other","event":"light_update","lux":1}',
        b'{"device":"siro-node-01","event":"light_update"}',
        b'{"device":"siro-node-01","event":"light_update","lux":-1}',
        b'{"device":"siro-node-01","event":"light_update","lux":"1"}',
        b'{"device":"siro-node-01","event":"light_update","lux":1e999}',
        b'{"device":"siro-node-01","event":"motion_detected","lux":1}',
        b'{"device":"siro-node-01","event":"button_pressed","action":"light.set"}',
        b'{"device":"siro-node-01","event":[]}',
        b'{"device":"siro-node-01","event":"button_pressed","event":"light_update"}',
        b"{" + b" " * 4096 + b"}",
    ],
)
async def test_invalid_http_event_does_not_create_observation(
    tmp_path: Path, payload: bytes
) -> None:
    store = SQLiteStore(tmp_path / "sensor.sqlite3")
    await store.initialize()
    world = WorldModel(SQLiteWorldRepository(store))
    registry = DeviceRegistry(SQLiteDeviceRepository(store), world)
    await registry.register(http_sensor_descriptor("siro-node-01"))
    projector = Esp32HttpSensorProjector(registry, device_id="siro-node-01")
    with pytest.raises(ValueError):
        await projector.handle(payload, now=datetime.now(UTC))
    for name in ("motion", "illuminance", "last_button_press_at"):
        current = await world.current("siro-node-01", name, now=datetime.now(UTC))
        assert current.status is WorldStatus.UNKNOWN
