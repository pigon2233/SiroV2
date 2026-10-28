"""Retire an idle worker process so its model memory is returned; use reloads it."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable

DEFAULT_IDLE_SECONDS = 600.0
IDLE_ENV = "SIRO_WORKER_IDLE_SECONDS"


def idle_seconds(configured: float | None = None) -> float:
    """Explicit value wins, then SIRO_WORKER_IDLE_SECONDS; 0 disables unloading."""
    if configured is None:
        raw = os.environ.get(IDLE_ENV)
        if raw is None or raw == "":
            return DEFAULT_IDLE_SECONDS
        try:
            configured = float(raw)
        except ValueError:
            raise ValueError(f"{IDLE_ENV} must be a number of seconds") from None
    if not 0 <= configured <= 86_400:
        raise ValueError("worker idle seconds must be between 0 and 86400")
    return configured


class IdleRetirer:
    """Calls ``retire`` once ``seconds`` pass without ``touch``; ``retire`` must skip if busy."""

    def __init__(self, seconds: float, retire: Callable[[], Awaitable[None]]) -> None:
        self._seconds = seconds
        self._retire = retire
        self._handle: asyncio.TimerHandle | None = None
        self._task: asyncio.Task[None] | None = None

    def touch(self) -> None:
        if self._seconds <= 0:
            return
        self.cancel()
        self._handle = asyncio.get_running_loop().call_later(self._seconds, self._fire)

    def cancel(self) -> None:
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None

    def _fire(self) -> None:
        self._handle = None
        self._task = asyncio.ensure_future(self._retire())
