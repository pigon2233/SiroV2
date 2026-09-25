from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from siro.adapters.runtime import LocalRuntimeClient
from siro.ports.runtime import GrantToken as PortGrantToken
from siro.ports.runtime import RuntimeRejected, RuntimeRequest, RuntimeUnavailable


@asynccontextmanager
async def rpc_fixture(path: Path, response: dict[str, object]) -> AsyncIterator[None]:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readline()
        writer.write(json.dumps(response).encode() + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_unix_server(handle, path)
    try:
        yield
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_health_schema_and_missing_runtime_fail_closed(tmp_path: Path) -> None:
    socket = tmp_path / "runtime.sock"
    client = LocalRuntimeClient(socket, timeout_seconds=0.2)
    with pytest.raises(RuntimeUnavailable):
        await client.health()
    async with rpc_fixture(
        socket, {"ok": True, "result": {"state": "healthy", "protocol_version": 1}, "error": None}
    ):
        assert await client.health() == {"state": "healthy", "protocol_version": 1}


@pytest.mark.asyncio
async def test_denial_is_explicit_and_oversized_requests_never_connect(tmp_path: Path) -> None:
    socket = tmp_path / "runtime.sock"
    client = LocalRuntimeClient(socket)
    request = RuntimeRequest(
        "action-1",
        "filesystem.read",
        {"path": "/outside"},
        "path",
        "/outside",
        PortGrantToken((), "invalid"),
    )
    async with rpc_fixture(socket, {"ok": False, "result": None, "error": "forged_grant"}):
        with pytest.raises(RuntimeRejected, match="forged_grant"):
            await client.execute(request)

    huge = RuntimeRequest(
        "action-2",
        "filesystem.read",
        {"path": "x" * (64 * 1024)},
        "path",
        "/safe",
        PortGrantToken((), "invalid"),
    )
    with pytest.raises(RuntimeUnavailable, match="64 KiB"):
        await client.execute(huge)
