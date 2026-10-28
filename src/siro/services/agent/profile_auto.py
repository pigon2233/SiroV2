"""Idle-time owner profile rebuild: runs on SIRO's own judgment, never during foreground work."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from siro.contracts.events import UserTextEvent

LOGGER = logging.getLogger(__name__)
MAX_SEEN = 2000
MAX_BACKOFF_SECONDS = 6 * 3600


class Builder(Protocol):
    async def build(self, events: Sequence[UserTextEvent]) -> Sequence[object]: ...


class Source(Protocol):
    async def unseen_user_events(self) -> list[UserTextEvent]: ...


class ProfileAuto:
    def __init__(
        self,
        service: Builder,
        source: Source,
        busy: Callable[[], bool],
        *,
        enabled: bool = True,
        idle_seconds: float = 60,
        poll_seconds: float = 5,
        cooldown_seconds: float = 30 * 60,
        min_unseen: int = 10,
        max_age_seconds: float = 6 * 3600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._service, self._source, self._busy = service, source, busy
        self.enabled = enabled
        self._idle, self._poll = idle_seconds, poll_seconds
        self._cooldown, self._min_unseen = cooldown_seconds, min_unseen
        self._max_age = max_age_seconds
        self._clock = clock
        now = self._clock()
        self._last_foreground = now
        self._last_run_clock = now  # no run yet: age counts from start
        self._next_attempt = now
        self._failures = 0
        self._seen: set[UUID] = set()
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._work: asyncio.Task[None] | None = None
        self.state = "waiting" if enabled else "disabled"
        self.last_run: str | None = None

    def snapshot(self) -> dict[str, object]:
        return {"enabled": self.enabled, "state": self.state, "last_run": self.last_run}

    async def start(self) -> None:
        if self._task is None and self.enabled:
            self._task = asyncio.create_task(self._loop(), name="siro-profile-auto")

    async def foreground(self) -> None:
        self._last_foreground = self._clock()
        if self._work is not None:
            self._work.cancel()
            await asyncio.gather(self._work, return_exceptions=True)
            self._work = None
        if self.enabled:
            self.state = "foreground"

    async def _due(self) -> list[UserTextEvent]:
        now = self._clock()
        if now < self._next_attempt:
            return []
        unseen = await self._source.unseen_user_events()
        pending = [e for e in unseen if e.event_id not in self._seen]
        stale = now - self._last_run_clock >= self._max_age
        if len(pending) >= self._min_unseen or (pending and stale):
            return pending
        return []

    async def _run(self, events: list[UserTextEvent]) -> None:
        self.state = "running"
        try:
            await self._service.build(events)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._failures += 1
            delay = min(self._cooldown * 2**self._failures, MAX_BACKOFF_SECONDS)
            self._next_attempt = self._clock() + delay
            self.state = "backoff"
            LOGGER.warning("profile auto-update failed; retry in %.0fs", delay, exc_info=True)
            return
        self._failures = 0
        self._seen.update(e.event_id for e in events)
        if len(self._seen) > MAX_SEEN:
            self._seen = {e.event_id for e in events}
        self._last_run_clock = self._clock()
        self._next_attempt = self._last_run_clock + self._cooldown
        self.last_run = datetime.now(UTC).isoformat()
        self.state = "waiting"

    async def tick(self) -> None:
        """One scheduling decision; the loop calls this every poll."""
        if not self.enabled:
            return
        if self._busy():
            self._last_foreground = self._clock()
            self.state = "foreground"
            return
        if self._clock() - self._last_foreground < self._idle:
            return
        try:
            events = await self._due()
        except Exception:
            LOGGER.warning("profile auto-update could not read messages", exc_info=True)
            return
        if not events:
            if self.state == "foreground":
                self.state = "waiting"
            return
        self._work = asyncio.create_task(self._run(events), name="siro-profile-build")
        await asyncio.gather(self._work, return_exceptions=True)
        self._work = None

    async def _loop(self) -> None:
        while True:
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), self._poll)
            self._wake.clear()
            try:
                await self.tick()
            except Exception:
                LOGGER.warning("profile auto-update loop error", exc_info=True)

    async def close(self) -> None:
        await self.foreground()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        self.state = "stopped"
