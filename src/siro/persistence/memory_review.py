"""Candidate metadata and explicit transitions in the existing Memory transaction."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from siro.contracts.events import Privacy
from siro.core.memory import Memory, MemoryKind, MemoryStatus
from siro.core.memory_candidates import (
    CandidateDraft,
    CandidateKind,
    _draft,
    classify_source_text,
)
from siro.core.memory_review import (
    ReviewCommand,
    ReviewOperation,
    ReviewOutcome,
    ReviewPermit,
    ReviewPreview,
    ReviewResult,
    ReviewSummary,
)
from siro.core.memory_sources import SourceScope
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.memory_sources import SQLiteMemorySourceRepository
from siro.persistence.sqlite import SQLiteStore


class _Abort(Exception):
    def __init__(self, outcome: ReviewOutcome) -> None:
        self.outcome = outcome


class SQLiteMemoryReviewRepository:
    def __init__(
        self,
        store: SQLiteStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store, self._clock = store, clock
        self._memories = SQLiteMemoryRepository(store)

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("review transaction requires an aware clock")
        return now

    @staticmethod
    def _row(c: sqlite3.Connection, candidate_id: UUID, scope: SourceScope) -> sqlite3.Row | None:
        row: sqlite3.Row | None = c.execute(
            "SELECT r.*,m.text AS memory_text,m.status AS memory_status,m.deleted_at,"
            "m.revision AS actual_revision,m.valid_to AS memory_valid_to,m.kind AS memory_kind,"
            "m.identity_id AS actual_identity,m.person_id AS actual_person "
            "FROM memory_candidate_reviews r JOIN memories m ON m.memory_id=r.memory_id "
            "WHERE r.memory_id=? AND r.identity_id=? AND r.person_id=? AND r.session_id=?",
            (str(candidate_id), scope.identity_id, scope.person_id, scope.session_id),
        ).fetchone()
        return row

    @staticmethod
    def _consistent(row: sqlite3.Row) -> bool:
        expected = {
            "pending": "candidate",
            "approved": "committed",
            "rejected": "deleted",
            "withdrawn": "deleted",
        }
        return (
            row["memory_revision"] == row["actual_revision"]
            and row["actual_identity"] == row["identity_id"]
            and row["actual_person"] == row["person_id"]
            and row["memory_kind"] == "episodic"
            and row["memory_status"] == expected.get(row["state"])
            and (row["deleted_at"] is None) == (row["state"] in {"pending", "approved"})
        )

    @classmethod
    def _summary(cls, row: sqlite3.Row, now: datetime) -> ReviewSummary:
        state = str(row["state"]) if cls._consistent(row) else "invalidated"
        expires = datetime.fromisoformat(row["expires_at"])
        if state == "pending" and now >= expires:
            state = "expired"
        return ReviewSummary(
            UUID(row["memory_id"]),
            CandidateKind(row["candidate_kind"]),
            state,
            int(row["actual_revision"]),
            expires,
            UUID(row["source_event_id"]),
            UUID(row["replaces_id"]) if row["replaces_id"] else None,
        )

    def _preview(
        self,
        c: sqlite3.Connection,
        row: sqlite3.Row,
        now: datetime,
    ) -> ReviewPreview | None:
        scope = SourceScope(row["identity_id"], row["person_id"], row["session_id"])
        summary = self._summary(row, now)
        if summary.state != "pending":
            return None
        checked = SQLiteMemorySourceRepository.inspect(
            c,
            UUID(row["source_event_id"]),
            scope,
            route_privacy=Privacy.LOCAL_ONLY,
            policy_revision=int(row["source_policy_revision"]),
            policy_hash=row["source_policy_hash"],
            now=now,
        )
        if checked.snapshot is None or checked.snapshot.source_hash != row["source_hash"]:
            return None
        source = replace(checked.snapshot, captured_at=datetime.fromisoformat(row["captured_at"]))
        selected = classify_source_text(source.source.payload.text)
        if selected is None:
            return None
        draft = _draft(source, selected)
        if (
            draft.candidate_id != summary.candidate_id
            or draft.selection.kind != summary.kind
            or draft.selection.text != row["memory_text"]
            or draft.generator_version != row["generator_version"]
            or draft.valid_until != summary.expires_at
            or datetime.fromisoformat(row["memory_valid_to"]) != draft.valid_until
        ):
            return None
        return ReviewPreview(summary, draft)

    def _lookup(
        self,
        c: sqlite3.Connection,
        action_id: UUID,
        scope: SourceScope,
        permit: ReviewPermit,
        command_hash: str | None,
    ) -> ReviewResult | None:
        row = c.execute(
            "SELECT a.*,r.candidate_kind FROM memory_candidate_actions a "
            "JOIN memory_candidate_reviews r ON r.memory_id=a.memory_id "
            "WHERE a.action_id=? AND a.identity_id=? AND a.person_id=? AND a.session_id=?",
            (str(action_id), scope.identity_id, scope.person_id, scope.session_id),
        ).fetchone()
        if row is None:
            return None
        if CandidateKind(row["candidate_kind"]) not in permit.kinds:
            return ReviewResult(ReviewOutcome.DENIED)
        if command_hash is not None and row["command_hash"] != command_hash:
            return ReviewResult(ReviewOutcome.CONFLICT)
        return ReviewResult(
            ReviewOutcome.ALREADY_APPLIED,
            UUID(row["memory_id"]),
            int(row["memory_revision"]),
            row["state_at_commit"],
        )

    async def lookup(
        self,
        action_id: UUID,
        scope: SourceScope,
        permit: ReviewPermit,
        *,
        command_hash: str | None = None,
    ) -> ReviewResult | None:
        def read(c: sqlite3.Connection) -> ReviewResult | None:
            c.execute("PRAGMA query_only=ON")
            if not any(permit.allows(scope, op, self._now()) for op in permit.operations):
                return None
            return self._lookup(c, action_id, scope, permit, command_hash)

        return await self._store.run_transaction(read)

    async def pending(self, scope: SourceScope, permit: ReviewPermit) -> tuple[ReviewSummary, ...]:
        def read(c: sqlite3.Connection) -> tuple[ReviewSummary, ...]:
            c.execute("PRAGMA query_only=ON")
            now = self._now()
            if not permit.allows(scope, ReviewOperation.READ, now):
                return ()
            rows = c.execute(
                "SELECT memory_id FROM memory_candidate_reviews "
                "WHERE identity_id=? AND person_id=? AND session_id=? AND state='pending' "
                "ORDER BY captured_at,memory_id LIMIT 100",
                (scope.identity_id, scope.person_id, scope.session_id),
            ).fetchall()
            summaries = []
            for item in rows:
                row = self._row(c, UUID(item["memory_id"]), scope)
                if row is not None and CandidateKind(row["candidate_kind"]) in permit.kinds:
                    summaries.append(self._summary(row, now))
            return tuple(summaries)

        return await self._store.run_transaction(read)

    async def draft(
        self,
        candidate_id: UUID,
        scope: SourceScope,
        permit: ReviewPermit,
    ) -> ReviewPreview | None:
        def read(c: sqlite3.Connection) -> ReviewPreview | None:
            c.execute("PRAGMA query_only=ON")
            now = self._now()
            row = self._row(c, candidate_id, scope)
            # APPROVE lease may inspect its candidate before explicit approval.
            if row is None or not (
                permit.allows(scope, ReviewOperation.READ, now)
                or permit.allows(scope, ReviewOperation.APPROVE, now)
            ):
                return None
            if CandidateKind(row["candidate_kind"]) not in permit.kinds:
                return None
            return self._preview(c, row, now)

        return await self._store.run_transaction(read)

    @staticmethod
    def _check_source(
        c: sqlite3.Connection,
        draft: CandidateDraft,
        scope: SourceScope,
        now: datetime,
    ) -> ReviewOutcome | None:
        source = draft.source
        if source.scope != scope or source.route_privacy is not Privacy.LOCAL_ONLY:
            return ReviewOutcome.DENIED
        if draft.created_at > now or now >= draft.valid_until:
            return ReviewOutcome.EXPIRED
        selected = classify_source_text(source.source.payload.text)
        if selected is None or _draft(source, selected) != draft:
            return ReviewOutcome.SOURCE_INVALID
        checked = SQLiteMemorySourceRepository.inspect(
            c,
            source.source.event_id,
            scope,
            route_privacy=Privacy.LOCAL_ONLY,
            policy_revision=source.policy_revision,
            policy_hash=source.policy_hash,
            now=now,
        )
        fresh = checked.snapshot
        if fresh is None or (fresh.source_hash, fresh.source, fresh.valid_until) != (
            source.source_hash,
            source.source,
            source.valid_until,
        ):
            return ReviewOutcome.SOURCE_INVALID
        return None

    def _insert(
        self,
        c: sqlite3.Connection,
        draft: CandidateDraft,
        replaces_id: UUID | None,
    ) -> None:
        source = draft.source
        memory = Memory(
            draft.candidate_id,
            source.scope.identity_id,
            draft.selection.text,
            (source.source.event_id,),
            draft.created_at,
            kind=MemoryKind.EPISODIC,
            person_id=source.scope.person_id,
            status=MemoryStatus.CANDIDATE,
            valid_to=draft.valid_until,
        )
        self._memories._add_memory(c, memory, None)
        c.execute(
            "INSERT INTO memory_candidate_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'pending',1,?)",
            (
                str(memory.memory_id),
                source.scope.identity_id,
                source.scope.person_id,
                source.scope.session_id,
                str(source.source.event_id),
                source.source_hash,
                source.policy_revision,
                source.policy_hash,
                draft.generator_version,
                draft.selection.kind,
                draft.created_at.isoformat(),
                draft.valid_until.isoformat(),
                str(replaces_id) if replaces_id else None,
            ),
        )

    def _transition(
        self,
        c: sqlite3.Connection,
        row: sqlite3.Row,
        state: str,
        now: datetime,
        *,
        valid_to: datetime | None = None,
    ) -> None:
        approved = state == "approved"
        c.execute(
            "UPDATE memories SET status=?,revision=revision+1,deleted_at=?,valid_to=? "
            "WHERE memory_id=? AND revision=?",
            (
                "committed" if approved else "deleted",
                None if approved else (row["deleted_at"] or now.isoformat()),
                (valid_to.isoformat() if valid_to else None)
                if approved
                else row["memory_valid_to"],
                row["memory_id"],
                row["actual_revision"],
            ),
        )
        updated = c.execute(
            "SELECT * FROM memories WHERE memory_id=?", (row["memory_id"],)
        ).fetchone()
        assert updated is not None
        memory = self._memories._to_memory(c, updated)
        self._memories._insert_revision(c, memory, reason="owner review: " + state, changed_at=now)
        c.execute("DELETE FROM memory_fts WHERE memory_id=?", (row["memory_id"],))
        self._memories._invalidate(c, row["memory_id"], reason="candidate reviewed", now=now)
        if approved:
            self._memories._index(c, memory)
        c.execute(
            "UPDATE memory_candidate_reviews SET state=?,memory_revision=? WHERE memory_id=?",
            (state, memory.revision, row["memory_id"]),
        )

    async def apply(
        self,
        command: ReviewCommand,
        permit: ReviewPermit,
        draft: CandidateDraft | None,
    ) -> ReviewResult:
        def write(c: sqlite3.Connection) -> ReviewResult:
            now = self._now()
            scope, op = command.scope, command.operation
            if not permit.allows(scope, op, now):
                return ReviewResult(ReviewOutcome.DENIED)
            recorded = self._lookup(c, command.action_id, scope, permit, command.fingerprint())
            if recorded is not None:
                return recorded
            if c.execute(
                "SELECT 1 FROM memory_candidate_actions WHERE action_id=?",
                (str(command.action_id),),
            ).fetchone():
                return ReviewResult(ReviewOutcome.CONFLICT)
            if draft is not None:
                if draft.selection.kind not in permit.kinds:
                    return ReviewResult(ReviewOutcome.DENIED)
                invalid = self._check_source(c, draft, scope, now)
                if invalid is not None:
                    return ReviewResult(invalid)
            new_source = op in {ReviewOperation.STAGE, ReviewOperation.REPLACE}
            if (new_source or op is ReviewOperation.APPROVE) and draft is None:
                return ReviewResult(ReviewOutcome.SOURCE_INVALID)
            if new_source and draft and command.source_event_id != draft.source.source.event_id:
                return ReviewResult(ReviewOutcome.CONFLICT)
            row = self._row(c, command.candidate_id, scope) if command.candidate_id else None
            if op is not ReviewOperation.STAGE:
                if row is None:
                    return ReviewResult(ReviewOutcome.NOT_FOUND)
                removable = (
                    op
                    in {ReviewOperation.REJECT, ReviewOperation.WITHDRAW, ReviewOperation.REPLACE}
                    and row["memory_status"] in {"candidate", "superseded", "deleted"}
                    and row["actual_identity"] == scope.identity_id
                    and row["actual_person"] == scope.person_id
                    and row["memory_kind"] == "episodic"
                )
                if (
                    row["state"] != "pending"
                    or row["actual_revision"] != command.expected_revision
                    or not (self._consistent(row) or removable)
                ):
                    return ReviewResult(ReviewOutcome.CONFLICT)
                if CandidateKind(row["candidate_kind"]) not in permit.kinds:
                    return ReviewResult(ReviewOutcome.DENIED)
            existing = self._row(c, draft.candidate_id, scope) if new_source and draft else None
            if existing is not None:
                if op is ReviewOperation.REPLACE or self._preview(c, existing, now) is None:
                    return ReviewResult(ReviewOutcome.CONFLICT)
                candidate_id, state, revision = UUID(existing["memory_id"]), "pending", 1
                outcome = ReviewOutcome.ALREADY_PRESENT
            elif new_source:
                assert draft is not None
                if command.source_event_id != draft.source.source.event_id:
                    return ReviewResult(ReviewOutcome.CONFLICT)
                count = c.execute(
                    "SELECT count(*) FROM memory_candidate_reviews WHERE identity_id=? "
                    "AND person_id=? AND session_id=? AND state='pending'",
                    (scope.identity_id, scope.person_id, scope.session_id),
                ).fetchone()[0]
                if count - int(op is ReviewOperation.REPLACE) >= permit.pending_limit:
                    return ReviewResult(ReviewOutcome.LIMIT_REACHED)
                if row is not None:
                    self._transition(c, row, "withdrawn", now)
                self._insert(c, draft, command.candidate_id)
                candidate_id, state, revision = draft.candidate_id, "pending", 1
                outcome = ReviewOutcome.APPLIED
            else:
                assert row is not None
                if op is ReviewOperation.APPROVE:
                    assert draft is not None
                    current = self._preview(c, row, now)
                    if current is None or current.draft != draft:
                        return ReviewResult(ReviewOutcome.SOURCE_INVALID)
                    expiry = draft.source.valid_until
                    if permit.memory_retention_seconds is not None:
                        configured = now + timedelta(seconds=permit.memory_retention_seconds)
                        expiry = min(expiry, configured) if expiry else configured
                    self._transition(c, row, "approved", now, valid_to=expiry)
                    state = "approved"
                else:
                    state = "rejected" if op is ReviewOperation.REJECT else "withdrawn"
                    self._transition(c, row, state, now)
                candidate_id, revision = UUID(row["memory_id"]), int(row["actual_revision"]) + 1
                outcome = ReviewOutcome.APPLIED
            end = self._now()
            if not permit.allows(scope, op, end):
                raise _Abort(ReviewOutcome.DENIED)
            if draft is not None and end >= draft.valid_until:
                raise _Abort(ReviewOutcome.EXPIRED)
            c.execute(
                "INSERT INTO memory_candidate_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(command.action_id),
                    command.fingerprint(),
                    str(candidate_id),
                    scope.identity_id,
                    scope.person_id,
                    scope.session_id,
                    op,
                    revision,
                    state,
                    permit.revision,
                    permit.fingerprint(),
                    end.isoformat(),
                ),
            )
            return ReviewResult(outcome, candidate_id, revision, state)

        try:
            return await self._store.run_transaction(write)
        except _Abort as error:
            return ReviewResult(error.outcome)
