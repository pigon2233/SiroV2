"""Source-backed episodic memory and identity prompt assembly."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from siro.contracts.events import Event
from siro.core.identity import IdentityState


class MemoryKind(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    SELF = "self"


class MemoryStatus(StrEnum):
    CANDIDATE = "candidate"
    COMMITTED = "committed"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class Memory:
    memory_id: UUID
    identity_id: str
    text: str
    source_event_ids: tuple[UUID, ...]
    created_at: datetime
    kind: MemoryKind = MemoryKind.EPISODIC
    person_id: str = "owner"
    confidence: float = 1.0
    valid_to: datetime | None = None
    status: MemoryStatus = MemoryStatus.COMMITTED
    revision: int = 1

    def __post_init__(self) -> None:
        if not self.identity_id or not self.person_id or not self.text:
            raise ValueError("memory identity, person scope, and text cannot be empty")
        if not self.source_event_ids:
            raise ValueError("memory requires at least one source event")
        if not 0 <= self.confidence <= 1:
            raise ValueError("memory confidence must be between 0 and 1")
        if self.revision < 1:
            raise ValueError("memory revision must be positive")


@dataclass(frozen=True, slots=True)
class MemoryRevision:
    memory_id: UUID
    revision: int
    text: str
    status: MemoryStatus
    reason: str
    changed_at: datetime
    source_event_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class SemanticFact:
    memory_id: UUID
    subject: str
    predicate: str
    value: object
    verification: str

    def __post_init__(self) -> None:
        if not self.subject or not self.predicate or not self.verification:
            raise ValueError("semantic fact fields cannot be empty")


class MemoryRepository(Protocol):
    async def add(self, memory: Memory, source_event: Event) -> None: ...

    async def search(
        self,
        identity_id: str,
        query: str,
        *,
        person_id: str = "owner",
        kinds: tuple[MemoryKind, ...] = (),
        as_of: datetime | None = None,
        source_event_id: UUID | None = None,
        limit: int = 5,
    ) -> list[Memory]: ...

    async def correct(
        self, memory_id: UUID, text: str, source_event: Event, *, reason: str
    ) -> Memory: ...

    async def delete(self, memory_id: UUID, *, reason: str, deleted_at: datetime) -> bool: ...

    async def revisions(self, memory_id: UUID) -> list[MemoryRevision]: ...

    async def list_active(
        self, identity_id: str, *, person_id: str = "owner", limit: int = 100
    ) -> list[Memory]: ...

    async def add_fact(self, memory: Memory, source_event: Event, fact: SemanticFact) -> None: ...

    async def facts(
        self, identity_id: str, subject: str, predicate: str, *, person_id: str = "owner"
    ) -> list[SemanticFact]: ...


class MemoryService:
    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def remember(self, memory: Memory, source_event: Event) -> None:
        if source_event.event_id not in memory.source_event_ids:
            raise ValueError("memory must cite the supplied source event")
        await self._repository.add(memory, source_event)

    async def remember_fact(self, memory: Memory, source_event: Event, fact: SemanticFact) -> None:
        if memory.kind is not MemoryKind.SEMANTIC:
            raise ValueError("semantic facts require semantic memory")
        if fact.memory_id != memory.memory_id:
            raise ValueError("fact must reference its memory")
        if source_event.event_id not in memory.source_event_ids:
            raise ValueError("memory must cite the supplied source event")
        await self._repository.add_fact(memory, source_event, fact)

    async def recall(
        self,
        identity_id: str,
        query: str,
        *,
        person_id: str = "owner",
        kinds: tuple[MemoryKind, ...] = (),
        as_of: datetime | None = None,
        source_event_id: UUID | None = None,
        limit: int = 5,
    ) -> list[Memory]:
        return await self._repository.search(
            identity_id,
            query,
            person_id=person_id,
            kinds=kinds,
            as_of=as_of,
            source_event_id=source_event_id,
            limit=limit,
        )

    async def correct(
        self, memory_id: UUID, text: str, source_event: Event, *, reason: str = "owner correction"
    ) -> Memory:
        if not text.strip():
            raise ValueError("corrected memory text cannot be empty")
        return await self._repository.correct(memory_id, text, source_event, reason=reason)

    async def delete(self, memory_id: UUID, *, reason: str = "owner deletion") -> bool:
        return await self._repository.delete(memory_id, reason=reason, deleted_at=datetime.now(UTC))

    async def revisions(self, memory_id: UUID) -> list[MemoryRevision]:
        return await self._repository.revisions(memory_id)

    async def browse(
        self, identity_id: str, *, person_id: str = "owner", limit: int = 100
    ) -> list[Memory]:
        return await self._repository.list_active(identity_id, person_id=person_id, limit=limit)

    async def conflicting_facts(
        self,
        identity_id: str,
        subject: str,
        predicate: str,
        *,
        person_id: str = "owner",
    ) -> list[SemanticFact]:
        return await self._repository.facts(identity_id, subject, predicate, person_id=person_id)


@dataclass(frozen=True, slots=True)
class WorkingMessage:
    role: str
    text: str


class WorkingMemory:
    """Bounded per-session recent context; durable messages remain in SQLite."""

    def __init__(self, *, max_messages: int = 12) -> None:
        if max_messages < 1:
            raise ValueError("max_messages must be positive")
        self._max_messages = max_messages
        self._sessions: defaultdict[str, deque[WorkingMessage]] = defaultdict(
            lambda: deque(maxlen=self._max_messages)
        )

    def append(self, session_id: str, role: str, text: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("working-memory role must be user or assistant")
        if text:
            self._sessions[session_id].append(WorkingMessage(role, text))

    def recent(self, session_id: str) -> tuple[WorkingMessage, ...]:
        return tuple(self._sessions[session_id])

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


def assemble_prompt(
    identity: IdentityState,
    user_text: str,
    memories: Sequence[Memory],
    working: Sequence[WorkingMessage] = (),
) -> str:
    values = ", ".join(identity.core.core_values)
    evidence = "\n".join(
        f"- {memory.text} [source:{memory.source_event_ids[0]}]" for memory in memories
    )
    if not evidence:
        evidence = "- NO_SOURCE: If the answer needs memory, say you do not know."
    recent = "\n".join(f"{message.role}: {message.text}" for message in working)
    if not recent:
        recent = "(none)"
    return (
        f"Identity: {identity.core.name} ({identity.identity_id})\n"
        f"Baseline: {identity.core.baseline_identity}\nValues: {values}\n"
        f"Verified memories:\n{evidence}\nRecent conversation:\n{recent}\nUser: {user_text}"
    )
