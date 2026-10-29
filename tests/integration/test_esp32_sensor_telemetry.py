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
from siro.core.devices import DeviceDescriptor, DeviceProperty, DeviceRegistry
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
  auto run = [](PirMotionSampler &p, uint32_t from, uint32_t to, bool level) {
    bool changed = false;
    for (uint32_t t = from; t < to; t += 20) changed |= p.update(t, level);
    return changed;
  };
  assert(!pir.update(60999, true));  // no motion during warm-up
  assert(!pir.ready());
  assert(pir.update(61000, false));  // first reliable absence is emitted
  assert(pir.ready() && !pir.motion());

  // One isolated 0.8 s pulse is not presence.
  assert(!run(pir, 61020, 61820, true));
  assert(!run(pir, 61820, 75000, false));
  assert(!pir.motion());
  // A bounce shorter than the debounce is not even a pulse.
  assert(!run(pir, 75000, 75100, true));
  assert(!run(pir, 75100, 76000, false));
  assert(pir.pulsesInWindow(76000) == 0);

  // This module's real pattern while someone moves: ~1 s HIGH, ~2.5 s LOW, repeating.
  bool rose = false;
  uint32_t t = 80000;
  for (int cycle = 0; cycle < 4; ++cycle) {
    rose |= run(pir, t, t + 1000, true);
    rose |= run(pir, t + 1000, t + 3500, false);
    t += 3500;
  }
  assert(rose && pir.motion());  // second pulse inside the window confirms presence
  // After the last pulse, presence is held and then released.
  assert(!run(pir, t, t + 20000, false));
  assert(pir.motion());
  assert(run(pir, t + 20000, t + 45000, false));
  assert(!pir.motion());

  // A single sustained HIGH is presence by itself.
  const uint32_t s = t + 50000;
  assert(!run(pir, s - 20, s, false));
  assert(run(pir, s, s + 1700, true));
  assert(pir.motion());

  pir.invalidate();
  assert(!pir.ready());
  assert(!pir.update(s + 5000, false));
  assert(!pir.update(s + 5499, false));
  assert(pir.update(s + 5500, false));  // a fresh stable reading is required after reconnect
  assert(pir.ready());

  PirMotionSampler wrapped(UINT32_MAX - 1000u);
  assert(!wrapped.update(UINT32_MAX - 1u, true));
  assert(wrapped.update(59000u, false));
  assert(wrapped.ready() && !wrapped.motion());
  assert(std::fabs(luxFromBh1750Raw(120) - 100.0f) < 0.01f);
  assert(luxFromBh1750Raw(0) == 0.0f);

  ButtonSampler button;
  button.reset(true); // held during boot is not counted as a new press
  assert(button.down() && button.pressCount() == 0);
  assert(!button.update(10, false));
  assert(!button.update(59, false));
  assert(button.update(60, false));
  assert(!button.down());
  assert(!button.update(70, true));
  assert(!button.update(90, false)); // bounce cancels the candidate
  assert(!button.update(100, true));
  assert(!button.update(149, true));
  assert(button.update(150, true));
  assert(button.down() && button.pressCount() == 1);
  assert(!button.update(151, true));
  assert(!button.update(UINT32_MAX - 25u, false));
  assert(!button.update(23u, false));
  assert(button.update(24u, false)); // millis rollover
  assert(!button.down() && button.pressCount() == 1);
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
            "motion": DeviceProperty(type="boolean"),
            "illuminance": DeviceProperty(type="number", unit="lx"),
            "button_down": DeviceProperty(type="boolean"),
            "button_press_count": DeviceProperty(type="number"),
        },
        actions={},
        availability_ttl_ms=20_000,
        privacy=Privacy.LOCAL_ONLY,
    )
    await registry.register(descriptor)
    now = datetime.now(UTC).replace(microsecond=0)
    payload = json.dumps(
        {
            "observed_at_epoch": int(now.timestamp()),
            "properties": {
                "motion": True,
                "illuminance": 235.8,
                "button_down": False,
                "button_press_count": 3,
            },
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

    for name, expected in (
        ("motion", True),
        ("illuminance", 235.8),
        ("button_down", False),
        ("button_press_count", 3),
    ):
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
