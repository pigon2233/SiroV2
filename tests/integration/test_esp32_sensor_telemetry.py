"""ESP32 sensor timing and authenticated telemetry projection contracts."""

from __future__ import annotations

import asyncio
import json
import shutil
import socket
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiomqtt
import pytest
from amqtt.broker import Broker  # type: ignore[import-untyped]
from argon2 import PasswordHasher

from siro.contracts.events import Privacy
from siro.core.devices import DeviceAction, DeviceDescriptor, DeviceProperty, DeviceRegistry
from siro.core.world import WorldModel, WorldStatus
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteWorldRepository
from siro.services.devices.mqtt import MqttStateProjector

FIRMWARE_INCLUDE = Path(__file__).resolve().parents[2] / "firmware" / "esp32" / "include"


def test_pir_warmup_debounce_wraparound_and_bh1750_conversion(tmp_path: Path) -> None:
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("host C++ compiler unavailable; firmware timing test not run")
    source = tmp_path / "sensor_contract.cpp"
    source.write_text(
        """
#include <cassert>
#include <cmath>
#include <cstdint>
#include "sensor_telemetry.h"
int main() {
  PirMotionSampler pir(1000);
  assert(!pir.update(60999, true));  // no motion during warm-up
  assert(!pir.ready());
  assert(pir.update(61000, false));  // first reliable absence is emitted
  assert(pir.ready() && !pir.motion());
  assert(!pir.update(61010, true));
  assert(!pir.update(61200, false)); // short bounce is discarded
  assert(!pir.update(61500, true));
  assert(!pir.update(61999, true));
  assert(pir.update(62000, true));
  assert(pir.motion());
  assert(!pir.update(63000, true)); // unchanged state is not an edge
  pir.invalidate();
  assert(!pir.ready());
  assert(!pir.update(64000, true));
  assert(!pir.update(64499, true));
  assert(pir.update(64500, true));
  assert(pir.ready() && pir.motion());

  PirMotionSampler wrapped(UINT32_MAX - 1000u);
  assert(!wrapped.update(UINT32_MAX - 1u, true));
  assert(wrapped.update(59000u, false));
  assert(wrapped.ready() && !wrapped.motion());
  assert(std::fabs(luxFromBh1750Raw(120) - 100.0f) < 0.01f);
  assert(luxFromBh1750Raw(0) == 0.0f);
}
""",
        encoding="utf-8",
    )
    binary = tmp_path / "sensor_contract"
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(FIRMWARE_INCLUDE),
            str(source),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run([str(binary)], check=True, capture_output=True, text=True)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@pytest.mark.asyncio
async def test_authenticated_sensor_state_reaches_world_with_source_and_expiry(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "sensor.sqlite3")
    await store.initialize()
    world = WorldModel(SQLiteWorldRepository(store))
    registry = DeviceRegistry(SQLiteDeviceRepository(store), world)
    descriptor = DeviceDescriptor(
        device_id="siro-node-01",
        adapter="esp32_mqtt",
        location="lab",
        properties={
            "power": DeviceProperty(type="boolean"),
            "motion": DeviceProperty(type="boolean"),
            "illuminance": DeviceProperty(type="number", unit="lx"),
        },
        actions={"light.set": DeviceAction(input_schema="light_set.v1")},
        availability_ttl_ms=20_000,
        privacy=Privacy.LOCAL_ONLY,
    )
    await registry.register(descriptor)
    now = datetime.now(UTC).replace(microsecond=0)
    payload = json.dumps(
        {
            "observed_at_epoch": int(now.timestamp()),
            "properties": {"power": False, "motion": True, "illuminance": 235.8},
        }
    ).encode()
    port = free_port()
    password_file = tmp_path / "passwords"
    username, password = "sensor-fixture", "fixture-password"  # pragma: allowlist secret
    password_file.write_text(f"{username}:{PasswordHasher().hash(password)}\n")
    broker = Broker(
        {
            "listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{port}"}},
            "plugins": {
                "amqtt.plugins.authentication.FileAuthPlugin": {"password_file": str(password_file)}
            },
        }
    )
    await broker.start()
    topic = f"siro/devices/{descriptor.device_id}/state"
    try:
        async with aiomqtt.Client(
            "127.0.0.1", port, username=username, password=password
        ) as observer:
            await observer.subscribe(topic, qos=1)
            async with aiomqtt.Client(
                "127.0.0.1", port, username=username, password=password
            ) as device:
                await device.publish(topic, payload, qos=1, retain=True)
            received = await asyncio.wait_for(observer.messages.__anext__(), 3)
            assert str(received.topic) == topic
            assert bytes(received.payload) == payload
            await MqttStateProjector(registry).handle_state(
                descriptor.device_id, bytes(received.payload)
            )
    finally:
        await broker.shutdown()

    for name, expected in (("power", False), ("motion", True), ("illuminance", 235.8)):
        current = await world.current(descriptor.device_id, name, now=now + timedelta(seconds=1))
        assert current.status is WorldStatus.KNOWN
        assert current.observation is not None
        assert current.observation.value == expected
        assert current.observation.source_id == "device:siro-node-01:esp32_mqtt"
        assert current.observation.observed_at == now
    # PIR motion alone must not claim room occupancy or absence.
    presence = await registry.room_presence("lab", now=now + timedelta(seconds=1))
    assert presence.status is WorldStatus.UNKNOWN and presence.present is None
    expired = await world.current(descriptor.device_id, "motion", now=now + timedelta(seconds=20))
    assert expired.status is WorldStatus.UNKNOWN and expired.reason == "expired"
