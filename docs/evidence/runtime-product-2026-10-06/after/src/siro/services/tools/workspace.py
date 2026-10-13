"""Owned, unprivileged Rust read-only workspace; authorization stays in the tool path."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from stat import S_ISREG
from uuid import uuid4

from siro.adapters.runtime import LocalRuntimeClient
from siro.ports.models import ToolDefinition
from siro.ports.runtime import GrantToken, RuntimeRequest, RuntimeUnavailable
from siro.services.tools.execution import ExecutionContext

WORKSPACE_TOOLS = tuple(
    ToolDefinition(
        "filesystem." + action,
        description + " Only the owner-selected workspace is allowed. Use a relative path. "
        "Never bypass a workspace refusal with computer.execute.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    )
    for action, description in (
        ("read", "Read a small UTF-8 text file (up to 8 KiB)."),
        ("list", 'List names in a workspace directory; use path="." for its root.'),
    )
)


class WorkspaceRuntime:
    def __init__(self, root: Path, binary: Path) -> None:
        self.root = root.expanduser().resolve()
        self._binary = binary.resolve()
        self._process: asyncio.subprocess.Process | None = None
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._client: LocalRuntimeClient | None = None
        self._secret = secrets.token_hex(32).encode()
        self.error: str | None = None

    @property
    def available(self) -> bool:
        return (
            self._process is not None
            and self._process.returncode is None
            and self._client is not None
        )

    async def start(self) -> None:
        if self.available:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        if not self._binary.is_file():
            self.error = "runtime_binary_missing"
            return
        await self.close()
        self._temporary = tempfile.TemporaryDirectory(prefix="siro-read-")
        directory = Path(self._temporary.name)
        # The private socket/ledger are outside the readable workspace. Do not inherit model keys.
        environment = {
            "PATH": os.defpath,
            "SIRO_RUNTIME_ROOTS": str(self.root),
            "SIRO_RUNTIME_SOCKET": str(directory / "rpc.sock"),
            "SIRO_RUNTIME_DB": str(directory / "ledger.sqlite3"),
            "SIRO_RUNTIME_SECRET": self._secret.decode(),
        }
        try:
            self._process = await asyncio.create_subprocess_exec(
                str(self._binary),
                env=environment,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            client = LocalRuntimeClient(directory / "rpc.sock")
            for _ in range(50):
                if self._process.returncode is not None:
                    raise RuntimeUnavailable("runtime exited")
                if (directory / "rpc.sock").exists():
                    await client.health()
                    self._client = client
                    self.error = None
                    return
                await asyncio.sleep(0.02)
            raise RuntimeUnavailable("runtime startup timeout")
        except Exception as error:
            self.error = type(error).__name__
            await self.close()
        except asyncio.CancelledError:
            await self.close()
            raise

    async def execute(
        self, capability: str, arguments: dict[str, object], context: ExecutionContext
    ) -> object:
        context.check()
        if not context.authorized:
            raise PermissionError("trusted tool approval is required")
        if capability not in {"filesystem.read", "filesystem.list"}:
            raise PermissionError("workspace is read-only")
        raw = arguments.get("path")
        if not isinstance(raw, str) or not raw or len(raw) > 4096:
            raise ValueError("path must be a non-empty workspace path")
        path = await asyncio.to_thread((self.root / raw).resolve, strict=True)
        if not path.is_relative_to(self.root):
            raise PermissionError("path is outside the workspace")
        if capability == "filesystem.read":
            stat = await asyncio.to_thread(path.stat)
            if not S_ISREG(stat.st_mode) or stat.st_size > 8192:
                raise ValueError("workspace read requires a regular UTF-8 file up to 8 KiB")
        if not self.available or self._client is None:
            raise RuntimeUnavailable("workspace runtime is unavailable")
        context.check()
        args: dict[str, object] = {"path": str(path)}
        claims = {
            "grant_id": str(uuid4()),
            "actor": "siro-owner",
            "capability": capability,
            "scope": {"path": [str(path)]},
            "args_hash": hashlib.sha256(
                json.dumps(args, ensure_ascii=False, separators=(",", ":")).encode()
            ).hexdigest(),
            "expires_at_unix": int(time.time()) + 10,
            "uses_remaining": 1,
        }
        encoded = json.dumps(claims, separators=(",", ":")).encode()
        grant = GrantToken(
            tuple(encoded), hmac.new(self._secret, encoded, hashlib.sha256).hexdigest()
        )
        result = await self._client.execute(
            RuntimeRequest(str(uuid4()), capability, args, "path", str(path), grant)
        )
        context.check()
        return result.result

    async def close(self) -> None:
        self._client = None
        process = self._process
        if process is not None:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 1)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            self._process = None
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
