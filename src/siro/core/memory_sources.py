"""Read-only preparation of persisted owner sources; never a write or disclosure grant."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

from siro.contracts.events import Privacy, UserTextEvent
from siro.core.authorization import PermissionDecision


@dataclass(frozen=True, slots=True)
class SourceScope:
    identity_id: str
    person_id: str
    session_id: str

    def __post_init__(self) -> None:
        for value in (self.identity_id, self.person_id, self.session_id):
            if not isinstance(value, str) or not value.strip() or len(value) > 128 or "\0" in value:
                raise ValueError("source scope requires bounded nonempty identifiers")


@dataclass(frozen=True, slots=True)
class SourcePermission:
    """View supplied by the trusted Policy owner, not flags parsed from source text."""

    scope: SourceScope
    revision: int
    decision: PermissionDecision = PermissionDecision.DENY
    actor: str = ""
    owner_authenticated: bool = False
    allow_preparation: bool = False
    allowed_routes: frozenset[Privacy] = frozenset({Privacy.LOCAL_ONLY})

    def __post_init__(self) -> None:
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 1
        ):
            raise ValueError("source permission requires a positive revision")
        if not isinstance(self.scope, SourceScope) or not isinstance(self.actor, str):
            raise ValueError("source permission requires typed scope and actor")
        if not isinstance(self.allowed_routes, frozenset):
            raise ValueError("source permission routes must be immutable")
        if not isinstance(self.decision, PermissionDecision) or not all(
            isinstance(route, Privacy) for route in self.allowed_routes
        ):
            raise ValueError("source permission requires typed decisions and routes")

    def fingerprint(self) -> str:
        data = {**asdict(self), "allowed_routes": sorted(self.allowed_routes)}
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class SourceReason(StrEnum):
    PREPARED = "prepared"
    POLICY_DENIED = "policy_denied"
    POLICY_UNAVAILABLE = "policy_unavailable"
    POLICY_CHANGED = "policy_changed"
    MISSING_EVENT = "missing_event"
    INVALID_EVENT = "invalid_event"
    UNTRUSTED_SOURCE = "untrusted_source"
    UNBOUND_PERSON = "unbound_person"
    UNBOUND_SESSION = "unbound_session"
    SCOPE_MISMATCH = "scope_mismatch"
    PRIVACY_WITHHELD = "privacy_withheld"
    EXPIRED = "expired"
    NOT_YET_VALID = "not_yet_valid"
    SOURCE_REVOKED = "source_revoked"
    SOURCE_INVALIDATED = "source_invalidated"
    SOURCE_CHANGED = "source_changed"
    STORE_UNAVAILABLE = "store_unavailable"
    CLOCK_UNAVAILABLE = "clock_unavailable"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class PreparedSource:
    scope: SourceScope
    source_hash: str
    policy_revision: int
    policy_hash: str
    route_privacy: Privacy
    captured_at: datetime
    valid_until: datetime | None
    source: UserTextEvent = field(repr=False)
    content_review_required: Literal[True] = field(default=True, init=False)
    authorizes_memory_write: Literal[False] = field(default=False, init=False)
    authorizes_external_disclosure: Literal[False] = field(default=False, init=False)
    is_owner_fact: Literal[False] = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.scope, SourceScope) or not all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in (self.source_hash, self.policy_hash)
        ):
            raise ValueError("prepared source requires scope and opaque source/policy hashes")
        if (
            not isinstance(self.captured_at, datetime)
            or self.captured_at.utcoffset() is None
            or isinstance(self.policy_revision, bool)
            or not isinstance(self.policy_revision, int)
            or self.policy_revision < 1
        ):
            raise ValueError("prepared source requires aware time and policy revision")
        if self.valid_until is not None and (
            not isinstance(self.valid_until, datetime) or self.valid_until.utcoffset() is None
        ):
            raise ValueError("source expiry must include a timezone")
        if not isinstance(self.source, UserTextEvent) or not isinstance(
            self.route_privacy, Privacy
        ):
            raise ValueError("prepared source requires typed source and route")

    def metadata(self) -> dict[str, object]:
        return {
            "event_id": str(self.source.event_id),
            "source_hash": self.source_hash,
            "policy_revision": self.policy_revision,
            "policy_hash": self.policy_hash,
            "route_privacy": self.route_privacy,
            "captured_at": self.captured_at.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "content_review_required": True,
            "authorizes_memory_write": False,
            "authorizes_external_disclosure": False,
            "is_owner_fact": False,
        }


@dataclass(frozen=True, slots=True)
class SourceDecision:
    reason: SourceReason
    snapshot: PreparedSource | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (self.reason is SourceReason.PREPARED) != (self.snapshot is not None):
            raise ValueError("only prepared decisions may carry a private source")


class SourcePolicy(Protocol):
    async def current(self, scope: SourceScope) -> SourcePermission | None: ...


class SourceRepository(Protocol):
    async def prepare(
        self,
        event_id: UUID,
        scope: SourceScope,
        *,
        route_privacy: Privacy,
        policy_revision: int,
        policy_hash: str,
        now: datetime,
    ) -> SourceDecision: ...


class MemorySourceGate:
    def __init__(
        self,
        repository: SourceRepository,
        policy: SourcePolicy,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        timeout_seconds: float = 5,
    ) -> None:
        if not 0 < timeout_seconds <= 60:
            raise ValueError("source preparation timeout must be within 60 seconds")
        self._repository, self._policy, self._clock = repository, policy, clock
        self._timeout = timeout_seconds

    async def prepare(
        self,
        event_id: UUID,
        scope: SourceScope,
        *,
        route_privacy: Privacy = Privacy.LOCAL_ONLY,
    ) -> SourceDecision:
        if not isinstance(event_id, UUID) or not isinstance(scope, SourceScope):
            raise TypeError("source preparation requires UUID and typed scope")
        if not isinstance(route_privacy, Privacy):
            raise TypeError("source preparation requires a typed route")
        try:
            async with asyncio.timeout(self._timeout):
                try:
                    permission = await self._policy.current(scope)
                except Exception:
                    return SourceDecision(SourceReason.POLICY_UNAVAILABLE)
                if permission is None or not isinstance(permission, SourcePermission):
                    return SourceDecision(SourceReason.POLICY_UNAVAILABLE)
                if not (
                    permission.scope == scope
                    and scope.person_id == "owner"
                    and permission.actor == "owner"
                    and permission.owner_authenticated is True
                    and permission.allow_preparation is True
                    and permission.decision is PermissionDecision.ALLOW
                    and route_privacy in permission.allowed_routes
                ):
                    return SourceDecision(SourceReason.POLICY_DENIED)
                try:
                    now = self._clock()
                    if now.utcoffset() is None:
                        return SourceDecision(SourceReason.CLOCK_UNAVAILABLE)
                except Exception:
                    return SourceDecision(SourceReason.CLOCK_UNAVAILABLE)
                try:
                    policy_hash = permission.fingerprint()
                    result = await self._repository.prepare(
                        event_id,
                        scope,
                        route_privacy=route_privacy,
                        policy_revision=permission.revision,
                        policy_hash=policy_hash,
                        now=now,
                    )
                except Exception:
                    return SourceDecision(SourceReason.STORE_UNAVAILABLE)
                try:
                    current = await self._policy.current(scope)
                except Exception:
                    return SourceDecision(SourceReason.POLICY_UNAVAILABLE)
                if current != permission or current.fingerprint() != policy_hash:
                    return SourceDecision(SourceReason.POLICY_CHANGED)
                return result
        except TimeoutError:
            return SourceDecision(SourceReason.TIMEOUT)

    async def revalidate(
        self, snapshot: PreparedSource, *, route_privacy: Privacy
    ) -> SourceDecision:
        if not isinstance(snapshot, PreparedSource):
            raise TypeError("source revalidation requires a prepared source")
        if route_privacy is not snapshot.route_privacy:
            return SourceDecision(SourceReason.PRIVACY_WITHHELD)
        result = await self.prepare(
            snapshot.source.event_id, snapshot.scope, route_privacy=route_privacy
        )
        fresh = result.snapshot
        if fresh is None:
            return result
        if (fresh.policy_revision, fresh.policy_hash) != (
            snapshot.policy_revision,
            snapshot.policy_hash,
        ):
            return SourceDecision(SourceReason.POLICY_CHANGED)
        if (
            fresh.source_hash != snapshot.source_hash
            or fresh.source != snapshot.source
            or fresh.valid_until != snapshot.valid_until
            or fresh.captured_at < snapshot.captured_at
        ):
            return SourceDecision(SourceReason.SOURCE_CHANGED)
        return result
