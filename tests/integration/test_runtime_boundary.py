from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sqlite3
import time
from pathlib import Path

import pytest

from siro.adapters.runtime import LocalRuntimeClient
from siro.ports.runtime import GrantToken, RuntimeRejected, RuntimeRequest


def grant(
    secret: bytes, grant_id: str, arguments: dict[str, object], *, expires_at: int
) -> GrantToken:
    encoded_arguments = json.dumps(arguments, separators=(",", ":")).encode()
    claims = {
        "grant_id": grant_id,
        "actor": "integration-owner",
        "capability": "filesystem.read",
        "scope": {"path": [str(arguments["path"])]},
        "args_hash": hashlib.sha256(encoded_arguments).hexdigest(),
        "expires_at_unix": expires_at,
        "uses_remaining": 1,
    }
    claims_json = json.dumps(claims, separators=(",", ":")).encode()
    signature = hmac.new(secret, claims_json, hashlib.sha256).hexdigest()
    return GrantToken(tuple(claims_json), signature)


async def start_runtime(
    binary: Path, socket: Path, database: Path, secret: bytes
) -> asyncio.subprocess.Process:
    socket.unlink(missing_ok=True)
    environment = os.environ.copy()
    environment.update(
        SIRO_RUNTIME_SOCKET=str(socket),
        SIRO_RUNTIME_SECRET=secret.decode(),
        SIRO_RUNTIME_DB=str(database),
        SIRO_RUNTIME_ROOTS=str(database.parent),
    )
    process = await asyncio.create_subprocess_exec(
        binary,
        env=environment,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    for _ in range(50):
        if socket.exists():
            return process
        await asyncio.sleep(0.02)
    process.terminate()
    await process.wait()
    raise AssertionError("runtime socket did not appear")


@pytest.mark.asyncio
async def test_real_rust_runtime_health_contract(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    binary = root / "target" / "debug" / "siro-runtime"
    if not binary.exists():
        pytest.skip("cargo test/build has not produced the runtime binary")
    socket = tmp_path / "runtime.sock"
    database = tmp_path / "runtime.sqlite3"
    secret = b"integration-only-secret"
    process = await start_runtime(binary, socket, database, secret)
    try:
        client = LocalRuntimeClient(socket)
        assert await client.health() == {
            "state": "healthy",
            "protocol_version": 1,
        }
        safe = tmp_path / "safe.txt"
        safe.write_text("runtime-readback", encoding="utf-8")
        arguments: dict[str, object] = {"path": str(safe)}
        expired = RuntimeRequest(
            "expired",
            "filesystem.read",
            arguments,
            "path",
            str(safe),
            grant(secret, "expired", arguments, expires_at=int(time.time()) - 1),
        )
        with pytest.raises(RuntimeRejected, match="expired_grant"):
            await client.execute(expired)

        forged_token = grant(secret, "forged", arguments, expires_at=int(time.time()) + 60)
        forged = RuntimeRequest(
            "forged",
            "filesystem.read",
            arguments,
            "path",
            str(safe),
            GrantToken(forged_token.claims_json, "00" * 32),
        )
        with pytest.raises(RuntimeRejected, match="forged_grant"):
            await client.execute(forged)

        original: dict[str, object] = {"path": str(safe)}
        changed = RuntimeRequest(
            "changed",
            "filesystem.read",
            {"path": str(tmp_path / "changed")},
            "path",
            str(tmp_path / "changed"),
            grant(secret, "changed", original, expires_at=int(time.time()) + 60),
        )
        with pytest.raises(RuntimeRejected, match="arguments_changed"):
            await client.execute(changed)

        token = grant(secret, "persisted-use", arguments, expires_at=int(time.time()) + 60)
        request = RuntimeRequest(
            "first-use",
            "filesystem.read",
            arguments,
            "path",
            str(safe),
            token,
        )
        assert (await client.execute(request)).result == {"text": "runtime-readback"}
        revoked_token = grant(secret, "revoked", arguments, expires_at=int(time.time()) + 60)
        await client.revoke("revoked")
    finally:
        process.terminate()
        await process.wait()

    process = await start_runtime(binary, socket, database, secret)
    try:
        client = LocalRuntimeClient(socket)
        assert (await client.execute(request)).result == {"text": "runtime-readback"}
        second_action = RuntimeRequest(
            "second-action",
            "filesystem.read",
            arguments,
            "path",
            str(safe),
            token,
        )
        with pytest.raises(RuntimeRejected, match="exhausted_grant"):
            await client.execute(second_action)
        conflict_arguments: dict[str, object] = {"path": str(tmp_path / "other.txt")}
        conflict = RuntimeRequest(
            "first-use",
            "filesystem.read",
            conflict_arguments,
            "path",
            str(tmp_path / "other.txt"),
            grant(secret, "conflict-grant", conflict_arguments, expires_at=int(time.time()) + 60),
        )
        with pytest.raises(RuntimeRejected, match="action_conflict"):
            await client.execute(conflict)
        revoked = RuntimeRequest(
            "revoked-after-restart",
            "filesystem.read",
            arguments,
            "path",
            str(safe),
            revoked_token,
        )
        with pytest.raises(RuntimeRejected, match="revoked_grant"):
            await client.execute(revoked)
    finally:
        process.terminate()
        await process.wait()

    with sqlite3.connect(database) as connection:
        decisions = connection.execute(
            "SELECT decision,reason FROM runtime_audit ORDER BY audit_id"
        ).fetchall()
    assert ("allow", "valid_grant") in decisions
    assert ("deny", "expired_grant") in decisions
    assert ("deny", "forged_grant") in decisions
    assert ("deny", "arguments_changed") in decisions
    assert ("deny", "exhausted_grant") in decisions
    assert ("deny", "action_conflict") in decisions
    assert ("deny", "revoked_grant") in decisions
