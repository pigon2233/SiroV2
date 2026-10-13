"""Run the deterministic T29 room-entry and manual-readback demonstrations."""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from siro.adapters.devices import SimulatedLight, SimulatedRoomLightActuator, SimulatedSensor
from siro.config import ProactivitySettings, RoomAutomationSettings
from siro.core.authorization import AuthorizationService, PermissionDecision, PermissionPolicy
from siro.core.devices import DeviceRegistry
from siro.core.proactivity import ProactivityRules
from siro.core.rooms import RoomAutomation
from siro.core.world import WorldModel
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteWorldRepository


async def run() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="siro-t29-") as temporary:
        store = SQLiteStore(Path(temporary) / "demo.sqlite3")
        await store.initialize()
        registry = DeviceRegistry(
            SQLiteDeviceRepository(store), WorldModel(SQLiteWorldRepository(store))
        )
        light = SimulatedLight("light-entry", "simulated_light", "entry")
        sensor = SimulatedSensor(
            "presence-entry", "simulated_sensor", "presence", "boolean", "entry"
        )
        await registry.register(light.descriptor)
        await registry.register(sensor.descriptor)
        now = datetime(2026, 9, 26, 10, tzinfo=UTC)
        await registry.record_property(light.device_id, "power", False, observed_at=now)
        await registry.record_property(sensor.device_id, "presence", False, observed_at=now)
        automation = RoomAutomation(
            registry,
            ProactivityRules(
                ProactivitySettings(
                    enabled=True, timezone="UTC", quiet_start="23:00", quiet_end="08:00"
                )
            ),
            AuthorizationService(
                PermissionPolicy({"device.light.set": PermissionDecision.ALLOW}), b"demo-secret"
            ),
            SimulatedRoomLightActuator(light),
            RoomAutomationSettings(enabled=True),
        )
        arrival = await automation.ingest_presence(sensor.device_id, present=True, observed_at=now)
        await automation.ingest_presence(
            sensor.device_id, present=False, observed_at=now + timedelta(seconds=1)
        )
        bounce = await automation.ingest_presence(
            sensor.device_id, present=True, observed_at=now + timedelta(seconds=2)
        )
        manual = await automation.ingest_light_readback(
            light.device_id, power=False, observed_at=now + timedelta(seconds=3), source="manual"
        )
        return {
            "arrival": {
                "greeted": arrival.greeted,
                "light_status": arrival.light_status,
                "trace": [asdict(step) for step in arrival.trace],
            },
            "bounce": {
                "greeted": bounce.greeted,
                "light_status": bounce.light_status,
                "trace": [asdict(step) for step in bounce.trace],
            },
            "manual_readback": [asdict(step) for step in manual],
        }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), default=str, indent=2))
