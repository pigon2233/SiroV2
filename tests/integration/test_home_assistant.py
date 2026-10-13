from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from websockets.asyncio.server import ServerConnection, serve

from siro.adapters.home_assistant import (
    HomeAssistantAdapter,
    HomeAssistantAuthError,
    HomeAssistantConfig,
    HomeAssistantEntityMapping,
    HomeAssistantStateChange,
    LightActionStatus,
    descriptor_for,
    load_home_assistant_config,
    parse_state_changed,
    state_value,
)
from siro.core.devices import DeviceAvailability, DeviceRegistry
from siro.core.world import WorldModel, WorldStatus
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteWorldRepository


def mapping(entity_id: str, kind: str, location: str = "bedroom") -> HomeAssistantEntityMapping:
    return HomeAssistantEntityMapping.model_validate(
        {"entity_id": entity_id, "kind": kind, "location": location}
    )


def config(base_url: str = "http://ha.test:8123") -> HomeAssistantConfig:
    return HomeAssistantConfig(
        base_url=base_url,
        token=SecretStr("private-ha-token"),  # pragma: allowlist secret
        entities=(
            mapping("light.bedroom", "light"),
            mapping("binary_sensor.entry_presence", "presence", "entry"),
            mapping("sensor.bedroom_temperature", "temperature"),
        ),
    )


def test_t28_descriptor_mapping_values_and_secret_redaction() -> None:
    settings = config()
    assert "private-ha-token" not in repr(settings)  # pragma: allowlist secret

    light, presence, temperature = (descriptor_for(item) for item in settings.entities)
    assert light.device_id == "ha:light.bedroom"
    assert light.location == "bedroom"
    assert set(light.actions) == {"light.set"}
    assert set(presence.properties) == {"presence"}
    assert set(temperature.properties) == {"temperature"}

    unavailable = httpx.Response(200, json={"entity_id": "light.bedroom", "state": "x"})
    parsed = unavailable.json()
    from siro.adapters.home_assistant import HomeAssistantState

    light_state = HomeAssistantState.model_validate(parsed)
    assert state_value(settings.entities[0], light_state) == (
        DeviceAvailability.UNKNOWN,
        None,
    )
    temperature_state = HomeAssistantState(entity_id="sensor.bedroom_temperature", state="24.5")
    assert state_value(settings.entities[2], temperature_state) == (
        DeviceAvailability.ONLINE,
        24.5,
    )


def test_t28_file_config_reads_token_only_from_environment(tmp_path: Path) -> None:
    config_path = tmp_path / "home-assistant.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "http://ha.test:8123",
                "token_env": "SIRO_HA_TOKEN",
                "entities": [
                    {"entity_id": "light.bedroom", "kind": "light", "location": "bedroom"}
                ],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_home_assistant_config(
        config_path,
        environ={"SIRO_HA_TOKEN": "runtime-only-token"},  # pragma: allowlist secret
    )
    assert loaded.token.get_secret_value() == "runtime-only-token"  # pragma: allowlist secret
    assert "runtime-only-token" not in repr(loaded)  # pragma: allowlist secret
    assert "runtime-only-token" not in config_path.read_text()  # pragma: allowlist secret
    with pytest.raises(ValueError, match="SIRO_HA_TOKEN"):
        load_home_assistant_config(config_path, environ={})


@pytest.mark.asyncio
async def test_t28_rest_snapshot_and_event_project_into_registry(tmp_path: Path) -> None:
    now = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    snapshot = [
        {
            "entity_id": "light.bedroom",
            "state": "off",
            "last_updated": now.isoformat(),
        },
        {
            "entity_id": "binary_sensor.entry_presence",
            "state": "unavailable",
            "last_updated": now.isoformat(),
        },
        {
            "entity_id": "sensor.bedroom_temperature",
            "state": "23.75",
            "last_updated": now.isoformat(),
        },
    ]

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=snapshot)

    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()
    registry = DeviceRegistry(
        SQLiteDeviceRepository(store), WorldModel(SQLiteWorldRepository(store))
    )
    async with HomeAssistantAdapter(config(), transport=httpx.MockTransport(handler)) as adapter:
        await adapter.sync_registry(registry)
        presence = await registry.available("ha:binary_sensor.entry_presence", now=now)
        assert presence is not None and presence.availability is DeviceAvailability.UNKNOWN

        changed = HomeAssistantStateChange.model_validate(
            {
                "entity_id": "binary_sensor.entry_presence",
                "old_state": snapshot[1],
                "new_state": {
                    "entity_id": "binary_sensor.entry_presence",
                    "state": "on",
                    "last_updated": now.isoformat(),
                },
                "occurred_at": now,
            }
        )
        await adapter.project_change(registry, changed)

    room = await registry.room_presence("entry", now=now)
    assert room.status is WorldStatus.KNOWN and room.present is True


