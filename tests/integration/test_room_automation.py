from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from siro.adapters.devices import SimulatedLight, SimulatedRoomLightActuator, SimulatedSensor
from siro.config import ProactivitySettings, RoomAutomationSettings
from siro.core.authorization import AuthorizationService, PermissionDecision, PermissionPolicy
from siro.core.devices import DeviceAvailability, DeviceRegistry
from siro.core.outcomes import ActionOutcome
from siro.core.proactivity import ProactivityRules
from siro.core.rooms import LightReadbackStatus, RoomAutomation
from siro.core.world import WorldModel, WorldStatus
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteWorldRepository


class CapturingOutcomes:
    def __init__(self) -> None:
        self.values: list[tuple[str, ActionOutcome, object | None, object | None]] = []

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
        del occurred_at, importance, controllability
        self.values.append((action_id, outcome, expected, observed))


async def room_stack(
    tmp_path: Path, *, light_enabled: bool, policy_allowed: bool = True, name: str = "room"
) -> tuple[DeviceRegistry, WorldModel, SimulatedLight, SimulatedSensor, RoomAutomation, datetime]:
    store = SQLiteStore(tmp_path / f"{name}.sqlite3")
    await store.initialize()
    world = WorldModel(SQLiteWorldRepository(store))
    registry = DeviceRegistry(SQLiteDeviceRepository(store), world)
    light = SimulatedLight("light-room", "simulated_light", "entry")
    sensor = SimulatedSensor("presence-room", "simulated_sensor", "presence", "boolean", "entry")
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
            PermissionPolicy(
                {"device.light.set": PermissionDecision.ALLOW} if policy_allowed else {}
            ),
            b"test-secret",
        ),
        SimulatedRoomLightActuator(light),
        RoomAutomationSettings(enabled=light_enabled),
    )
    return registry, world, light, sensor, automation, now


@pytest.mark.asyncio
async def test_t29_arrival_trace_bounce_suppression_and_manual_light_readback(
    tmp_path: Path,
) -> None:
    _, world, light, sensor, automation, now = await room_stack(tmp_path, light_enabled=True)

    arrival = await automation.ingest_presence(sensor.device_id, present=True, observed_at=now)
    assert arrival.greeted is True
    assert arrival.light_status is LightReadbackStatus.CONFIRMED
    assert [step.stage for step in arrival.trace] == [
        "sensor",
        "salience",
        "candidate",
        "policy",
        "policy",
        "device",
    ]
    assert light.power is True

    await automation.ingest_presence(
        sensor.device_id, present=False, observed_at=now + timedelta(seconds=1)
    )
    bounced = await automation.ingest_presence(
        sensor.device_id, present=True, observed_at=now + timedelta(seconds=2)
    )
    assert bounced.greeted is False
    assert bounced.light_status is None
    assert bounced.trace[-1].detail == "presence_bounce_suppressed"

    manual = await automation.ingest_light_readback(
        light.device_id, power=False, observed_at=now + timedelta(seconds=3), source="manual_ha"
    )
    assert manual[-1].detail == "readback_only:manual_ha"
    power = await world.current(light.device_id, "power", now=now + timedelta(seconds=3))
    assert power.status is WorldStatus.KNOWN and power.observation is not None
    assert power.observation.value is False
    assert light.power is True  # The simulated actuator was not called by a manual readback.


@pytest.mark.asyncio
async def test_t29_disabled_or_denied_policy_never_toggles_light(tmp_path: Path) -> None:
    _, _, light, sensor, automation, now = await room_stack(tmp_path, light_enabled=False)
    disabled = await automation.ingest_presence(sensor.device_id, present=True, observed_at=now)
    assert disabled.greeted is True
    assert disabled.light_status is None
    assert disabled.trace[-1].detail == "light_automation_disabled"
    assert light.power is False

    _, _, light, sensor, automation, now = await room_stack(
        tmp_path, light_enabled=True, policy_allowed=False, name="denied"
    )
    denied = await automation.ingest_presence(sensor.device_id, present=True, observed_at=now)
    assert denied.light_status is None
    assert any(step.detail == "light_policy_denied" for step in denied.trace)
    assert light.power is False


@pytest.mark.asyncio
async def test_t29_offline_sensor_and_mismatched_device_readback_are_safe(tmp_path: Path) -> None:
    registry, _, light, sensor, automation, now = await room_stack(tmp_path, light_enabled=True)
    await registry.set_availability(sensor.device_id, DeviceAvailability.OFFLINE, observed_at=now)
    offline = await automation.ingest_presence(sensor.device_id, present=True, observed_at=now)
    assert offline.greeted is False
    assert offline.trace[-1].detail == "device_unavailable"
    assert light.power is False

    registry, _, light, sensor, _, now = await room_stack(
        tmp_path, light_enabled=True, name="mismatch"
    )
    outcomes = CapturingOutcomes()
    mismatch = RoomAutomation(
        registry,
        ProactivityRules(
            ProactivitySettings(
                enabled=True, timezone="UTC", quiet_start="23:00", quiet_end="08:00"
            )
        ),
        AuthorizationService(
            PermissionPolicy({"device.light.set": PermissionDecision.ALLOW}), b"test-secret"
        ),
        SimulatedRoomLightActuator(light, confirm_commands=False),
        RoomAutomationSettings(enabled=True),
        outcome_reporter=outcomes,
    )
    outcome = await mismatch.ingest_presence(sensor.device_id, present=True, observed_at=now)
    assert outcome.light_status is LightReadbackStatus.MISMATCH
    assert light.power is False
    assert outcomes.values[0][1:] == ("mismatch", True, False)
