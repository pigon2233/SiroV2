"""Offline content corpus; no synthetic input authorizes production memory writes."""

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
from siro.core.memory_candidates import (
    CandidateReason,
    MemoryCandidateGenerator,
    classify_source_text,
)
from siro.core.memory_sources import MemorySourceGate, SourcePermission, SourceReason, SourceScope
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.memory_sources import SQLiteMemorySourceRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository

CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures/automatic_memory_candidates.json").read_text("utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_content_corpus(case: dict[str, str | None]) -> None:
    selection = classify_source_text(str(case["text"]))
    assert (selection.kind.value if selection else None) == case["kind"]
    if selection:
        assert str(case["text"])[selection.start : selection.end] == selection.text


NOW = datetime(2026, 10, 20, tzinfo=UTC)
SCOPE = SourceScope("siro", "owner", "synthetic-session")


class Policy:
    def __init__(self) -> None:
        self.view = SourcePermission(
            SCOPE,
            1,
            PermissionDecision.ALLOW,
            actor="owner",
            owner_authenticated=True,
            allow_preparation=True,
        )
        self.calls = 0
        self.block = False

    async def current(self, scope: SourceScope) -> SourcePermission:
        self.calls += 1
        if self.block:
            await asyncio.Event().wait()
        return self.view


async def setup(
    path: Path, text: str = "我喜歡無糖烏龍茶。", **updates: Any
) -> tuple[SQLiteStore, UserTextEvent, Policy, list[datetime], MemoryCandidateGenerator]:
    store = SQLiteStore(path)
    await store.initialize()
    for identity in ("siro", "other"):
        await IdentityService(SQLiteIdentityRepository(store)).create(
            identity,
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
    event = UserTextEvent.model_validate(fields)
    await store.record_event(event)
    policy, clock = Policy(), [NOW]
    gate = MemorySourceGate(SQLiteMemorySourceRepository(store), policy, clock=lambda: clock[0])
    return store, event, policy, clock, MemoryCandidateGenerator(gate)


async def database_hash(store: SQLiteStore) -> str:
    return await store.run_transaction(
        lambda c: hashlib.sha256("\n".join(c.iterdump()).encode()).hexdigest()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "我不喜歡太甜的飲料。",
        "我確認我們已完成合成報告。",
        "我需要準備讀書會。",
    ],
)
async def test_real_sources_remain_exact_attributed_review_only_and_read_only(
    tmp_path: Path,
    text: str,
) -> None:
    store, event, _, _, generator = await setup(tmp_path / "candidate.sqlite", text)
    before = await database_hash(store)
    result = await generator.prepare(event.event_id, SCOPE)
    assert result.reason is CandidateReason.READY_FOR_REVIEW and result.draft
    draft = result.draft
    assert draft.selection.text == text and draft.source.source == event
    assert not draft.is_owner_fact and not draft.verified_tool_completion
    assert not draft.authorizes_memory_write and not draft.authorizes_execution
    assert draft.review_required
    assert text not in repr(draft) + repr(result) + json.dumps(draft.metadata())
    assert (await generator.revalidate(draft)).draft == draft
    repeated = await generator.prepare(event.event_id, SCOPE)
    assert repeated.draft and repeated.draft.candidate_id == draft.candidate_id
    assert await database_hash(store) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [c["text"] for c in CASES if c["kind"] is None])
async def test_rejected_content_never_adds_persistent_rows(tmp_path: Path, text: str) -> None:
    store, event, _, _, generator = await setup(tmp_path / "rejected.sqlite", text)
    before = await database_hash(store)
    result = await generator.prepare(event.event_id, SCOPE)
    assert result.reason is CandidateReason.NOT_SELECTED and result.draft is None
    assert text not in repr(result)
    assert await database_hash(store) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["policy", "revoke", "correct", "identity", "ttl"])
async def test_source_or_policy_change_invalidates_draft(tmp_path: Path, change: str) -> None:
    updates: dict[str, Any] = {"ttl_ms": 1000} if change == "ttl" else {}
    store, event, policy, clock, generator = await setup(tmp_path / "stale.sqlite", **updates)
    result = await generator.prepare(event.event_id, SCOPE)
    assert result.draft
    memories = MemoryService(SQLiteMemoryRepository(store))
    if change == "policy":
        policy.view = replace(policy.view, allow_preparation=False)
    elif change == "revoke":
        await SQLiteMemoryRepository(store).revoke_source(
            event.event_id, reason="synthetic", now=NOW
        )
    elif change == "correct":
        memory = Memory(uuid4(), "siro", event.payload.text, (event.event_id,), NOW)
        await memories.remember(memory, event)
        correction = event.model_copy(update={"event_id": uuid4()})
        await memories.correct(memory.memory_id, "我改喝合成飲料", correction, reason="synthetic")
    elif change == "identity":
        await store.run_transaction(
            lambda c: c.execute(
                "UPDATE conversations SET identity_id='other' WHERE session_id=?",
                (SCOPE.session_id,),
            )
        )
    else:
        clock[0] = NOW + timedelta(seconds=1)
    checked = await generator.revalidate(result.draft)
    assert checked.reason is CandidateReason.SOURCE_REJECTED and checked.draft is None


@pytest.mark.asyncio
async def test_untrusted_scope_payload_or_permission_never_generates_candidate(
    tmp_path: Path,
) -> None:
    _, event, policy, _, generator = await setup(tmp_path / "scope.sqlite")
    for scope in (
        SourceScope("other", "owner", SCOPE.session_id),
        SourceScope("siro", "guest", SCOPE.session_id),
    ):
        assert (await generator.prepare(event.event_id, scope)).draft is None
    policy.view = replace(policy.view, decision=PermissionDecision.DENY)
    assert (await generator.prepare(event.event_id, SCOPE)).draft is None
    with pytest.raises(TypeError):
        await generator.prepare(event, SCOPE)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["text", "kind", "span", "id", "expiry", "version"])