@pytest.mark.asyncio
async def test_t28_service_success_requires_readback_and_action_ledger() -> None:
    current_state = "off"
    post_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal current_state, post_count
        assert request.headers["authorization"] == "Bearer private-ha-token"
        if request.method == "POST":
            post_count += 1
            if post_count == 2:
                current_state = "on"
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={
                "entity_id": "light.bedroom",
                "state": current_state,
                "attributes": {},
            },
        )

    async with HomeAssistantAdapter(config(), transport=httpx.MockTransport(handler)) as adapter:
        unchanged = await adapter.set_light("a-1", "light.bedroom", True)
        assert unchanged.status is LightActionStatus.STATE_UNCHANGED
        assert unchanged.observed_state == "off"
        duplicate = await adapter.set_light("a-1", "light.bedroom", True)
        assert duplicate == unchanged
        assert post_count == 1
        with pytest.raises(ValueError, match="different arguments"):
            await adapter.set_light("a-1", "light.bedroom", False)

        confirmed = await adapter.set_light("a-2", "light.bedroom", True)
        assert confirmed.status is LightActionStatus.CONFIRMED
        assert confirmed.observed_state == "on"


@pytest.mark.asyncio
async def test_t28_revoked_credentials_and_unavailable_device_degrade() -> None:
    async def revoked(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    async with HomeAssistantAdapter(config(), transport=httpx.MockTransport(revoked)) as adapter:
        result = await adapter.set_light("revoked-1", "light.bedroom", True)
        assert result.status is LightActionStatus.AUTH_REVOKED
        with pytest.raises(HomeAssistantAuthError, match="credential"):
            await adapter.states()

    async def unavailable(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"entity_id": "light.bedroom", "state": "unavailable"})

    async with HomeAssistantAdapter(
        config(), transport=httpx.MockTransport(unavailable)
    ) as adapter:
        result = await adapter.set_light("offline-1", "light.bedroom", True)
        assert result.status is LightActionStatus.UNAVAILABLE
        assert result.observed_state == "unavailable"


def state_event() -> dict[str, object]:
    return {
        "id": 1,
        "type": "event",
        "event": {
            "event_type": "state_changed",
            "data": {
                "entity_id": "light.bedroom",
                "old_state": {"entity_id": "light.bedroom", "state": "off"},
                "new_state": {"entity_id": "light.bedroom", "state": "on"},
            },
            "time_fired": "2026-09-25T12:00:00Z",
        },
    }


@pytest.mark.asyncio
async def test_t28_websocket_auth_subscribe_and_state_event() -> None:
    received: list[dict[str, object]] = []

    async def ws_handler(websocket: ServerConnection) -> None:
        await websocket.send(json.dumps({"type": "auth_required", "ha_version": "2026.9.0"}))
        auth = json.loads(await websocket.recv())
        received.append(auth)
        await websocket.send(json.dumps({"type": "auth_ok", "ha_version": "2026.9.0"}))
        subscription = json.loads(await websocket.recv())
        received.append(subscription)
        await websocket.send(json.dumps({"id": 1, "type": "result", "success": True}))
        await websocket.send(json.dumps(state_event()))

    async with serve(ws_handler, "127.0.0.1", 0) as server:
        assert server.sockets
        port = next(iter(server.sockets)).getsockname()[1]
        async with HomeAssistantAdapter(config(f"http://127.0.0.1:{port}")) as adapter:
            event = await anext(adapter.state_changes())

    assert received == [
        {"type": "auth", "access_token": "private-ha-token"},  # pragma: allowlist secret
        {"id": 1, "type": "subscribe_events", "event_type": "state_changed"},
    ]
    assert event.entity_id == "light.bedroom"
    assert event.old_state is not None and event.old_state.state == "off"
    assert event.new_state is not None and event.new_state.state == "on"
    assert event.occurred_at == datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    assert parse_state_changed(json.dumps({"type": "pong"})) is None
