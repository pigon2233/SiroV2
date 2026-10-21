"""Bounded, resumable memory consolidation and relationship evolution."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from siro.core.memory import MemoryKind
from siro.ports.models import CancellationToken


@dataclass(frozen=True, slots=True)
class ConsolidationCandidate:
    text: str
    kind: MemoryKind
    source_event_ids: tuple[UUID, ...]
    confidence: float
    inferred: bool = False

    def __post_init__(self) -> None:
        if not self.text or self.kind is MemoryKind.WORKING:
            raise ValueError("candidate must be durable and non-empty")
        if not self.source_event_ids or len(set(self.source_event_ids)) != len(
            self.source_event_ids
        ):
            raise ValueError("candidate requires independent source events")
        if not 0 <= self.confidence <= 1:
            raise ValueError("candidate confidence must be between 0 and 1")

    @property
    def key(self) -> str:
        payload = "\0".join(
            (self.kind, self.text, *(str(value) for value in sorted(self.source_event_ids)))
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ConsolidationResult:
    run_id: str
    state: str
    checkpoint: int
    created: int
    duplicates: int


class ConsolidationRepository(Protocol):
    async def start_or_resume(
        self, run_key: str, identity_id: str, now: datetime
    ) -> tuple[str, int]: ...

    async def commit_candidate(
        self,
        run_id: str,
        identity_id: str,
        candidate: ConsolidationCandidate,
        checkpoint: int,
        now: datetime,
    ) -> bool: ...

    async def finish_run(self, run_id: str, state: str, checkpoint: int, now: datetime) -> None: ...


class Consolidator:
    def __init__(
        self,
        repository: ConsolidationRepository,
        *,
        max_sources: int = 100,
        timeout_seconds: float = 60,
    ) -> None:
        self._repository = repository
        self._max_sources = max_sources
        self._timeout = timeout_seconds

    async def run(
        self,
        run_key: str,
        identity_id: str,
        candidates: tuple[ConsolidationCandidate, ...],
        cancellation: CancellationToken,
        *,
        now: datetime,
    ) -> ConsolidationResult:
        sources = {source for candidate in candidates for source in candidate.source_event_ids}
        if len(sources) > self._max_sources:
            raise ValueError("consolidation source budget exceeded")
        run_id, checkpoint = await self._repository.start_or_resume(run_key, identity_id, now)
        created = duplicates = 0
        state = "completed"
        try:
            async with asyncio.timeout(self._timeout):
                for index, candidate in enumerate(candidates[checkpoint:], start=checkpoint):
                    if cancellation.cancelled:
                        state = "cancelled"
                        break
                    if await self._repository.commit_candidate(
                        run_id, identity_id, candidate, index + 1, now
                    ):
                        created += 1
                    else:
                        duplicates += 1
                    checkpoint = index + 1
        except TimeoutError:
            state = "cancelled"
        await self._repository.finish_run(run_id, state, checkpoint, now)
        return ConsolidationResult(run_id, state, checkpoint, created, duplicates)


@dataclass(slots=True)
class _ScheduledRun:
    token: CancellationToken
    task: asyncio.Task[ConsolidationResult]


class ConsolidationScheduler:
    """Owns bounded background runs without granting them foreground priority."""

    def __init__(self, consolidator: Consolidator) -> None:
        self._consolidator = consolidator
        self._runs: dict[str, _ScheduledRun] = {}

    def active(self, run_key: str) -> bool:
        scheduled = self._runs.get(run_key)
        return scheduled is not None and not scheduled.task.done()

    async def schedule(
        self,
        run_key: str,
        identity_id: str,
        candidates: tuple[ConsolidationCandidate, ...],
        *,
        now: datetime,
        idle: bool,
        resources_available: bool,
    ) -> bool:
        if not idle or not resources_available or run_key in self._runs:
            return False
        token = CancellationToken()
        task = asyncio.create_task(
            self._consolidator.run(run_key, identity_id, candidates, token, now=now),
            name=f"consolidation-{run_key}",
        )
        self._runs[run_key] = _ScheduledRun(token, task)
        return True

    async def cancel(self, run_key: str) -> bool:
        scheduled = self._runs.get(run_key)
        if scheduled is None or scheduled.task.done():
            return False
        scheduled.token.cancel()
        await asyncio.gather(scheduled.task, return_exceptions=True)
        return True

    async def wait(self, run_key: str) -> ConsolidationResult | None:
        scheduled = self._runs.get(run_key)
        if scheduled is None:
            return None
        try:
            return await scheduled.task
        finally:
            self._runs.pop(run_key, None)

    async def close(self) -> None:
        active = tuple(self._runs.values())
        for scheduled in active:
            scheduled.token.cancel()
        if active:
            await asyncio.gather(*(scheduled.task for scheduled in active), return_exceptions=True)
        self._runs.clear()
