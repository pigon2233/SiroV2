"""OTA manifest and image are served only to the loopback relay holding the token."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from siro.services.presentation.gateway import create_app

TOKEN = "test-only-esp32-relay-token-with-32-bytes"
HEADERS = {"X-SIRO-ESP32-Relay-Token": TOKEN}


def _client(app: object, host: str = "127.0.0.1") -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=(host, 1)),  # type: ignore[arg-type]
        base_url="http://127.0.0.1:8000",
    )


@pytest.mark.asyncio
async def test_manifest_and_image(tmp_path: Path) -> None:
    image = tmp_path / "node.bin"
    image.write_bytes(b"firmware")
    app = create_app(esp32_relay_token=TOKEN, esp32_ota_image=image, esp32_ota_version="1.0.0")
    async with _client(app) as client:
        assert (await client.get("/v1/devices/esp32/ota/manifest")).status_code == 401
        manifest = await client.get("/v1/devices/esp32/ota/manifest", headers=HEADERS)
        assert manifest.json()["sha256"] == hashlib.sha256(b"firmware").hexdigest()
        body = await client.get("/v1/devices/esp32/ota/firmware", headers=HEADERS)
        assert body.content == b"firmware"
    async with _client(app, host="192.168.1.9") as remote:
        reply = await remote.get("/v1/devices/esp32/ota/manifest", headers=HEADERS)
        assert reply.status_code == 403


@pytest.mark.asyncio
async def test_disabled_without_image() -> None:
    async with _client(create_app(esp32_relay_token=TOKEN)) as client:
        reply = await client.get("/v1/devices/esp32/ota/manifest", headers=HEADERS)
        assert reply.status_code == 503
