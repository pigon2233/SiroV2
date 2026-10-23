"""Loopback relay ingress writes validated ESP32 events through the gateway owner."""

from __future__ import annotations

import http.client
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from runpy import run_path
from threading import Thread
from typing import cast

import httpx
import pytest

from siro.core.devices import DeviceRegistry
from siro.core.world import WorldModel, WorldStatus
from siro.persistence.devices import SQLiteDeviceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteWorldRepository
from siro.services.devices.http_sensor import (
    Esp32HttpSensorProjector,
    http_sensor_descriptor,
    http_sensor_state_snapshot,
)
from siro.services.presentation.gateway import create_app

RelayHandler = cast(
    type[BaseHTTPRequestHandler],
    run_path(str(Path(__file__).resolve().parents[2] / "scripts" / "esp32_http_receiver.py"))[
        "RelayHandler"
    ],
)

TOKEN = "test-only-esp32-relay-token-with-32-bytes"
EVENT = b'{"device":"siro-node-01","event":"light_update","lux":235.8}'


@pytest.mark.asyncio
async def test_authenticated_loopback_event_persists_world_observation(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    world = WorldModel(SQLiteWorldRepository(store))
    registry = DeviceRegistry(SQLiteDeviceRepository(store), world)
    await registry.register(http_sensor_descriptor("siro-node-01"))
    projector = Esp32HttpSensorProjector(registry, device_id="siro-node-01")

    async def read_state() -> dict[str, object]:
        return await http_sensor_state_snapshot(
            world, device_id="siro-node-01", now=datetime.now(UTC)
        )

    app = create_app(
        on_esp32_http_event=projector.handle,
        on_esp32_http_state=read_state,
        esp32_relay_token=TOKEN,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 12345)),
        base_url="http://127.0.0.1:8000",
    ) as client:
        route = "/v1/devices/esp32/events"
        assert (await client.post(route, content=EVENT)).status_code == 401
        assert (
            await client.post(route, content=EVENT, headers={"X-SIRO-ESP32-Relay-Token": "wrong"})
        ).status_code == 401
        assert (
            await client.post(
                route,
                content=b'{"device":"siro-node-01","event":"light_update","lux":"bad"}',
                headers={
                    "X-SIRO-ESP32-Relay-Token": TOKEN,
                    "Content-Type": "application/json",
                },
            )
        ).status_code == 400
        assert (
            await client.post(
                route,
                content=EVENT,
                headers={"X-SIRO-ESP32-Relay-Token": TOKEN, "Content-Type": "text/plain"},
            )
        ).status_code == 415
        assert (
            await client.post(
                route,
                content=b"x" * 4097,
                headers={"X-SIRO-ESP32-Relay-Token": TOKEN, "Content-Type": "application/json"},
            )
        ).status_code == 413
        response = await client.post(
            route,
            content=EVENT,
            headers={"X-SIRO-ESP32-Relay-Token": TOKEN, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json() == {"accepted": True}
        assert (await client.get("/v1/devices/esp32/state")).status_code == 401
        session = await client.post("/v1/session", headers={"Origin": "http://127.0.0.1:8000"})
        assert session.status_code == 200
        state = await client.get(
            "/v1/devices/esp32/state",
            headers={"Authorization": f"Bearer {session.json()['token']}"},
        )
        assert state.status_code == 200
        assert state.json()["properties"]["illuminance"]["value"] == 235.8

    current = await world.current("siro-node-01", "illuminance", now=datetime.now(UTC))
    assert current.status is WorldStatus.KNOWN
    assert current.observation is not None
    assert current.observation.value == 235.8
    assert current.observation.source_id == "device:siro-node-01:esp32_http"
    assert current.observation.expires_at is not None
    assert current.observation.expires_at - current.observation.observed_at == timedelta(seconds=20)
    stale = await http_sensor_state_snapshot(
        world, device_id="siro-node-01", now=current.observation.observed_at + timedelta(seconds=21)
    )
    assert stale["properties"]["illuminance"] == {"status": "unknown", "value": None}


@pytest.mark.asyncio
async def test_disabled_or_non_loopback_ingress_never_calls_projector() -> None:
    received: list[bytes] = []

    async def record(payload: bytes, *, now: datetime) -> None:
        received.append(payload)

    disabled = create_app(on_esp32_http_event=record)
    enabled = create_app(on_esp32_http_event=record, esp32_relay_token=TOKEN)
    for app, source, expected in (
        (disabled, "127.0.0.1", 503),
        (enabled, "192.0.2.10", 403),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=(source, 12345)),
            base_url="http://127.0.0.1:8000",
        ) as client:
            response = await client.post(
                "/v1/devices/esp32/events",
                content=EVENT,
                headers={"X-SIRO-ESP32-Relay-Token": TOKEN},
            )
            assert response.status_code == expected
    assert not received


def test_windows_relay_forwards_once_and_reports_downstream_result() -> None:
    received: list[bytes] = []
    downstream_status = [200]

    class GatewayHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            received.append(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.path == "/v1/devices/esp32/events"
            assert self.headers["X-SIRO-ESP32-Relay-Token"] == TOKEN
            self.send_response(downstream_status[0])
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    gateway = HTTPServer(("127.0.0.1", 0), GatewayHandler)
    relay_handler = type(
        "TestRelayHandler",
        (RelayHandler,),
        {"allowed_ip": "127.0.0.1", "gateway_port": gateway.server_port, "token": TOKEN},
    )
    relay = HTTPServer(("127.0.0.1", 0), relay_handler)
    gateway_thread = Thread(target=gateway.serve_forever, daemon=True)
    relay_thread = Thread(target=relay.serve_forever, daemon=True)
    gateway_thread.start()
    relay_thread.start()
    try:
        for expected_gateway, expected_relay in ((200, 200), (503, 502)):
            downstream_status[0] = expected_gateway
            connection = http.client.HTTPConnection("127.0.0.1", relay.server_port, timeout=2)
            try:
                connection.request(
                    "POST", "/event", EVENT, headers={"Content-Type": "application/json"}
                )
                response = connection.getresponse()
                assert response.status == expected_relay
                response.read()
            finally:
                connection.close()
        assert received == [EVENT, EVENT]
    finally:
        relay.shutdown()
        gateway.shutdown()
        relay.server_close()
        gateway.server_close()
        relay_thread.join(timeout=2)
        gateway_thread.join(timeout=2)
