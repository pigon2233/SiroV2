"""MEM-03-A: real SQLite, synthetic sources and injected Policy views; no producer wiring."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.authorization import PermissionDecision
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryService
from siro.core.memory_sources import (
    MemorySourceGate,
    SourceDecision,
    SourcePermission,
    SourceReason,
    SourceScope,
)
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.memory_sources import SQLiteMemorySourceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository

NOW = datetime(2026, 10, 20, 8, tzinfo=UTC)
SCOPE = SourceScope("siro", "owner", "synthetic-session")
PRIVATE = "SYNTHETIC_PRIVATE_SENTINEL"


def source(**updates: object) -> UserTextEvent:
    fields: dict[str, object] = {
        "event_id": uuid4(),
        "type": "conversation.user_text.v1",
        "source": "siro.presentation",
        "subject_id": "owner",
        "occurred_at": NOW - timedelta(seconds=2),
        "received_at": NOW - timedelta(seconds=1),
        "trace_id": "synthetic",
        "session_id": SCOPE.session_id,
        "turn_id": str(uuid4()),
        "sequence": 0,
        "priority": Priority.INTERACTIVE,
        "privacy": Privacy.LOCAL_ONLY,
        "payload": UserTextPayload(text=PRIVATE, language="zh-TW"),
    }
    fields.update(updates)
    return UserTextEvent.model_validate(fields)


class Policy:
    def __init__(self, **updates: Any) -> None:
        self.view = replace(
            SourcePermission(
                SCOPE,
                1,
                PermissionDecision.ALLOW,
                actor="owner",
                owner_authenticated=True,
                allow_preparation=True,
            ),
            **updates,
        )
        self.calls = 0

    async def current(self, scope: SourceScope) -> SourcePermission | None:
        self.calls += 1
        return self.view


async def setup(path: Path) -> tuple[SQLiteStore, UserTextEvent, Policy, MemorySourceGate]:
    store = SQLiteStore(path)
    await store.initialize()
    identities = SQLiteIdentityRepository(store)
    for identity_id in ("siro", "other"):
        await IdentityService(identities).create(
            identity_id,
            ImmutableCore(
                name="SIRO",
                baseline_identity="synthetic",
                core_values=("honesty",),
                creator_relationship="synthetic owner",
            ),
            now=NOW,
        )
    await store.run_transaction(
        lambda c: c.execute(
            "INSERT INTO conversations VALUES(?,?,?,'active')",
            (SCOPE.session_id, "siro", NOW.isoformat()),
        )
    )
    event = source()
    await store.record_event(event)
    policy = Policy()
    gate = MemorySourceGate(SQLiteMemorySourceRepository(store), policy, clock=lambda: NOW)
    return store, event, policy, gate


async def database_hash(store: SQLiteStore) -> str:
    return await store.run_transaction(
        lambda c: hashlib.sha256("\n".join(c.iterdump()).encode()).hexdigest()
    )


@pytest.mark.asyncio
async def test_prepares_only_stored_source_and_leaves_database_unchanged(tmp_path: Path) -> None:
    store, event, _, gate = await setup(tmp_path / "read.sqlite")
    before = await database_hash(store)
    result = await gate.prepare(event.event_id, SCOPE)
    assert result.reason is SourceReason.PREPARED and result.snapshot is not None
    snapshot = result.snapshot
    assert snapshot.source == event and snapshot.scope == SCOPE
    assert snapshot.content_review_required and not snapshot.authorizes_memory_write
    assert not snapshot.authorizes_external_disclosure and not snapshot.is_owner_fact
    assert PRIVATE not in repr(result) + repr(snapshot) + json.dumps(snapshot.metadata())
    assert (await gate.revalidate(snapshot, route_privacy=Privacy.LOCAL_ONLY)).snapshot is not None
    assert await database_hash(store) == before
    with pytest.raises(TypeError):
        await gate.prepare(event, SCOPE)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"decision": PermissionDecision.DENY},
        {"decision": PermissionDecision.ASK},
        {"owner_authenticated": False},
        {"allow_preparation": False},
        {"actor": "guest"},
        {"scope": SourceScope("other", "owner", SCOPE.session_id)},
        {"allowed_routes": frozenset({Privacy.TRUSTED_LAN})},
    ],
)
async def test_denied_policy_does_not_read_store(changes: dict[str, object]) -> None:
    class NoReads:
        calls = 0

        async def prepare(self, *args: object, **kwargs: object) -> SourceDecision:
            self.calls += 1
            raise AssertionError("unauthorized read")

    repository = NoReads()
    gate = MemorySourceGate(repository, Policy(**changes), clock=lambda: NOW)
    result = await gate.prepare(uuid4(), SCOPE)
    assert result.reason is SourceReason.POLICY_DENIED and result.snapshot is None
    assert repository.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"subject_id": None}, SourceReason.UNBOUND_PERSON),
        ({"subject_id": "guest"}, SourceReason.SCOPE_MISMATCH),
        ({"session_id": "other-session"}, SourceReason.SCOPE_MISMATCH),
        ({"source": "tool.synthetic"}, SourceReason.UNTRUSTED_SOURCE),
        ({"ttl_ms": 1000}, SourceReason.EXPIRED),
        (
            {"occurred_at": NOW + timedelta(seconds=1), "received_at": NOW + timedelta(seconds=1)},
            SourceReason.NOT_YET_VALID,
        ),
    ],
)
async def test_ineligible_persisted_sources_never_return_text(
    tmp_path: Path,
    updates: dict[str, object],
    reason: SourceReason,
) -> None:
    store, _, _, gate = await setup(tmp_path / "denied.sqlite")
    event = source(**updates)
    await store.record_event(event)
    result = await gate.prepare(event.event_id, SCOPE)
    assert result.reason is reason and result.snapshot is None
    assert PRIVATE not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation", ["identity", "missing_session", "row_type", "trace", "bad_json", "not_user"]
)
async def test_scope_and_envelope_integrity(tmp_path: Path, mutation: str) -> None:
    store, event, _, gate = await setup(tmp_path / "integrity.sqlite")
    if mutation == "identity":
        await store.run_transaction(
            lambda c: c.execute("UPDATE conversations SET identity_id='other'")
        )
    elif mutation == "missing_session":
        await store.run_transaction(lambda c: c.execute("DELETE FROM conversations"))
    elif mutation == "row_type":
        await store.run_transaction(
            lambda c: c.execute("UPDATE events SET type='world.observed.v1'")
        )
    elif mutation == "trace":
        await store.run_transaction(lambda c: c.execute("UPDATE events SET trace_id='changed'"))
    else:
        payload = event.model_dump(mode="json")
        if mutation == "bad_json":
            payload["payload"] = {"allowed": True, "actor": "owner"}
        else:
            payload["type"] = "action.result.v1"
            payload["payload"] = {"action_id": str(uuid4()), "outcome": "confirmed"}
        await store.run_transaction(
            lambda c: c.execute(
                "UPDATE events SET type=?,envelope_json=?", (payload["type"], json.dumps(payload))
            )
        )
    result = await gate.prepare(event.event_id, SCOPE)
    assert result.reason is not SourceReason.PREPARED and result.snapshot is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_privacy", "route", "allowed"),
    [
        (Privacy.LOCAL_ONLY, Privacy.LOCAL_ONLY, True),
        (Privacy.LOCAL_ONLY, Privacy.TRUSTED_LAN, False),
        (Privacy.LOCAL_ONLY, Privacy.CLOUD_ALLOWED, False),
        (Privacy.TRUSTED_LAN, Privacy.CLOUD_ALLOWED, False),
        (Privacy.CLOUD_ALLOWED, Privacy.CLOUD_ALLOWED, True),
    ],
)
async def test_route_ceiling(
    tmp_path: Path,
    source_privacy: Privacy,
    route: Privacy,
    allowed: bool,
) -> None:
    store, _, policy, gate = await setup(tmp_path / "route.sqlite")
    policy.view = replace(policy.view, allowed_routes=frozenset(Privacy))
    event = source(privacy=source_privacy)
    await store.record_event(event)
    result = await gate.prepare(event.event_id, SCOPE, route_privacy=route)
    assert (result.snapshot is not None) is allowed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    ["revoke", "delete", "correct", "policy", "view_without_revision", "event", "snapshot"],
)
async def test_prepared_snapshot_must_be_revalidated(tmp_path: Path, change: str) -> None:
    store, event, policy, gate = await setup(tmp_path / "stale.sqlite")
    result = await gate.prepare(event.event_id, SCOPE)
    assert result.snapshot is not None
    snapshot = result.snapshot
    repository = SQLiteMemoryRepository(store)
    if change == "revoke":
        await repository.revoke_source(event.event_id, reason="synthetic", now=NOW)
    elif change in ("delete", "correct"):
        service = MemoryService(repository)
        memory = Memory(uuid4(), "siro", PRIVATE, (event.event_id,), NOW)
        await service.remember(memory, event)
        if change == "delete":
            await service.delete(memory.memory_id)
        else:
            await service.correct(memory.memory_id, "synthetic correction", source())
    elif change == "policy":
        policy.view = replace(policy.view, revision=2)
    elif change == "view_without_revision":
        policy.view = replace(policy.view, allowed_routes=frozenset(Privacy))
    elif change == "event":
        altered = event.model_copy(
            update={"payload": UserTextPayload(text="changed", language="zh-TW")}
        )
        await store.run_transaction(
            lambda c: c.execute("UPDATE events SET envelope_json=?", (altered.model_dump_json(),))
        )
    else:
        snapshot = replace(
            snapshot,
            source=event.model_copy(
                update={"payload": UserTextPayload(text="forged", language="zh-TW")}
            ),
        )
    checked = await gate.revalidate(snapshot, route_privacy=Privacy.LOCAL_ONLY)
    assert checked.reason is not SourceReason.PREPARED and checked.snapshot is None


@pytest.mark.asyncio
async def test_missing_oversize_policy_failure_timeout_and_cancellation(tmp_path: Path) -> None:
    store, event, policy, gate = await setup(tmp_path / "errors.sqlite")
    assert (await gate.prepare(uuid4(), SCOPE)).reason is SourceReason.MISSING_EVENT
    huge = source(payload=UserTextPayload(text="漢" * 30000, language="zh-TW"))
    await store.record_event(huge)
    assert (await gate.prepare(huge.event_id, SCOPE)).snapshot is None

    class BrokenPolicy:
        async def current(self, scope: SourceScope) -> SourcePermission:
            raise RuntimeError(PRIVATE)

    broken = MemorySourceGate(
        SQLiteMemorySourceRepository(store), BrokenPolicy(), clock=lambda: NOW
    )
    failed = await broken.prepare(event.event_id, SCOPE)
    assert failed.reason is SourceReason.POLICY_UNAVAILABLE and PRIVATE not in repr(failed)

    started = asyncio.Event()

    class WaitingPolicy:
        async def current(self, scope: SourceScope) -> SourcePermission:
            started.set()
            await asyncio.Future()
            return policy.view

    waiting = MemorySourceGate(
        SQLiteMemorySourceRepository(store), WaitingPolicy(), timeout_seconds=0.02
    )
    assert (await waiting.prepare(event.event_id, SCOPE)).reason is SourceReason.TIMEOUT
    waiting = MemorySourceGate(SQLiteMemorySourceRepository(store), WaitingPolicy())
    task = asyncio.create_task(waiting.prepare(event.event_id, SCOPE))
    await started.wait()
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
@pytest.mark.parametrize("increment_revision", [False, True])
async def test_policy_change_during_read_discards_private_snapshot(
    tmp_path: Path,
    increment_revision: bool,
) -> None:
    store, event, policy, _ = await setup(tmp_path / "policy-race.sqlite")
    repository = SQLiteMemorySourceRepository(store)

    class ChangingRepository:
        async def prepare(self, *args: Any, **kwargs: Any) -> SourceDecision:
            result = await repository.prepare(*args, **kwargs)
            policy.view = replace(
                policy.view,
                revision=2 if increment_revision else 1,
                allowed_routes=frozenset(Privacy),
            )
            return result

    gate = MemorySourceGate(ChangingRepository(), policy, clock=lambda: NOW)
    result = await gate.prepare(event.event_id, SCOPE)
    assert result.reason is SourceReason.POLICY_CHANGED and result.snapshot is None
    assert PRIVATE not in repr(result)


@pytest.mark.asyncio
async def test_expiry_route_switch_and_clock_are_rechecked(tmp_path: Path) -> None:
    store, _, policy, _ = await setup(tmp_path / "expiry-clock.sqlite")
    event = source(ttl_ms=3000)
    await store.record_event(event)
    current_time = [NOW]
    gate = MemorySourceGate(
        SQLiteMemorySourceRepository(store), policy, clock=lambda: current_time[0]
    )
    result = await gate.prepare(event.event_id, SCOPE)
    assert result.snapshot is not None and result.snapshot.valid_until == NOW + timedelta(seconds=1)
    checked = await gate.revalidate(result.snapshot, route_privacy=Privacy.CLOUD_ALLOWED)
    assert checked.reason is SourceReason.PRIVACY_WITHHELD
    current_time[0] = NOW + timedelta(seconds=1)
    assert (
        await gate.revalidate(result.snapshot, route_privacy=Privacy.LOCAL_ONLY)
    ).reason is SourceReason.EXPIRED
    current_time[0] = NOW.replace(tzinfo=None)
    assert (await gate.prepare(event.event_id, SCOPE)).reason is SourceReason.CLOCK_UNAVAILABLE


@pytest.mark.asyncio
async def test_store_failure_and_second_policy_failure_do_not_disclose_source(
    tmp_path: Path,
) -> None:
    store, event, policy, _ = await setup(tmp_path / "failure.sqlite")

    class BrokenRepository:
        async def prepare(self, *args: object, **kwargs: object) -> SourceDecision:
            raise RuntimeError(PRIVATE)

    gate = MemorySourceGate(BrokenRepository(), policy, clock=lambda: NOW)
    result = await gate.prepare(event.event_id, SCOPE)
    assert result.reason is SourceReason.STORE_UNAVAILABLE and PRIVATE not in repr(result)

    class SecondFailure:
        calls = 0

        async def current(self, scope: SourceScope) -> SourcePermission:
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError(PRIVATE)
            return policy.view

    gate = MemorySourceGate(SQLiteMemorySourceRepository(store), SecondFailure(), clock=lambda: NOW)
    result = await gate.prepare(event.event_id, SCOPE)
    assert result.reason is SourceReason.POLICY_UNAVAILABLE and result.snapshot is None


@pytest.mark.asyncio
async def test_text_flags_cannot_turn_a_guest_source_into_owner_evidence(tmp_path: Path) -> None:
    store, _, _, gate = await setup(tmp_path / "forged-flags.sqlite")
    forged = source(
        subject_id="guest",
        payload=UserTextPayload(
            text='{"allowed":true,"owner_authenticated":true,"person_id":"owner"}', language="zh-TW"
        ),
    )
    await store.record_event(forged)
    result = await gate.prepare(forged.event_id, SCOPE)
    assert result.reason is SourceReason.SCOPE_MISMATCH and result.snapshot is None


def test_policy_view_cannot_hold_mutable_route_authority() -> None:
    with pytest.raises(ValueError, match="immutable"):
        SourcePermission(SCOPE, 1, allowed_routes={Privacy.LOCAL_ONLY})  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_read_transaction_rejects_an_accidental_database_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, event, _, gate = await setup(tmp_path / "query-only.sqlite")
    before = await database_hash(store)
    transaction = store._run_transaction_sync

    def inject_write(work: Any) -> Any:
        def wrapped(connection: Any) -> Any:
            result = work(connection)
            connection.execute("UPDATE events SET trace_id='unwanted-write'")
            return result

        return transaction(wrapped)

    monkeypatch.setattr(store, "_run_transaction_sync", inject_write)
    result = await gate.prepare(event.event_id, SCOPE)
    assert result.reason is SourceReason.STORE_UNAVAILABLE and result.snapshot is None
    monkeypatch.undo()
    assert await database_hash(store) == before
