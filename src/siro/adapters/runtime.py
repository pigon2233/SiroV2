"""Bounded Unix-socket client for the privileged Rust Runtime."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from siro.ports.runtime import (
    RuntimeRejected,
    RuntimeRequest,
    RuntimeResult,
    RuntimeUnavailable,
)

MAX_RPC_BYTES = 64 * 1024


class LocalRuntimeClient:
    def __init__(self, socket_path: Path, *, timeout_seconds: float = 2.0) -> None:
        self._socket_path = socket_path
        self._timeout = timeout_seconds

    async def health(self) -> dict[str, object]:
        response = await self._call({"method": "health"})
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeUnavailable("runtime returned an invalid health result")
        return {str(key): value for key, value in result.items()}

    async def execute(self, request: RuntimeRequest) -> RuntimeResult:
        response = await self._call(
            {
                "method": "execute",
                "action_id": request.action_id,
                "capability": request.capability,
                "arguments": request.arguments,
                "scope_key": request.scope_key,
                "scope_value": request.scope_value,
                "grant": {
                    "claims_json": list(request.grant.claims_json),
                    "signature_hex": request.grant.signature_hex,
                },
            }
        )
        if not response.get("ok"):
            error = response.get("error")
            raise RuntimeRejected(error if isinstance(error, str) else "runtime rejected request")
        return RuntimeResult(response.get("result"))

    async def revoke(self, grant_id: str) -> None:
        response = await self._call({"method": "revoke", "grant_id": grant_id})
        if not response.get("ok"):
            raise RuntimeRejected("runtime rejected revocation")

    async def _call(self, request: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(request, separators=(",", ":")).encode() + b"\n"
        if len(encoded) > MAX_RPC_BYTES:
            raise RuntimeUnavailable("runtime request exceeds 64 KiB")
        writer: asyncio.StreamWriter | None = None
        try:
            reader, connected_writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self._socket_path, limit=MAX_RPC_BYTES + 1),
                timeout=self._timeout,
            )
            writer = connected_writer
            connected_writer.write(encoded)
            await asyncio.wait_for(connected_writer.drain(), timeout=self._timeout)
            raw = await asyncio.wait_for(reader.readline(), timeout=self._timeout)
        except (OSError, TimeoutError, asyncio.LimitOverrunError) as error:
            raise RuntimeUnavailable("runtime is unavailable") from error
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()
        if not raw or len(raw) > MAX_RPC_BYTES or not raw.endswith(b"\n"):
            raise RuntimeUnavailable("runtime returned an invalid bounded response")
        try:
            response = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeUnavailable("runtime returned invalid JSON") from error
        if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
            raise RuntimeUnavailable("runtime returned an invalid response")
        return response
