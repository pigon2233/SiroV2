"""Command channel between the backend (WSL) and the Windows shell that owns input and capture.

The shell long-polls ``next_command``, runs it, and posts ``submit_result``. Every input command
passes ``ControlGate`` first, expires quickly, and is never resent: a timeout is
``outcome_unknown`` (the click may have happened), not success.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from siro.services.computer_use.perception import Observation, sanitize
from siro.services.computer_use.safety import ControlGate, InputAction

INPUT_TIMEOUT = 12.0  # covers a cold helper start (C# compile) plus the 3 s input timeout
OBSERVE_TIMEOUT = 6.0
COMMAND_TTL = 5.0
FOCUS_TIMEOUT = 10.0
EXECUTOR_ONLINE_WITHIN = 10.0


@dataclass(frozen=True, slots=True)
class BridgeResult:
    ok: bool
    error: str = ""
    data: dict[str, Any] | None = None


class ComputerBridge:
    def __init__(self, gate: ControlGate, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.gate = gate
        self._clock = clock
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=8)
        self._pending: dict[str, asyncio.Future[BridgeResult]] = {}
        self._last_poll = float("-inf")
        self._waiting = 0  # shell polls currently parked on the queue
        self._seq = 0

    @property
    def executor_online(self) -> bool:
        return self._waiting > 0 or self._clock() - self._last_poll <= EXECUTOR_ONLINE_WITHIN

    def stop(self) -> None:
        """Emergency stop: latch the gate, drop queued commands, fail everything in flight."""
        self.gate.trip()
        while not self._queue.empty():
            self._queue.get_nowait()
        for future in self._pending.values():
            if not future.done():
                future.set_result(BridgeResult(False, "emergency_stop"))

    async def next_command(self, wait: float = 20.0) -> dict[str, Any] | None:
        self._last_poll = self._clock()
        self._waiting += 1
        try:
            command = await asyncio.wait_for(self._queue.get(), timeout=wait)
        except TimeoutError:
            return None
        finally:
            self._waiting -= 1
            self._last_poll = self._clock()
        if self._clock() > command["expires_at"] or command["id"] not in self._pending:
            return None  # stale or already settled: never run late
        return command

    def submit_result(
        self, command_id: str, ok: bool, error: str = "", data: dict[str, Any] | None = None
    ) -> bool:
        future = self._pending.get(command_id)
        if future is None or future.done():
            return False
        future.set_result(BridgeResult(ok, error, data))
        return True

    async def act(self, action: InputAction) -> BridgeResult:
        decision = self.gate.check(action)
        if not decision.allowed:
            return BridgeResult(False, decision.reason)
        return await self._request("input", asdict(action), INPUT_TIMEOUT, "outcome_unknown")

    async def focus(self, process: str) -> BridgeResult:
        """Ask the shell to bring an (allowlisted) program's window to the front."""
        if not self.gate.enabled:
            return BridgeResult(
                False, "emergency_stop" if self.gate.tripped else "control_disabled"
            )
        return await self._request("focus", {"process": process}, FOCUS_TIMEOUT, "focus_timeout")

    async def observe(self) -> tuple[Observation | None, str]:
        if self.gate.tripped:
            return None, "emergency_stop"
        result = await self._request("observe", {}, OBSERVE_TIMEOUT, "observe_timeout")
        if not result.ok or result.data is None:
            return None, result.error or "observe_failed"
        self._seq += 1
        observation = sanitize(result.data, seq=self._seq, now=self._clock())
        self.gate.set_screen(*observation.screen)
        return observation, ""

    async def _request(
        self, op: str, payload: dict[str, Any], timeout: float, timeout_error: str
    ) -> BridgeResult:
        if not self.executor_online:
            return BridgeResult(False, "executor_offline")
        command_id = uuid4().hex
        future: asyncio.Future[BridgeResult] = asyncio.get_running_loop().create_future()
        self._pending[command_id] = future
        command = {
            "id": command_id,
            "op": op,
            "payload": payload,
            "expires_at": self._clock() + COMMAND_TTL,
        }
        try:
            self._queue.put_nowait(command)
        except asyncio.QueueFull:
            del self._pending[command_id]
            return BridgeResult(False, "queue_full")
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except TimeoutError:
            future.cancel()
            return BridgeResult(False, timeout_error)
        finally:
            self._pending.pop(command_id, None)
