"""Injected policy leases and real SQLite; not production owner authentication."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.authorization import PermissionDecision
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryService
from siro.core.memory_candidates import CandidateDraft, CandidateKind, MemoryCandidateGenerator
from siro.core.memory_review import (
    MemoryReviewService,
    ReviewCommand,
    ReviewOperation,
    ReviewOutcome,
    ReviewPermit,
    ReviewReadUnavailable,
    ReviewResult,
)
from siro.core.memory_sources import MemorySourceGate, SourcePermission, SourceScope
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.memory_review import SQLiteMemoryReviewRepository
from siro.persistence.memory_sources import SQLiteMemorySourceRepository
from siro.persistence.sqlite import SQLiteStore, apply_migrations, load_migrations
from siro.persistence.state import SQLiteIdentityRepository

NOW = datetime(2026, 10, 20, tzinfo=UTC)
SCOPE = SourceScope("siro", "owner", "synthetic-review-session")
TEXT = "我喜歡無糖烏龍茶。"


class Policy:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.held = False
        self.view = ReviewPermit(
            SCOPE,
            1,
            NOW + timedelta(days=7),
            decision=PermissionDecision.ALLOW,
            actor="owner",
            owner_authenticated=True,
            operations=frozenset(ReviewOperation),
            kinds=frozenset(CandidateKind),
        )
        self.source = SourcePermission(
            SCOPE,
            1,
            PermissionDecision.ALLOW,
            actor="owner",
            owner_authenticated=True,
            allow_preparation=True,
        )

    async def current(self, scope: SourceScope) -> SourcePermission:
        return self.source

    @asynccontextmanager
    async def lease(
        self,
        scope: SourceScope,
        operation: ReviewOperation,
    ) -> AsyncIterator[ReviewPermit | None]:
        async with self.lock:
            self.held = True
            try:
                yield self.view
            finally:
                self.held = False

    async def disable_source(self) -> None:
        async with self.lock:
            self.source = replace(self.source, allow_preparation=False, revision=2)


def source(text: str = TEXT, **updates: Any) -> UserTextEvent:
    fields = dict(
        type="conversation.user_text.v1",
        event_id=uuid4(),
        source="siro.presentation",
        subject_id="owner",
        occurred_at=NOW,
        received_at=NOW,
        trace_id="synthetic",
        session_id=SCOPE.session_id,
        turn_id="synthetic-turn",
        sequence=0,
        priority=Priority.INTERACTIVE,
        privacy=Privacy.LOCAL_ONLY,
        payload=UserTextPayload(text=text, language="zh-TW"),
    )
    fields.update(updates)
    return UserTextEvent.model_validate(fields)


def service(
    store: SQLiteStore,
    policy: Policy,
    clock: list[datetime],
    repository: SQLiteMemoryReviewRepository | None = None,
) -> MemoryReviewService:
    gate = MemorySourceGate(SQLiteMemorySourceRepository(store), policy, clock=lambda: clock[0])
    return MemoryReviewService(
        repository or SQLiteMemoryReviewRepository(store, clock=lambda: clock[0]),
        MemoryCandidateGenerator(gate),
        policy,
        clock=lambda: clock[0],
    )


async def setup(
    path: Path,
    **updates: Any,
) -> tuple[SQLiteStore, UserTextEvent, Policy, list[datetime], MemoryReviewService]:
    store = SQLiteStore(path)
    await store.initialize()
    for identity in ("siro", "other"):
        await IdentityService(SQLiteIdentityRepository(store)).create(
            identity,
            ImmutableCore(
                name="SIRO",
                baseline_identity="synthetic",
                core_values=("honesty",),
                creator_relationship="synthetic",
            ),
            now=NOW,
        )
    await store.run_transaction(
        lambda c: c.execute(
            "INSERT INTO conversations VALUES(?,?,?,'active')",
            (SCOPE.session_id, "siro", NOW.isoformat()),
        )
    )
    event = source(**updates)
    await store.record_event(event)
    policy, clock = Policy(), [NOW]
    return store, event, policy, clock, service(store, policy, clock)


def command(
    operation: ReviewOperation,
    candidate_id: UUID | None = None,
    *,
    event_id: UUID | None = None,
    action_id: UUID | None = None,
    revision: int = 1,
    scope: SourceScope = SCOPE,
) -> ReviewCommand:
    return ReviewCommand(
        action_id or uuid4(),
        scope,
        operation,
        candidate_id,
        revision if candidate_id is not None else None,
        event_id,
    )


async def digest(store: SQLiteStore) -> str:
    return await store.run_transaction(
        lambda c: hashlib.sha256("\n".join(c.iterdump()).encode()).hexdigest()
    )


@pytest.mark.asyncio
async def test_stage_restart_preview_approve_and_readback_use_existing_memory(
    tmp_path: Path,
) -> None:
    store, event, policy, clock, review = await setup(tmp_path / "review.sqlite")
    request = command(ReviewOperation.STAGE, event_id=event.event_id)
    staged = await review.execute(request)
    assert staged.outcome is ReviewOutcome.APPLIED and staged.candidate_id
    candidate = staged.candidate_id
    memories = MemoryService(SQLiteMemoryRepository(store))
    assert await memories.recall("siro", "烏龍茶") == []
    assert (
        await store.run_transaction(
            lambda c: c.execute("SELECT count(*) FROM memory_fts").fetchone()[0]
        )
        == 0
    )
    restarted = SQLiteStore(store.path)
    await restarted.initialize()
    review = service(restarted, policy, clock)
    summaries = await review.pending(SCOPE)
    assert len(summaries) == 1 and summaries[0].state == "pending"
    preview = await review.preview(candidate, SCOPE)
    assert preview and preview.draft.selection.text == TEXT
    assert TEXT not in repr(preview) + repr(summaries) + json.dumps(preview.draft.metadata())
    approved = await review.execute(command(ReviewOperation.APPROVE, candidate))
    assert approved.outcome is ReviewOutcome.APPLIED and approved.revision == 2
    found = await memories.recall("siro", "烏龍茶", as_of=NOW)
    assert len(found) == 1 and found[0].text == TEXT and found[0].kind.value == "episodic"
    assert (
        await memories.recall("siro", "烏龍茶", route_privacy=Privacy.CLOUD_ALLOWED, as_of=NOW)
        == []
    )
    assert await review.pending(SCOPE) == ()
    assert [r.status.value for r in await memories.revisions(candidate)] == [
        "candidate",
        "committed",
    ]
    repeated = await review.execute(request)
    assert repeated.outcome is ReviewOutcome.ALREADY_APPLIED
    assert repeated.state_at_commit == "pending"  # Historical receipt, not current status.
    assert (await review.lookup(request.action_id, SCOPE)) == repeated


@pytest.mark.asyncio
@pytest.mark.parametrize("op", [ReviewOperation.REJECT, ReviewOperation.WITHDRAW])
async def test_reject_withdraw_and_retries_do_not_refill_sources(
    tmp_path: Path, op: ReviewOperation
) -> None:
    store, event, _, _, review = await setup(tmp_path / "reject.sqlite")
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id
    request = command(op, staged.candidate_id)
    result = await review.execute(request)
    assert result.outcome is ReviewOutcome.APPLIED and result.revision == 2
    before = await digest(store)
    assert (await review.execute(request)).outcome is ReviewOutcome.ALREADY_APPLIED
    assert await digest(store) == before
    assert (
        await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    ).outcome is ReviewOutcome.SOURCE_INVALID
    assert (
        await review.execute(command(ReviewOperation.APPROVE, staged.candidate_id))
    ).outcome is ReviewOutcome.NOT_FOUND


@pytest.mark.asyncio
async def test_replace_edit_is_atomic_and_binds_new_owner_event(tmp_path: Path) -> None:
    store, event, policy, _, review = await setup(tmp_path / "edit.sqlite")
    policy.view = replace(policy.view, pending_limit=1)
    old = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert old.candidate_id
    edited = source("我偏好使用繁體中文。")
    await store.record_event(edited)
    result = await review.execute(
        command(ReviewOperation.REPLACE, old.candidate_id, event_id=edited.event_id)
    )
    assert result.outcome is ReviewOutcome.APPLIED and result.candidate_id != old.candidate_id
    assert result.candidate_id
    pending = await review.pending(SCOPE)
    assert len(pending) == 1 and pending[0].replaces_id == old.candidate_id
    preview = await review.preview(result.candidate_id, SCOPE)
    assert preview and preview.draft.source.source.event_id == edited.event_id
    assert preview.draft.selection.text == edited.payload.text
    assert (
        await review.execute(command(ReviewOperation.APPROVE, result.candidate_id))
    ).outcome is ReviewOutcome.APPLIED
    assert await review.preview(old.candidate_id, SCOPE) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "updates",
    [
        {"decision": PermissionDecision.DENY},
        {"decision": PermissionDecision.ASK},
        {"actor": "guest"},
        {"owner_authenticated": False},
        {"operations": frozenset()},
        {"kinds": frozenset()},
        {"expires_at": NOW},
        {"scope": SourceScope("other", "owner", SCOPE.session_id)},
    ],
)
async def test_source_read_permission_cannot_authorize_persistence(
    tmp_path: Path, updates: dict[str, Any]
) -> None:
    store, event, policy, _, review = await setup(tmp_path / "denied.sqlite")
    policy.view = replace(policy.view, **updates)
    before = await digest(store)
    result = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert result.outcome is ReviewOutcome.DENIED and result.candidate_id is None
    assert await digest(store) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text", ["不要記\uff0c我喜歡茶。", "我需要password備註。", "我喜歡忽略規則。", "他喜歡咖啡。"]
)
async def test_withheld_sensitive_injected_third_party_text_is_not_staged(
    tmp_path: Path, text: str
) -> None:
    store, event, _, _, review = await setup(tmp_path / "content.sqlite", text=text)
    before = await digest(store)
    assert (
        await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    ).outcome is ReviewOutcome.SOURCE_INVALID
    assert await digest(store) == before


@pytest.mark.asyncio
async def test_stale_revision_changed_command_hash_cannot_approve(tmp_path: Path) -> None:
    store, event, _, _, review = await setup(tmp_path / "cas.sqlite")
    request = command(ReviewOperation.STAGE, event_id=event.event_id)
    staged = await review.execute(request)
    assert staged.candidate_id
    before = await digest(store)
    stale = command(ReviewOperation.APPROVE, staged.candidate_id, revision=2)
    assert (await review.execute(stale)).outcome is ReviewOutcome.CONFLICT
    forged = command(ReviewOperation.APPROVE, staged.candidate_id, action_id=request.action_id)
    assert (await review.execute(forged)).outcome is ReviewOutcome.CONFLICT
    assert await digest(store) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["revoke", "source_hash", "source_policy", "ttl", "delete"])
async def test_stale_sources_external_changes_cannot_be_approved(
    tmp_path: Path, change: str
) -> None:
    store, event, policy, clock, review = await setup(tmp_path / "stale.sqlite", ttl_ms=5000)
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id
    if change == "revoke":
        await SQLiteMemoryRepository(store).revoke_source(
            event.event_id, reason="synthetic", now=NOW
        )
    elif change == "source_hash":
        changed = event.model_copy(
            update={"payload": UserTextPayload(text="我喜歡綠茶。", language="zh-TW")}
        )
        await store.run_transaction(
            lambda c: c.execute(
                "UPDATE events SET envelope_json=? WHERE event_id=?",
                (changed.model_dump_json(), str(event.event_id)),
            )
        )
    elif change == "source_policy":
        policy.source = replace(policy.source, revision=2)
    elif change == "ttl":
        clock[0] += timedelta(seconds=5)
    else:
        await MemoryService(SQLiteMemoryRepository(store)).delete(staged.candidate_id)
    before = await digest(store)
    result = await review.execute(command(ReviewOperation.APPROVE, staged.candidate_id))
    assert result.outcome in {ReviewOutcome.NOT_FOUND, ReviewOutcome.SOURCE_INVALID}
    assert await review.preview(staged.candidate_id, SCOPE) is None
    assert await digest(store) == before


@pytest.mark.asyncio
async def test_pending_limit_duplicate_does_not_extend_retention(tmp_path: Path) -> None:
    store, event, policy, clock, review = await setup(tmp_path / "limit.sqlite")
    policy.view = replace(policy.view, pending_limit=1)
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id
    first = await review.preview(staged.candidate_id, SCOPE)
    clock[0] += timedelta(seconds=1)
    assert (
        await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    ).outcome is ReviewOutcome.ALREADY_PRESENT
    second = await review.preview(staged.candidate_id, SCOPE)
    assert first and second and first.draft.valid_until == second.draft.valid_until
    another = source("我偏好簡短回答。")
    await store.record_event(another)
    assert (
        await review.execute(command(ReviewOperation.STAGE, event_id=another.event_id))
    ).outcome is ReviewOutcome.LIMIT_REACHED


@pytest.mark.asyncio
async def test_retention_source_ttl_both_limit_approved_memory(tmp_path: Path) -> None:
    store, event, policy, clock, review = await setup(tmp_path / "retention.sqlite", ttl_ms=5000)
    policy.view = replace(policy.view, memory_retention_seconds=60)
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id
    assert (
        await review.execute(command(ReviewOperation.APPROVE, staged.candidate_id))
    ).outcome is ReviewOutcome.APPLIED
    values = await MemoryService(SQLiteMemoryRepository(store)).recall("siro", "茶", as_of=NOW)
    assert values and values[0].valid_to == NOW + timedelta(seconds=5)
    clock[0] += timedelta(seconds=5)
    assert (
        await MemoryService(SQLiteMemoryRepository(store)).recall("siro", "茶", as_of=clock[0])
        == []
    )


@pytest.mark.asyncio
async def test_cross_scope_metadata_preview_action_lookup_are_empty(tmp_path: Path) -> None:
    _, event, policy, _, review = await setup(tmp_path / "scope.sqlite")
    request = command(ReviewOperation.STAGE, event_id=event.event_id)
    staged = await review.execute(request)
    assert staged.candidate_id
    other = SourceScope("other", "owner", SCOPE.session_id)
    policy.view = replace(policy.view, scope=other)
    assert await review.pending(other) == ()
    assert await review.preview(staged.candidate_id, other) is None
    assert await review.lookup(request.action_id, other) is None


@pytest.mark.asyncio
async def test_ledger_failure_rolls_back_revision_and_index(tmp_path: Path) -> None:
    store, event, _, _, review = await setup(tmp_path / "rollback.sqlite")
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id
    await store.run_transaction(
        lambda c: c.execute(
            "CREATE TRIGGER fail_review_ledger BEFORE INSERT ON memory_candidate_actions "
            "BEGIN SELECT RAISE(ABORT,'synthetic failure'); END"
        )
    )
    before = await digest(store)
    request = command(ReviewOperation.APPROVE, staged.candidate_id)
    assert (await review.execute(request)).outcome is ReviewOutcome.UNKNOWN
    assert await digest(store) == before
    assert await review.lookup(request.action_id, SCOPE) is None
    assert await review.preview(staged.candidate_id, SCOPE) is not None


def test_migration_16_to_17_additive_and_reopen_idempotent(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "migrate.sqlite")
    migrations = load_migrations()[:17]
    apply_migrations(connection, migrations[:16])
    old = connection.execute(
        "SELECT version,checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    apply_migrations(connection, migrations)
    apply_migrations(connection, migrations)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert (
        connection.execute(
            "SELECT version,checksum FROM schema_migrations WHERE version<=16 ORDER BY version"
        ).fetchall()
        == old
    )
    assert connection.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 17
    assert connection.execute("SELECT count(*) FROM memory_candidate_reviews").fetchone()[0] == 0
    connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["revoke", "source_hash", "identity", "ttl"])
async def test_transaction_rechecks_sources_after_core_preflight(
    tmp_path: Path, change: str
) -> None:
    store, event, policy, clock, review = await setup(tmp_path / "race.sqlite", ttl_ms=5000)
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id

    class Racing(SQLiteMemoryReviewRepository):
        async def apply(
            self,
            request: ReviewCommand,
            permit: ReviewPermit,
            draft: CandidateDraft | None,
        ) -> ReviewResult:
            if change == "revoke":
                await SQLiteMemoryRepository(store).revoke_source(
                    event.event_id, reason="synthetic race", now=NOW
                )
            elif change == "source_hash":
                changed = event.model_copy(
                    update={"payload": UserTextPayload(text="我偏好簡短回答。", language="zh-TW")}
                )
                await store.run_transaction(
                    lambda c: c.execute(
                        "UPDATE events SET envelope_json=? WHERE event_id=?",
                        (changed.model_dump_json(), str(event.event_id)),
                    )
                )
            elif change == "identity":
                await store.run_transaction(
                    lambda c: c.execute(
                        "UPDATE conversations SET identity_id='other' WHERE session_id=?",
                        (SCOPE.session_id,),
                    )
                )
            else:
                clock[0] += timedelta(seconds=5)
            return await super().apply(request, permit, draft)

    review = service(store, policy, clock, Racing(store, clock=lambda: clock[0]))
    request = command(ReviewOperation.APPROVE, staged.candidate_id)
    result = await review.execute(request)
    assert result.outcome in {ReviewOutcome.SOURCE_INVALID, ReviewOutcome.EXPIRED}
    assert await review.lookup(request.action_id, SCOPE) is None
    assert (
        await store.run_transaction(
            lambda c: c.execute(
                "SELECT count(*) FROM memories WHERE status='committed'"
            ).fetchone()[0]
        )
        == 0
    )
    assert (
        await store.run_transaction(
            lambda c: c.execute("SELECT count(*) FROM memory_fts").fetchone()[0]
        )
        == 0
    )


@pytest.mark.asyncio
async def test_cancel_joins_sqlite_before_releasing_policy_lease(tmp_path: Path) -> None:
    store, event, policy, clock, review = await setup(tmp_path / "cancel.sqlite")
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id
    entered, release = Event(), Event()

    class Blocking(SQLiteMemoryReviewRepository):
        async def apply(
            self,
            request: ReviewCommand,
            permit: ReviewPermit,
            draft: CandidateDraft | None,
        ) -> ReviewResult:
            original = self._clock

            def blocking_clock() -> datetime:
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("synthetic worker not released")
                return original()

            self._clock = blocking_clock
            try:
                return await super().apply(request, permit, draft)
            finally:
                self._clock = original

    review = service(store, policy, clock, Blocking(store, clock=lambda: clock[0]))
    request = command(ReviewOperation.APPROVE, staged.candidate_id)
    task = asyncio.create_task(review.execute(request))
    assert await asyncio.to_thread(entered.wait, 3)
    update = asyncio.create_task(policy.disable_source())
    try:
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()  # Repeated cancellation must not abandon the in-flight transaction.
        await asyncio.sleep(0.01)
        assert not task.done() and policy.held and not update.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await update
    result = await review.lookup(request.action_id, SCOPE)
    assert result and result.state_at_commit == "approved"
    assert not policy.held and not policy.source.allow_preparation


@pytest.mark.asyncio
async def test_expiring_permit_rolls_back_changes_at_transaction_end(tmp_path: Path) -> None:
    store, event, policy, clock, _ = await setup(tmp_path / "permit-expiry.sqlite")

    class Expiring(SQLiteMemoryReviewRepository):
        async def apply(
            self,
            request: ReviewCommand,
            permit: ReviewPermit,
            draft: CandidateDraft | None,
        ) -> ReviewResult:
            original, calls = self._clock, 0

            def advancing() -> datetime:
                nonlocal calls
                calls += 1
                return original() if calls == 1 else permit.expires_at

            self._clock = advancing
            try:
                return await super().apply(request, permit, draft)
            finally:
                self._clock = original

    review = service(store, policy, clock, Expiring(store, clock=lambda: clock[0]))
    before = await digest(store)
    result = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert result.outcome is ReviewOutcome.DENIED
    assert await digest(store) == before


@pytest.mark.asyncio
async def test_read_failure_is_sanitized_and_distinct_from_empty(tmp_path: Path) -> None:
    store, _, policy, clock, _ = await setup(tmp_path / "read-failure.sqlite")

    class Failing(SQLiteMemoryReviewRepository):
        async def pending(self, scope: SourceScope, permit: ReviewPermit) -> tuple[Any, ...]:
            raise OSError(TEXT)

    review = service(store, policy, clock, Failing(store, clock=lambda: clock[0]))
    with pytest.raises(ReviewReadUnavailable) as captured:
        await review.pending(SCOPE)
    assert TEXT not in str(captured.value)


def test_failed_migration_17_rolls_back_new_tables(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "migration-failure.sqlite")
    migrations = load_migrations()[:17]
    apply_migrations(connection, migrations[:16])
    failed = replace(migrations[-1], sql=migrations[-1].sql + ";NOT VALID SQL")
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(connection, (*migrations[:16], failed))
    assert connection.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 16
    assert (
        connection.execute(
            "SELECT name FROM sqlite_master WHERE name='memory_candidate_reviews'"
        ).fetchall()
        == []
    )
    connection.close()


@pytest.mark.asyncio
async def test_owner_can_withdraw_invalidated_pending_entry_with_current_revision(
    tmp_path: Path,
) -> None:
    store, event, _, _, review = await setup(tmp_path / "invalidated-withdraw.sqlite")
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id
    await SQLiteMemoryRepository(store).revoke_source(event.event_id, reason="synthetic", now=NOW)
    summary = (await review.pending(SCOPE))[0]
    assert summary.state == "invalidated" and summary.revision == 2
    result = await review.execute(
        command(ReviewOperation.WITHDRAW, staged.candidate_id, revision=summary.revision)
    )
    assert result.outcome is ReviewOutcome.APPLIED and result.revision == 3
    assert await review.pending(SCOPE) == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["correct", "delete", "revoke"])
async def test_approved_memory_keeps_existing_derivation_invalidation(
    tmp_path: Path,
    operation: str,
) -> None:
    store, event, _, _, review = await setup(tmp_path / "lineage.sqlite")
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id
    assert (
        await review.execute(command(ReviewOperation.APPROVE, staged.candidate_id))
    ).outcome is ReviewOutcome.APPLIED
    repository = SQLiteMemoryRepository(store)
    snapshot = await repository.capture_sources(
        "siro",
        "owner",
        (staged.candidate_id,),
        now=NOW,
        generator_version="synthetic-child",
        policy_revision=1,
    )
    child = Memory(uuid4(), "siro", "derived synthetic tea", (event.event_id,), NOW)
    await repository.add_derived(child, snapshot, now=NOW, policy_revision=1)
    memories = MemoryService(repository)
    if operation == "correct":
        await memories.correct(staged.candidate_id, "我改喝合成飲料", source("我偏好合成飲料。"))
    elif operation == "delete":
        await memories.delete(staged.candidate_id)
    else:
        await repository.revoke_source(event.event_id, reason="synthetic", now=NOW)
    assert await memories.recall("siro", "derived", as_of=NOW) == []
    assert not await repository.sources_current(snapshot, now=NOW)


@pytest.mark.asyncio
async def test_expired_pending_entry_can_be_withdrawn_without_source_preview(
    tmp_path: Path,
) -> None:
    _, event, _, clock, review = await setup(tmp_path / "expired.sqlite")
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id
    clock[0] += timedelta(hours=24)
    assert (await review.pending(SCOPE))[0].state == "expired"
    assert await review.preview(staged.candidate_id, SCOPE) is None
    assert (
        await review.execute(command(ReviewOperation.WITHDRAW, staged.candidate_id))
    ).outcome is ReviewOutcome.APPLIED


@pytest.mark.asyncio
@pytest.mark.parametrize("same_action", [True, False])
async def test_concurrent_approval_never_duplicates_revision_or_index(
    tmp_path: Path,
    same_action: bool,
) -> None:
    store, event, _, _, review = await setup(tmp_path / "concurrent.sqlite")
    staged = await review.execute(command(ReviewOperation.STAGE, event_id=event.event_id))
    assert staged.candidate_id
    first = command(ReviewOperation.APPROVE, staged.candidate_id)
    second = first if same_action else command(ReviewOperation.APPROVE, staged.candidate_id)
    results = await asyncio.gather(review.execute(first), review.execute(second))
    assert sum(result.outcome is ReviewOutcome.APPLIED for result in results) == 1
    revisions = await MemoryService(SQLiteMemoryRepository(store)).revisions(staged.candidate_id)
    assert [r.revision for r in revisions] == [1, 2]
    assert (
        await store.run_transaction(
            lambda c: c.execute(
                "SELECT count(*) FROM memory_fts WHERE memory_id=?", (str(staged.candidate_id),)
            ).fetchone()[0]
        )
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("maximum", [15, 16])
async def test_older_release_schema_limits_refuse_schema17(tmp_path: Path, maximum: int) -> None:
    from siro.core.releases import ReleaseManager, ReleaseManifest

    _, _, _, _, _ = await setup(tmp_path / "schema17.sqlite")
    manager = ReleaseManager(tmp_path / "release", bytes(range(32)), current_schema=17)
    manifest = ReleaseManifest(
        version="0.0.1",
        source_sha256="0" * 64,
        signature="0" * 64,
        min_schema=1,
        max_schema=maximum,
        signing_format="siro-release-manifest-v2",
    )
    assert not manager._compatible(manifest)