async def test_forged_draft_cannot_survive_source_reconstruction(
    tmp_path: Path, field: str
) -> None:
    _, event, _, _, generator = await setup(tmp_path / "forged.sqlite")
    result = await generator.prepare(event.event_id, SCOPE)
    assert result.draft
    draft = result.draft
    if field == "text":
        draft = replace(
            draft, selection=replace(draft.selection, text="假" * len(draft.selection.text))
        )
    elif field == "kind":
        from siro.core.memory_candidates import CandidateKind

        draft = replace(draft, selection=replace(draft.selection, kind=CandidateKind.TODO))
    elif field == "span":
        draft = replace(
            draft, selection=replace(draft.selection, start=1, end=draft.selection.end + 1)
        )
    elif field == "id":
        draft = replace(draft, candidate_id=uuid4())
    elif field == "expiry":
        draft = replace(draft, valid_until=draft.valid_until + timedelta(days=1))
    else:
        draft = replace(draft, generator_version="model-self-authorized")
    assert (await generator.revalidate(draft)).reason is CandidateReason.DRAFT_CHANGED


@pytest.mark.asyncio
async def test_ephemeral_draft_expires_even_if_source_does_not(tmp_path: Path) -> None:
    _, event, _, clock, generator = await setup(tmp_path / "expiry.sqlite")
    result = await generator.prepare(event.event_id, SCOPE)
    assert result.draft
    clock[0] = NOW + timedelta(hours=24)
    assert (await generator.revalidate(result.draft)).reason is CandidateReason.EXPIRED


@pytest.mark.asyncio
async def test_policy_change_between_classification_and_delivery_discards_draft(
    tmp_path: Path,
) -> None:
    _, event, policy, _, generator = await setup(tmp_path / "race.sqlite")
    original = policy.current

    async def changing(scope: SourceScope) -> SourcePermission:
        view = await original(scope)
        if policy.calls >= 3:
            return replace(view, revision=2)
        return view

    policy.current = changing  # type: ignore[method-assign]
    result = await generator.prepare(event.event_id, SCOPE)
    assert result.draft is None and result.source_reason is SourceReason.POLICY_CHANGED


@pytest.mark.asyncio
async def test_cancellation_propagates_during_source_policy_read(tmp_path: Path) -> None:
    _, event, policy, _, generator = await setup(tmp_path / "cancel.sqlite")
    policy.block = True
    task = asyncio.create_task(generator.prepare(event.event_id, SCOPE))
    while not policy.calls:
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize("text", ["", "我喜歡" + "茶" * 2048, "我喜歡\u200b茶", "我喜歡\0茶"])
def test_bounds_and_invisible_controls_are_rejected(text: str) -> None:
    assert classify_source_text(text) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "updates",
    [
        {"subject_id": None},
        {"subject_id": "guest"},
        {"source": "synthetic.model"},
        {"source": "synthetic.tool"},
        {"session_id": "unknown"},
    ],
)
async def test_legacy_model_tool_guest_and_unbound_events_are_not_owner_candidates(
    tmp_path: Path,
    updates: dict[str, Any],
) -> None:
    _, event, _, _, generator = await setup(tmp_path / "source-kind.sqlite", **updates)
    result = await generator.prepare(event.event_id, SCOPE)
    assert result.draft is None and result.reason is CandidateReason.SOURCE_REJECTED


@pytest.mark.asyncio
async def test_source_ttl_caps_draft_lifetime(tmp_path: Path) -> None:
    _, event, _, _, generator = await setup(tmp_path / "ttl.sqlite", ttl_ms=5000)
    result = await generator.prepare(event.event_id, SCOPE)
    assert result.draft and result.draft.valid_until == NOW + timedelta(seconds=5)


@pytest.mark.asyncio
async def test_invalid_candidate_expiry_is_rejected_without_raw_content(tmp_path: Path) -> None:
    _, event, _, _, generator = await setup(tmp_path / "invalid.sqlite")
    result = await generator.prepare(event.event_id, SCOPE)
    assert result.draft
    with pytest.raises(ValueError, match="typed provenance and aware expiry"):
        replace(result.draft, valid_until=NOW.replace(tzinfo=None))


@pytest.mark.parametrize(
    "text",
    [
        "我喜歡password備註。",
        "我需要token資料。",
        "我喜歡secret備註。",
        "我需要ｔｏｋｅｎ資料。",
        "我喜歡PASSWORD備註。",
        "我喜歡api_key資料。",
    ],
)
def test_mixed_chinese_english_sensitive_markers_are_not_hidden_by_word_boundaries(
    text: str,
) -> None:
    assert classify_source_text(text) is None


@pytest.mark.asyncio
async def test_draft_lifetime_starts_at_final_source_validation(tmp_path: Path) -> None:
    _, event, policy, clock, generator = await setup(tmp_path / "time-change.sqlite")
    original = policy.current

    async def advancing(scope: SourceScope) -> SourcePermission:
        view = await original(scope)
        if policy.calls == 3:
            clock[0] = NOW + timedelta(days=2)
        return view

    policy.current = advancing  # type: ignore[method-assign]
    result = await generator.prepare(event.event_id, SCOPE)
    assert result.draft and result.draft.created_at == clock[0]
    assert result.draft.valid_until == clock[0] + timedelta(hours=24)
    assert (await generator.revalidate(result.draft)).draft == result.draft
