"""One idle owner for a disposable, source-checked memory digest. Never writes facts."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime

from siro.core.memory import Memory, MemoryKind, MemoryService


def _version(items: list[Memory]) -> str:
    return hashlib.sha256(
        "\n".join(
            f"{m.memory_id}:{m.revision}:{m.text}:{m.source_event_ids}" for m in items
        ).encode()
    ).hexdigest()


class MemoryOrganizer:
    def __init__(
        self,
        memory: MemoryService,
        busy: Callable[[], bool],
        *,
        enabled: bool = True,
        idle_seconds: float = 15,
        poll_seconds: float = 5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._memory, self._busy = memory, busy
        self.enabled = enabled
        self._idle_seconds, self._poll_seconds = idle_seconds, poll_seconds
        self._clock = clock
        self._last_foreground = self._clock()
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._work: asyncio.Task[None] | None = None
        self._source_version = ""
        self._groups: list[dict[str, object]] = []
        self._requested = False
        self.state = "waiting" if enabled else "disabled"
        self.updated_at: str | None = None

    async def _sources(self) -> list[Memory]:
        return [
            m
            for m in await self._memory.browse("siro", person_id="owner", limit=100)
            if m.kind is MemoryKind.EPISODIC
        ]

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="siro-memory-organization")

    async def configure(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            await self.foreground()
            self._groups = []
            self._source_version = ""
            self.state = "disabled"
        self._wake.set()

    def request(self) -> None:
        self._requested = True  # Coalesce any number of triggers into one slot.
        self._wake.set()

    async def foreground(self) -> None:
        self._last_foreground = self._clock()
        self._requested = False
        if self._work is not None:
            self._work.cancel()
            await asyncio.gather(self._work, return_exceptions=True)
            self._work = None
        if self.enabled:
            self.state = "foreground"

    async def snapshot(self) -> dict[str, object]:
        sources = await self._sources()
        if _version(sources) != self._source_version:
            self._groups = []
            if self.enabled:
                self.state = "waiting"
        return {
            "enabled": self.enabled,
            "state": self.state,
            "updated_at": self.updated_at,
            "groups": list(self._groups),
            "source_limit": 100,
            "mode": "local_source_digest",
            "writes_facts": False,
        }

    async def _organize(self) -> None:
        async with asyncio.timeout(5):
            sources = await self._sources()
            version = _version(sources)
            grouped: dict[str, list[Memory]] = {}
            for memory in sources:
                # Exact normalized duplicate grouping; no inference or semantic merge.
                grouped.setdefault(" ".join(memory.text.split()), []).append(memory)
            groups: list[dict[str, object]] = []
            for memories in grouped.values():
                groups.append(
                    {
                        "text": memories[0].text[:512],
                        "truncated": len(memories[0].text) > 512,
                        "duplicates": len(memories) - 1,
                        "sources": [
                            {
                                "memory_id": str(m.memory_id),
                                "revision": m.revision,
                                "event_ids": [str(e) for e in m.source_event_ids],
                            }
                            for m in memories
                        ],
                    }
                )
                await asyncio.sleep(0)
            if not self.enabled or self._busy():
                return
            if version != _version(await self._sources()):
                self.state = "waiting"
                return
            self._groups, self._source_version = groups, version
            self.updated_at = datetime.now(UTC).isoformat()
            self.state = "ready"

    async def _loop(self) -> None:
        while True:
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), self._poll_seconds)
            self._wake.clear()
            if not self.enabled:
                continue
            if self._busy():
                self._last_foreground = self._clock()
                self.state = "foreground"
                continue
            if not self._requested and self._clock() - self._last_foreground < self._idle_seconds:
                continue
            self._requested = False
            self.state = "organizing"
            self._work = asyncio.create_task(self._organize(), name="siro-memory-digest")
            result = await asyncio.gather(self._work, return_exceptions=True)
            self._work = None
            if isinstance(result[0], Exception):
                self.state = "error"

    async def close(self) -> None:
        await self.foreground()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        self.state = "stopped"
