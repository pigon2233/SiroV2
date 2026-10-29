"""Monitor-page host load: token-gated, read-only, shaped for display."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from siro.services.presentation.gateway import create_app
from siro.services.presentation.system_stats import read_system_stats


def test_stats_shape_and_bounds(tmp_path: Path) -> None:
    stats = read_system_stats(tmp_path)
    assert 0 <= float(stats["cpu_percent"]) <= 100  # type: ignore[arg-type]
    memory = stats["memory"]
    assert isinstance(memory, dict) and 0 <= memory["percent"] <= 100
    disks = stats["disks"]
    assert isinstance(disks, list) and disks
    assert all(0 <= disk["percent"] <= 100 for disk in disks)
    assert stats["environment"] in {"wsl", "linux", "windows", "darwin"}


@pytest.mark.asyncio
async def test_endpoint_requires_session_token() -> None:
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 12345)),
        base_url="http://127.0.0.1:8000",
    ) as client:
        assert (await client.get("/v1/system/stats")).status_code == 401
        session = await client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"})
        token = session.json()["token"]
        response = await client.get(
            "/v1/system/stats", headers={"authorization": f"Bearer {token}"}
        )
    assert response.status_code == 200
    assert "memory" in response.json()
