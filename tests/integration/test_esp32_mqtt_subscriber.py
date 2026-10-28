from __future__ import annotations

import asyncio
import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import aiomqtt
import pytest
from amqtt.broker import Broker  # type: ignore[import-untyped]

from siro.core.devices import DeviceAvailability, DeviceRegistry
from siro.core.world import WorldModel, WorldStatus
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteWorldRepository
from siro.services.devices.mqtt_subscriber import Esp32MqttSubscriber, mqtt_sensor_descriptor


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@pytest.mark.asyncio
async def test_subscriber_projects_state_and_availability_from_loopback_broker(
    tmp_path: Path,
) -> None:
    port = free_port()
    broker = Broker(
        {
            "listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{port}"}},
            "plugins": {
                "amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True}
            },
        }
    )
    await broker.start()
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repository = SQLiteDeviceRepository(store)
    world = WorldModel(SQLiteWorldRepository(store))
    registry = DeviceRegistry(repository, world)
    await registry.register(mqtt_sensor_descriptor("node-mqtt", location="lab"))
    subscriber = Esp32MqttSubscriber(registry, host="127.0.0.1", port=port, device_id="node-mqtt")
    subscriber.start()
    try:
        await asyncio.wait_for(subscriber.connected.wait(), 5)
        async with aiomqtt.Client("127.0.0.1", port) as publisher:
            await publisher.publish("siro/devices/node-mqtt/availability", b"online", qos=1)
            # A different device and malformed payloads must not break the loop.
            await publisher.publish("siro/devices/other/state", b"{}", qos=1)
            await publisher.publish("siro/devices/node-mqtt/state", b"not json", qos=1)
            payload = {
                "observed_at_epoch": int(datetime.now(UTC).timestamp()),
                "properties": {"motion": True, "illuminance": 231.5, "button_down": False},
            }
            await publisher.publish("siro/devices/node-mqtt/state", json.dumps(payload), qos=1)
        for _ in range(50):
            current = await world.current("node-mqtt", "illuminance", now=datetime.now(UTC))
            if current.status is WorldStatus.KNOWN:
                break
            await asyncio.sleep(0.1)
        assert current.observation is not None and current.observation.value == 231.5
        assert current.observation.source_id == "device:node-mqtt:esp32_mqtt"
        motion = await world.current("node-mqtt", "motion", now=datetime.now(UTC))
        assert motion.observation is not None and motion.observation.value is True
        record = await repository.get("node-mqtt")
        assert record is not None and record.availability is DeviceAvailability.ONLINE
        async with aiomqtt.Client("127.0.0.1", port) as publisher:
            await publisher.publish("siro/devices/node-mqtt/availability", b"offline", qos=1)
        for _ in range(50):
            record = await repository.get("node-mqtt")
            if record is not None and record.availability is DeviceAvailability.OFFLINE:
                break
            await asyncio.sleep(0.1)
        assert record is not None and record.availability is DeviceAvailability.OFFLINE
    finally:
        await subscriber.close()
        await broker.shutdown()


@pytest.mark.asyncio
async def test_subscriber_survives_unreachable_broker_and_closes(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    registry = DeviceRegistry(
        SQLiteDeviceRepository(store), WorldModel(SQLiteWorldRepository(store))
    )
    subscriber = Esp32MqttSubscriber(
        registry, host="127.0.0.1", port=free_port(), device_id="node-mqtt", max_backoff=0.1
    )
    subscriber.start()
    await asyncio.sleep(0.3)
    assert not subscriber.connected.is_set()
    await subscriber.close()


@pytest.mark.asyncio
async def test_mqtt_state_snapshot_reports_known_and_unknown(tmp_path: Path) -> None:
    from siro.services.devices.mqtt_subscriber import mqtt_sensor_state_snapshot

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    world = WorldModel(SQLiteWorldRepository(store))
    registry = DeviceRegistry(SQLiteDeviceRepository(store), world)
    await registry.register(mqtt_sensor_descriptor("node-mqtt"))
    now = datetime.now(UTC)
    await registry.record_property("node-mqtt", "illuminance", 12.5, observed_at=now)
    snapshot = await mqtt_sensor_state_snapshot(world, device_id="node-mqtt", now=now)
    assert snapshot["device_id"] == "node-mqtt"
    assert snapshot["properties"]["illuminance"]["value"] == 12.5
    assert snapshot["properties"]["illuminance"]["source_id"] == "device:node-mqtt:esp32_mqtt"
    assert snapshot["properties"]["motion"] == {"status": "unknown", "value": None}


@pytest.mark.asyncio
async def test_esp32_state_endpoint_merges_mqtt_device_and_keeps_http_fields(
    tmp_path: Path,
) -> None:
    import httpx

    from siro.services.presentation.gateway import create_app

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    world = WorldModel(SQLiteWorldRepository(store))
    registry = DeviceRegistry(SQLiteDeviceRepository(store), world)
    await registry.register(mqtt_sensor_descriptor("node-mqtt"))
    await registry.record_property("node-mqtt", "illuminance", 7.0, observed_at=datetime.now(UTC))

    async def mqtt_state() -> dict[str, object]:
        from siro.services.devices.mqtt_subscriber import mqtt_sensor_state_snapshot

        return await mqtt_sensor_state_snapshot(world, device_id="node-mqtt", now=datetime.now(UTC))

    async def http_state() -> dict[str, object]:
        return {"device_id": "siro-node-01", "properties": {}}

    for http, expected_keys in (
        (http_state, {"device_id", "properties", "mqtt"}),
        (None, {"mqtt"}),
    ):
        app = create_app(on_esp32_mqtt_state=mqtt_state, on_esp32_http_state=http)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 12345)),
            base_url="http://127.0.0.1:8000",
        ) as client:
            session = await client.post("/v1/session", headers={"Origin": "http://127.0.0.1:8000"})
            state = await client.get(
                "/v1/devices/esp32/state",
                headers={"Authorization": f"Bearer {session.json()['token']}"},
            )
        assert state.status_code == 200
        body = state.json()
        assert set(body) == expected_keys
        assert body["mqtt"]["properties"]["illuminance"]["value"] == 7.0
    disabled = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=disabled, client=("127.0.0.1", 12345)),
        base_url="http://127.0.0.1:8000",
    ) as client:
        session = await client.post("/v1/session", headers={"Origin": "http://127.0.0.1:8000"})
        off = await client.get(
            "/v1/devices/esp32/state",
            headers={"Authorization": f"Bearer {session.json()['token']}"},
        )
    assert off.status_code == 503
