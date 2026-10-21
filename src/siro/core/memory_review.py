"""Explicit, policy-leased review of memory candidates; no production policy adapter."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from siro.core.authorization import PermissionDecision
from siro.core.memory_candidates import CandidateDraft, CandidateKind, MemoryCandidateGenerator
from siro.core.memory_sources import SourceScope


class ReviewOperation(StrEnum):
    READ = "read"
    STAGE = "stage"
    APPROVE = "approve"
    REJECT = "reject"
    WITHDRAW = "withdraw"
    REPLACE = "replace"


@dataclass(frozen=True, slots=True)
class ReviewPermit:
    scope: SourceScope
    revision: int
    expires_at: datetime
    decision: PermissionDecision = PermissionDecision.DENY
    actor: str = ""
    owner_authenticated: bool = False
    operations: frozenset[ReviewOperation] = frozenset()
    kinds: frozenset[CandidateKind] = frozenset()
    memory_retention_seconds: int | None = None
    pending_limit: int = 100

    def __post_init__(self) -> None:
        if (
            not isinstance(self.scope, SourceScope)
            or type(self.revision) is not int
            or self.revision < 1
            or not isinstance(self.expires_at, datetime)
            or self.expires_at.utcoffset() is None
            or not isinstance(self.decision, PermissionDecision)
            or not isinstance(self.operations, frozenset)
            or not all(isinstance(op, ReviewOperation) for op in self.operations)
            or not isinstance(self.kinds, frozenset)
            or not all(isinstance(kind, CandidateKind) for kind in self.kinds)
            or type(self.pending_limit) is not int
            or not 1 <= self.pending_limit <= 100
            or (
                self.memory_retention_seconds is not None
                and (
                    type(self.memory_retention_seconds) is not int
                    or not 1 <= self.memory_retention_seconds <= 31_536_000
                )
            )
        ):
            raise ValueError("review permit requires bounded typed policy metadata")

    def allows(self, scope: SourceScope, operation: ReviewOperation, now: datetime) -> bool:
        return (
            self.scope == scope
            and scope.person_id == "owner"
            and self.actor == "owner"
            and self.owner_authenticated is True
            and self.decision is PermissionDecision.ALLOW
            and operation in self.operations
            and now < self.expires_at
        )

    def fingerprint(self) -> str:
        data = {
            "scope": [self.scope.identity_id, self.scope.person_id, self.scope.session_id],
            "revision": self.revision,
            "expires_at": self.expires_at.isoformat(),
            "decision": self.decision,
            "actor": self.actor,
            "owner_authenticated": self.owner_authenticated,
            "operations": sorted(self.operations),
            "kinds": sorted(self.kinds),
            "retention": self.memory_retention_seconds,
            "pending_limit": self.pending_limit,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class MemoryReviewPolicy(Protocol):
    def lease(
        self,
        scope: SourceScope,
        operation: ReviewOperation,
    ) -> AbstractAsyncContextManager[ReviewPermit | None]: ...


class ReviewOutcome(StrEnum):
    APPLIED = "applied"
    ALREADY_APPLIED = "already_applied"
    ALREADY_PRESENT = "already_present"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    SOURCE_INVALID = "source_invalid"
    EXPIRED = "expired"
    LIMIT_REACHED = "limit_reached"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ReviewCommand:
    action_id: UUID
    scope: SourceScope
    operation: ReviewOperation
    candidate_id: UUID | None = None
    expected_revision: int | None = None
    source_event_id: UUID | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.action_id, UUID)
            or not isinstance(self.scope, SourceScope)
            or not isinstance(self.operation, ReviewOperation)
            or self.operation is ReviewOperation.READ
            or (self.candidate_id is not None and not isinstance(self.candidate_id, UUID))
            or (self.source_event_id is not None and not isinstance(self.source_event_id, UUID))
            or (
                self.expected_revision is not None
                and (type(self.expected_revision) is not int or self.expected_revision < 1)
            )
        ):
            raise ValueError("review command requires typed scope, identifiers and revision")
        stage = self.operation is ReviewOperation.STAGE
        new_source = self.operation in {ReviewOperation.STAGE, ReviewOperation.REPLACE}
        if (
            (self.candidate_id is None) != stage
            or (self.expected_revision is None) != stage
            or (self.source_event_id is not None) != new_source
        ):
            raise ValueError("review operation arguments do not match its contract")

    def fingerprint(self) -> str:
        data = [
            str(self.action_id),
            self.scope.identity_id,
            self.scope.person_id,
            self.scope.session_id,
            self.operation,
            str(self.candidate_id),
            self.expected_revision,
            str(self.source_event_id),
        ]
        return hashlib.sha256(json.dumps(data).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ReviewResult:
    outcome: ReviewOutcome
    candidate_id: UUID | None = None
    revision: int | None = None
    state_at_commit: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewSummary:
    candidate_id: UUID
    kind: CandidateKind
    state: str
    revision: int
    expires_at: datetime
    source_event_id: UUID
    replaces_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ReviewPreview:
    summary: ReviewSummary
    draft: CandidateDraft = field(repr=False)


class MemoryReviewRepository(Protocol):
    async def lookup(
        self,
        action_id: UUID,
        scope: SourceScope,
        permit: ReviewPermit,
        *,
        command_hash: str | None = None,
    ) -> ReviewResult | None: ...
    async def pending(
        self,
        scope: SourceScope,
        permit: ReviewPermit,
    ) -> tuple[ReviewSummary, ...]: ...
    async def draft(
        self,
        candidate_id: UUID,
        scope: SourceScope,
        permit: ReviewPermit,
    ) -> ReviewPreview | None: ...
    async def apply(
        self,
        command: ReviewCommand,
        permit: ReviewPermit,
        draft: CandidateDraft | None,
    ) -> ReviewResult: ...


class ReviewReadUnavailable(RuntimeError):
    """Sanitized read failure, distinct from an empty or denied review view."""


class MemoryReviewService:
    def __init__(
        self,
        repository: MemoryReviewRepository,
        generator: MemoryCandidateGenerator,
        policy: MemoryReviewPolicy,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository, self._generator, self._policy = repository, generator, policy
        self._clock = clock

    def _allowed(
        self, permit: ReviewPermit | None, scope: SourceScope, op: ReviewOperation
    ) -> bool:
        now = self._clock()
        return (
            now.utcoffset() is not None
            and isinstance(permit, ReviewPermit)
            and permit.allows(scope, op, now)
        )

    async def execute(self, command: ReviewCommand) -> ReviewResult:
        dispatched = False
        try:
            async with self._policy.lease(command.scope, command.operation) as permit:
                if not self._allowed(permit, command.scope, command.operation) or permit is None:
                    return ReviewResult(ReviewOutcome.DENIED)
                recorded = await self._repository.lookup(
                    command.action_id, command.scope, permit, command_hash=command.fingerprint()
                )
                if recorded is not None:
                    return recorded
                draft = None
                if command.operation in {ReviewOperation.STAGE, ReviewOperation.REPLACE}:
                    assert command.source_event_id is not None
                    selected = await self._generator.prepare(command.source_event_id, command.scope)
                    draft = selected.draft
                    if draft is None:
                        return ReviewResult(ReviewOutcome.SOURCE_INVALID)
                elif command.operation is ReviewOperation.APPROVE:
                    assert command.candidate_id is not None
                    preview = await self._repository.draft(
                        command.candidate_id, command.scope, permit
                    )
                    if preview is None:
                        return ReviewResult(ReviewOutcome.NOT_FOUND)
                    checked = await self._generator.revalidate(preview.draft)
                    draft = checked.draft
                    if draft is None:
                        return ReviewResult(ReviewOutcome.SOURCE_INVALID)
                if draft is not None and draft.selection.kind not in permit.kinds:
                    return ReviewResult(ReviewOutcome.DENIED)
                dispatched = True
                # SQLiteStore uses to_thread: keep the policy lease until its task is terminal.
                task = asyncio.create_task(self._repository.apply(command, permit, draft))
                try:
                    return await asyncio.shield(task)
                except asyncio.CancelledError:
                    while not task.done():
                        try:
                            await asyncio.shield(task)
                        except asyncio.CancelledError:
                            continue
                        except Exception:
                            break
                    if not task.cancelled():
                        task.exception()  # Retrieve failures; caller must read back action_id.
                    raise
        except asyncio.CancelledError:
            raise
        except Exception:
            return ReviewResult(ReviewOutcome.UNKNOWN if dispatched else ReviewOutcome.UNAVAILABLE)

    @asynccontextmanager
    async def _read_lease(self, scope: SourceScope) -> AsyncIterator[ReviewPermit | None]:
        try:
            async with self._policy.lease(scope, ReviewOperation.READ) as permit:
                yield permit if self._allowed(permit, scope, ReviewOperation.READ) else None
        except Exception:
            raise ReviewReadUnavailable("memory review read unavailable") from None

    async def lookup(self, action_id: UUID, scope: SourceScope) -> ReviewResult | None:
        async with self._read_lease(scope) as permit:
            if permit is None or not self._allowed(permit, scope, ReviewOperation.READ):
                return None
            return await self._repository.lookup(action_id, scope, permit)

    async def pending(self, scope: SourceScope) -> tuple[ReviewSummary, ...]:
        async with self._read_lease(scope) as permit:
            if permit is None or not self._allowed(permit, scope, ReviewOperation.READ):
                return ()
            return await self._repository.pending(scope, permit)

    async def preview(self, candidate_id: UUID, scope: SourceScope) -> ReviewPreview | None:
        async with self._read_lease(scope) as permit:
            if permit is None or not self._allowed(permit, scope, ReviewOperation.READ):
                return None
            preview = await self._repository.draft(candidate_id, scope, permit)
            if preview is None or (await self._generator.revalidate(preview.draft)).draft is None:
                return None
            return preview
