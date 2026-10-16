"""Keep the ISO contract while exercising the ESP32 numeric clock boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from siro.adapters.devices import SimulatedLight
from siro.core.devices import DeviceRegistry
from siro.core.world import WorldModel, WorldStatus
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteWorldRepository
from siro.services.devices.mqtt import (
    CommandResult,
    DeviceCommand,
    MqttLightCommandProcessor,
    MqttStateProjector,
    command_message,
)

NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)


def command() -> DeviceCommand:
    return DeviceCommand(
        command_id="time-相容",
        action="light.set",
        desired_state={"power": True},
        expires_at=NOW + timedelta(seconds=10, microseconds=750_000),
    )


@pytest.mark.parametrize("offset", [UTC, timezone(timedelta(hours=8))])
def test_command_wire_preserves_iso_and_adds_integer_epoch(offset: timezone) -> None:
    original = command()
    original = original.model_copy(update={"expires_at": original.expires_at.astimezone(offset)})
    payload, retained = command_message(original)
    parsed = json.loads(payload)
    assert retained is False
    assert datetime.fromisoformat(parsed["expires_at"]) == original.expires_at
    assert type(parsed["expires_at_epoch"]) is int
    assert parsed["expires_at_epoch"] == int(original.expires_at.timestamp())
    assert parsed["command_id"] == original.command_id
    assert parsed["desired_state"] == {"power": True}


@pytest.mark.parametrize("with_epoch", [False, True])
def test_simulator_accepts_old_iso_and_new_firmware_compatible_command(with_epoch: bool) -> None:
    light = SimulatedLight("light-time", "esp32_sim", "lab")
    processor = MqttLightCommandProcessor(light)
    original = command()
    payload = command_message(original)[0] if with_epoch else original.model_dump_json().encode()
    assert processor.handle(payload, retained=False, now=NOW) is CommandResult.ACCEPTED
    assert light.power is True
    assert processor.handle(payload, retained=False, now=NOW) is CommandResult.DUPLICATE


@pytest.mark.parametrize(
    "epoch", [True, None, "1792065610", float(int((NOW + timedelta(seconds=10)).timestamp())), 0]
)
def test_simulator_rejects_bad_epoch_mirror_before_actuation(epoch: object) -> None:
    light = SimulatedLight("light-time", "esp32_sim", "lab")
    processor = MqttLightCommandProcessor(light)
    parsed = json.loads(command_message(command())[0])
    parsed["expires_at_epoch"] = epoch
    with pytest.raises(ValueError):
        processor.handle(json.dumps(parsed).encode(), retained=False, now=NOW)
    assert light.power is False
    assert (
        processor.handle(command_message(command())[0], retained=False, now=NOW)
        is CommandResult.ACCEPTED
    )


def test_epoch_support_does_not_accept_other_unknown_command_fields() -> None:
    light = SimulatedLight("light-time", "esp32_sim", "lab")
    parsed = json.loads(command_message(command())[0])
    parsed["unrecognized"] = True
    with pytest.raises(ValueError):
        MqttLightCommandProcessor(light).handle(
            json.dumps(parsed).encode(), retained=False, now=NOW
        )
    assert light.power is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "timestamp",
    [
        {"observed_at_epoch": int(NOW.timestamp())},
        {"observed_at_epoch": NOW.timestamp() + 0.125},
        {"observed_at": NOW.isoformat()},
        {"observed_at": NOW.astimezone(timezone(timedelta(hours=8))).isoformat()},
    ],
)
async def test_state_time_formats_reach_existing_registry_and_world(
    tmp_path: Path, timestamp: dict[str, object]
) -> None:
    store = SQLiteStore(tmp_path / "mqtt-time.sqlite3")
    await store.initialize()
    world = WorldModel(SQLiteWorldRepository(store))
    registry = DeviceRegistry(SQLiteDeviceRepository(store), world)
    light = SimulatedLight("light-time", "esp32_mqtt", "lab")
    await registry.register(light.descriptor)
    await MqttStateProjector(registry).handle_state(
        light.descriptor.device_id,
        json.dumps({**timestamp, "properties": {"power": True}}).encode(),
    )
    current = await world.current("light-time", "power", now=NOW + timedelta(seconds=1))
    assert current.status is WorldStatus.KNOWN
    assert current.observation is not None
    assert current.observation.value is True
    assert current.observation.source_id == "device:light-time:esp32_mqtt"
    expected = (
        NOW + timedelta(microseconds=125_000)
        if isinstance(timestamp.get("observed_at_epoch"), float)
        else NOW
    )
    assert current.observation.observed_at == expected


@pytest.mark.asyncio
async def test_iso_observation_takes_precedence_over_epoch_mirror() -> None:
    registry = Mock(spec=DeviceRegistry)
    registry.record_property = AsyncMock()
    await MqttStateProjector(registry).handle_state(
        "light-time",
        json.dumps(
            {"observed_at": NOW.isoformat(), "observed_at_epoch": 0, "properties": {"power": True}}
        ).encode(),
    )
    registry.record_property.assert_awaited_once_with("light-time", "power", True, observed_at=NOW)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "timestamp",
    [
        {},
        {"observed_at_epoch": True},
        {"observed_at_epoch": False},
        {"observed_at_epoch": None},
        {"observed_at_epoch": "1792065600"},
        {"observed_at_epoch": float("nan")},
        {"observed_at_epoch": float("inf")},
        {"observed_at_epoch": -float("inf")},
        {"observed_at_epoch": 10**100},
        {"observed_at_epoch": -(10**100)},
        {"observed_at": "invalid", "observed_at_epoch": NOW.timestamp()},
        {"observed_at": None, "observed_at_epoch": NOW.timestamp()},
        {"observed_at": "2026-10-15T12:00:00", "observed_at_epoch": NOW.timestamp()},
    ],
)
async def test_invalid_state_timestamp_rejected_before_registry_mutation(
    timestamp: dict[str, object],
) -> None:
    registry = Mock(spec=DeviceRegistry)
    registry.record_property = AsyncMock()
    with pytest.raises(ValueError):
        await MqttStateProjector(registry).handle_state(
            "light-time", json.dumps({**timestamp, "properties": {"power": True}}).encode()
        )
    registry.record_property.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b"null",
        b"{",
        b'{"observed_at_epoch": 1}',
        b'{"observed_at_epoch": 1, "properties": []}',
    ],
)
async def test_invalid_state_shape_rejected_without_writes(payload: bytes) -> None:
    registry = Mock(spec=DeviceRegistry)
    registry.record_property = AsyncMock()
    with pytest.raises(ValueError):
        await MqttStateProjector(registry).handle_state("light-time", payload)
    registry.record_property.assert_not_awaited()
