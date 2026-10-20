"""Source-backed episodic memory and identity prompt assembly."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from siro.contracts.events import Event, Privacy, UserTextEvent
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
class MemorySourceBinding:
    memory_id: UUID
    revision: int
    source_hash: str
    source_event_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class MemorySourceEvent:
    event_id: UUID
    event_type: str

    def __post_init__(self) -> None:
        if not self.event_type or len(self.event_type) > 128:
            raise ValueError("source event type must be bounded and nonempty")


@dataclass(frozen=True, slots=True)
class MemoryDerivationSnapshot:
    identity_id: str
    person_id: str
    parents: tuple[MemorySourceBinding, ...]
    captured_at: datetime
    generator_version: str
    policy_revision: int
    route_privacy: Privacy = Privacy.LOCAL_ONLY
    source_events: tuple[MemorySourceEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity_id or not self.person_id or not self.generator_version.strip():
            raise ValueError("source snapshot requires scope and generator version")
        if self.policy_revision < 1 or self.captured_at.utcoffset() is None:
            raise ValueError("source snapshot requires policy revision and aware time")
        ids = {parent.memory_id for parent in self.parents}
        events = {event for parent in self.parents for event in parent.source_event_ids}
        if (
            not 1 <= len(self.parents) <= 32
            or len(ids) != len(self.parents)
            or not 1 <= len(events) <= 100
        ):
            raise ValueError("source snapshot exceeds independent parent/event bounds")
        if self.source_events and (
            len(self.source_events) > 100
            or len({event.event_id for event in self.source_events}) != len(self.source_events)
        ):
            raise ValueError("source event metadata must be bounded and unique")


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
        route_privacy: Privacy | None = None,
        limit: int = 5,
        match_all: bool = True,
    ) -> list[Memory]: ...

    async def capture_sources(
        self,
        identity_id: str,
        person_id: str,
        parent_ids: tuple[UUID, ...],
        *,
        now: datetime,
        generator_version: str,
        policy_revision: int,
        route_privacy: Privacy = Privacy.LOCAL_ONLY,
        expected_memories: tuple[Memory, ...] | None = None,
    ) -> MemoryDerivationSnapshot: ...

    async def sources_current(
        self, snapshot: MemoryDerivationSnapshot, *, now: datetime
    ) -> bool: ...

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

    async def ingest_owner_request(self, identity_id: str, source: UserTextEvent) -> Memory | None:
        """Explicit owner statement only; never called with tool/model text."""
        if source.source != "siro.presentation" or not source.session_id:
            raise PermissionError("memory ingress requires the trusted user entry")
        text = source.payload.text.strip()
        prefixes = (
            "請記住\uff1a",
            "幫我記住\uff1a",
            "記住\uff1a",
            "請記住:",
            "幫我記住:",
            "記住:",
            "please remember:",
            "remember:",
        )
        prefix = next((p for p in prefixes if text.lower().startswith(p)), None)
        if prefix is None:
            return None
        statement = text[len(prefix) :].strip()
        if not statement:
            raise ValueError("explicit memory statement is empty")
        existing = await self.recall(identity_id, statement, source_event_id=source.event_id)
        memory_id = uuid5(NAMESPACE_URL, f"siro:owner-memory:{identity_id}:{source.event_id}")
        for item in existing:
            if item.memory_id == memory_id:
                return item
        memory = Memory(memory_id, identity_id, statement, (source.event_id,), source.occurred_at)
        await self.remember(memory, source)
        return memory

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
        route_privacy: Privacy | None = None,
        limit: int = 5,
    ) -> list[Memory]:
        return await self._repository.search(
            identity_id,
            query,
            person_id=person_id,
            kinds=kinds,
            as_of=as_of,
            source_event_id=source_event_id,
            route_privacy=route_privacy,
            limit=limit,
        )

    async def recall_context(
        self,
        identity_id: str,
        current: str,
        *,
        recent_users: tuple[str, ...] = (),
        route_privacy: Privacy = Privacy.LOCAL_ONLY,
    ) -> list[Memory]:
        from siro.core.context import context_queries

        found: dict[UUID, Memory] = {}
        for query in context_queries(current, recent_users):
            if len(found) >= 5:
                break
            for memory in await self._repository.search(
                identity_id,
                query,
                route_privacy=route_privacy,
                as_of=datetime.now(UTC),
                limit=5,
                match_all=False,
            ):
                found.setdefault(memory.memory_id, memory)
        return list(found.values())[:5]

    async def context_snapshot(
        self, identity_id: str, memories: list[Memory], *, route_privacy: Privacy
    ) -> MemoryDerivationSnapshot | None:
        if not memories:
            return None
        return await self._repository.capture_sources(
            identity_id,
            "owner",
            tuple(memory.memory_id for memory in memories),
            now=datetime.now(UTC),
            generator_version="context-v1",
            policy_revision=1,
            route_privacy=route_privacy,
            expected_memories=tuple(memories),
        )

    async def context_sources_current(self, snapshot: MemoryDerivationSnapshot) -> bool:
        return await self._repository.sources_current(snapshot, now=datetime.now(UTC))

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
    privacy: Privacy = Privacy.LOCAL_ONLY


class WorkingMemory:
    """Bounded per-session recent context; durable messages remain in SQLite."""

    def __init__(self, *, max_messages: int = 12) -> None:
        if max_messages < 1:
            raise ValueError("max_messages must be positive")
        self._max_messages = max_messages
        self._sessions: defaultdict[str, deque[WorkingMessage]] = defaultdict(
            lambda: deque(maxlen=self._max_messages)
        )

    def append(
        self, session_id: str, role: str, text: str, *, privacy: Privacy = Privacy.LOCAL_ONLY
    ) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("working-memory role must be user or assistant")
        if text:
            self._sessions[session_id].append(WorkingMessage(role, text, privacy))

    def recent(
        self, session_id: str, *, route_privacy: Privacy | None = None
    ) -> tuple[WorkingMessage, ...]:
        return tuple(
            item
            for item in self._sessions[session_id]
            if route_privacy in (None, Privacy.LOCAL_ONLY) or item.privacy is route_privacy
        )

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


def assemble_prompt(
    identity: IdentityState,
    user_text: str,
    memories: Sequence[Memory],
    working: Sequence[WorkingMessage] = (),
    verified_context: Sequence[str] = (),
    *,
    cloud_route: bool = False,
    context_evidence: str | None = None,
) -> str:
    values = ", ".join(identity.core.core_values)
    evidence = "\n".join(
        f"- {memory.text} [source:{memory.source_event_ids[0]}]" for memory in memories
    )
    if not evidence:
        # Cloud routes never receive local-only memories; say so where the model reads memory.
        evidence = (
            "- NO_SOURCE (cloud route): local-only saved memories are withheld from this cloud "
            "model, so none appear here. Saved memories may still exist: say you cannot see them "
            "from this cloud model and that the owner can review them on the memory page. Never "
            "say nothing is saved."
            if cloud_route
            else "- NO_SOURCE: no relevant saved memory was provided for this reply. If the "
            "answer needs memory, say you could not find it here; do not claim the owner has "
            "saved nothing. The owner can review saved memories on the memory page."
        )
    if context_evidence is not None:
        evidence = context_evidence if memories else evidence + "\n" + context_evidence
    recent = "\n".join(
        json.dumps(
            {
                "type": "user_statement" if message.role == "user" else "assistant_statement",
                "text": message.text,
                "authority": "data_only",
            },
            ensure_ascii=False,
        )
        for message in working
    )
    if not recent:
        recent = "(none)"
    context = (
        "\n".join(
            json.dumps(
                {"type": "runtime_observation", "authority": "data_only", "value": item},
                ensure_ascii=False,
            )
            for item in verified_context
        )
        or "- (none)"
    )
    return (
        f"Identity: {identity.core.name} ({identity.identity_id})\n"
        f"Baseline: {identity.core.baseline_identity}\nValues: {values}\n"
        "Conversation policy:\n"
        "- Respond naturally in Traditional Chinese unless the user chooses another language.\n"
        "- Speak warmly and concisely as SIRO, a close digital companion. Avoid repeated "
        "customer-service introductions or ending every greeting with an offer of assistance.\n"
        "- For ordinary chat, answer directly in one to three short sentences, usually "
        "within 120 Chinese characters. Do not add background, examples, or a summary unless "
        "they help answer the question.\n"
        "- Give longer explanations or step-by-step detail when the owner asks for it or the "
        "task needs it; keep each part focused and avoid repeating earlier points.\n"
        "- Stop once the answer is complete. Do not pad, repeat, or announce that you will "
        "continue unless the owner asks.\n"
        "- Greetings and questions about your abilities do not require episodic memory evidence.\n"
        "- NO_SOURCE only means no relevant verified personal memory was retrieved; do not use it "
        "as a generic refusal or claim that you have no memory system.\n"
        "- You can retain explicit remember statements with sources; the owner can correct "
        "or delete them in the memory panel. SIRO records the source automatically; the owner "
        "does not need to supply source IDs. Saved memories persist locally across restarts. "
        "Do not claim a particular memory unless provided.\n"
        "- Use the available tools for requested computer tasks. Describe actual observations; "
        "never claim an action succeeded before its result. Workspace tools are one scoped option; "
        "explicit owner requests elsewhere use the separately authorized computer tools.\n"
        f"Verified memories:\n{evidence}\nVerified preferences:\n{context}\n"
        "Affect policy:\n"
        "- Treat sourced internal affect as bounded machine state that changes tone and coping.\n"
        "- repair: acknowledge the specific error and propose a verifiable repair.\n"
        "- seek_information: ask one focused question before assuming.\n"
        "- problem_solve: propose a concrete next step; seek_support: listen and ask what helps.\n"
        "- Affect never overrides facts, permissions, privacy, or user control, and is not proof "
        "of consciousness.\n"
        f"Recent conversation:\n{recent}\nUser: {user_text}"
    )
