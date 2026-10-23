"""Atomic, read-only inspection of existing provenance rows for MEM-03-A."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from uuid import UUID

from siro.contracts.events import Privacy, UserTextEvent, validate_event_json
from siro.core.memory_sources import PreparedSource, SourceDecision, SourceReason, SourceScope
from siro.persistence.sqlite import SQLiteStore


class SQLiteMemorySourceRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def prepare(
        self,
        event_id: UUID,
        scope: SourceScope,
        *,
        route_privacy: Privacy,
        policy_revision: int,
        policy_hash: str,
        now: datetime,
    ) -> SourceDecision:
        def read(connection: sqlite3.Connection) -> SourceDecision:
            connection.execute("PRAGMA query_only=ON")
            return self.inspect(
                connection,
                event_id,
                scope,
                route_privacy=route_privacy,
                policy_revision=policy_revision,
                policy_hash=policy_hash,
                now=now,
            )

        return await self._store.run_transaction(read)

    @staticmethod
    def inspect(
        connection: sqlite3.Connection,
        event_id: UUID,
        scope: SourceScope,
        *,
        route_privacy: Privacy,
        policy_revision: int,
        policy_hash: str,
        now: datetime,
    ) -> SourceDecision:
        """Read within the caller's existing transaction; does not toggle its write mode."""
        row = connection.execute(
            "SELECT * FROM events WHERE event_id=?", (str(event_id),)
        ).fetchone()
        if row is None:
            return SourceDecision(SourceReason.MISSING_EVENT)
        try:
            event = validate_event_json(row["envelope_json"].encode())
            if (
                event.event_id != event_id
                or event.type != row["type"]
                or event.trace_id != row["trace_id"]
                or event.received_at != datetime.fromisoformat(row["received_at"])
            ):
                return SourceDecision(SourceReason.INVALID_EVENT)
        except (ValueError, TypeError, AttributeError):
            return SourceDecision(SourceReason.INVALID_EVENT)
        if not isinstance(event, UserTextEvent) or event.source != "siro.presentation":
            return SourceDecision(SourceReason.UNTRUSTED_SOURCE)
        if event.subject_id is None:
            return SourceDecision(SourceReason.UNBOUND_PERSON)
        if event.subject_id != scope.person_id or event.session_id != scope.session_id:
            return SourceDecision(SourceReason.SCOPE_MISMATCH)
        session = connection.execute(
            "SELECT c.identity_id FROM conversations c JOIN identities i "
            "ON i.identity_id=c.identity_id WHERE c.session_id=?",
            (scope.session_id,),
        ).fetchone()
        if session is None:
            return SourceDecision(SourceReason.UNBOUND_SESSION)
        if session["identity_id"] != scope.identity_id:
            return SourceDecision(SourceReason.SCOPE_MISMATCH)
        if event.occurred_at > now or event.received_at > now:
            return SourceDecision(SourceReason.NOT_YET_VALID)
        if event.occurred_at > event.received_at:
            return SourceDecision(SourceReason.INVALID_EVENT)
        expiry = event.occurred_at + timedelta(milliseconds=event.ttl_ms) if event.ttl_ms else None
        if expiry is not None and now >= expiry:
            return SourceDecision(SourceReason.EXPIRED)
        if (
            route_privacy is Privacy.CLOUD_ALLOWED and event.privacy is not Privacy.CLOUD_ALLOWED
        ) or (route_privacy is Privacy.TRUSTED_LAN and event.privacy is Privacy.LOCAL_ONLY):
            return SourceDecision(SourceReason.PRIVACY_WITHHELD)
        if connection.execute(
            "SELECT 1 FROM memory_source_revocations WHERE source_event_id=?", (str(event_id),)
        ).fetchone():
            return SourceDecision(SourceReason.SOURCE_REVOKED)
        if connection.execute(
            "SELECT 1 FROM memory_sources s JOIN memories m ON m.memory_id=s.memory_id "
            "WHERE s.source_event_id=? AND "
            "(m.deleted_at IS NOT NULL OR m.status IN ('deleted','superseded') "
            "OR m.revision>1)",
            (str(event_id),),
        ).fetchone():
            return SourceDecision(SourceReason.SOURCE_INVALIDATED)
        digest = hashlib.sha256(
            json.dumps(
                {"event": dict(row), "session_identity": session["identity_id"]},
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        return SourceDecision(
            SourceReason.PREPARED,
            PreparedSource(
                scope,
                digest,
                policy_revision,
                policy_hash,
                route_privacy,
                now,
                expiry,
                event,
            ),
        )
