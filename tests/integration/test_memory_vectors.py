"""Synthetic lifecycle/authorization tests; semantic quality measured separately."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.companion import CompanionCore
from siro.core.context import END, START, read_context_snapshot, render_context
from siro.core.conversation import ConversationEngine, TurnState
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryService, MemoryStatus
from siro.core.memory_retrieval import HybridMemoryRetriever
from siro.persistence.conversation import SQLiteConversationRepository
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.memory_vectors import SQLiteMemoryVectors
from siro.persistence.sqlite import SQLiteStore, apply_migrations, load_migrations
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.embeddings import EmbeddingProfile, RetrievalUnavailable
from siro.ports.models import CancellationToken, ModelChunk, ModelMessage, ModelRequest

PROFILE = EmbeddingProfile("synthetic-embedding", "a" * 64, 32)
ROUTE = Privacy.LOCAL_ONLY


class FakeEmbedder:
    profile = PROFILE

    def __init__(self) -> None:
        self.documents: list[str] = []
        self.queries: list[str] = []

    async def embed(self, texts: tuple[str, ...], *, query: bool) -> tuple[tuple[float, ...], ...]:
        (self.queries if query else self.documents).extend(texts)
        return tuple((1.0,) + (0.0,) * 31 for _ in texts)


def source(text: str, privacy: Privacy = ROUTE) -> UserTextEvent:
    now = datetime.now(UTC)
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="synthetic",
        occurred_at=now,
        received_at=now,
        trace_id="synthetic",
        session_id="synthetic",
        turn_id=str(uuid4()),
        sequence=1,
        priority=Priority.INTERACTIVE,
        privacy=privacy,
        payload=UserTextPayload(text=text, language="zh-TW"),
    )


async def setup(path: Path) -> tuple[SQLiteStore, SQLiteMemoryRepository, SQLiteMemoryVectors]:
    store = SQLiteStore(path)
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="synthetic",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        now=datetime.now(UTC),
    )
    return store, SQLiteMemoryRepository(store), SQLiteMemoryVectors(store)


async def add(repo: SQLiteMemoryRepository, text: str, **changes: object) -> Memory:
    event = source(text)
    memory = Memory(uuid4(), "siro", text, (event.event_id,), event.occurred_at)
    memory = replace(memory, **changes)  # type: ignore[arg-type]
    await repo.add(memory, event)
    return memory


async def count(store: SQLiteStore) -> int:
    return await store.run_transaction(
        lambda c: int(c.execute("SELECT count(*) FROM memory_vectors").fetchone()[0])
    )


@pytest.mark.asyncio
async def test_cache_survives_restart_and_model_profile_isolated(tmp_path: Path) -> None:
    store, repo, cache = await setup(tmp_path / "cache.sqlite")
    memory = await add(repo, "合成記憶")
    embedder = FakeEmbedder()
    retriever = HybridMemoryRetriever(cache, embedder)
    service = MemoryService(repo, retriever=retriever)
    assert await service.recall_context("siro", "完全不同的問題") == [memory]
    assert embedder.documents == [memory.text]
    second = FakeEmbedder()
    restarted = SQLiteMemoryVectors(SQLiteStore(store.path))
    assert await HybridMemoryRetriever(restarted, second).recall(
        "siro", "問題", [], route=ROUTE
    ) == [memory]
    assert second.documents == [] and second.queries == ["問題"]
    assert await count(store) == 1
    second.profile = replace(PROFILE, digest="b" * 64)
    await HybridMemoryRetriever(restarted, second).recall("siro", "問題", [], route=ROUTE)
    assert second.documents == [memory.text] and await count(store) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["correct", "delete", "revoke"])
async def test_atomic_invalidation_root_and_descendant(tmp_path: Path, operation: str) -> None:
    store, repo, cache = await setup(tmp_path / "invalidate.sqlite")
    parent = await add(repo, "原始")
    snapshot = await repo.capture_sources(
        "siro",
        "owner",
        (parent.memory_id,),
        now=datetime.now(UTC),
        generator_version="test",
        policy_revision=1,
    )
    child = replace(parent, memory_id=uuid4(), text="衍生", created_at=datetime.now(UTC))
    await repo.add_derived(child, snapshot, now=datetime.now(UTC), policy_revision=1)
    await HybridMemoryRetriever(cache, FakeEmbedder()).recall("siro", "問題", [], route=ROUTE)
    assert await count(store) == 2
    if operation == "correct":
        await repo.correct(parent.memory_id, "更正", source("更正"), reason="synthetic")
    elif operation == "delete":
        await repo.delete(parent.memory_id, reason="synthetic", deleted_at=datetime.now(UTC))
    else:
        await repo.revoke_source(
            parent.source_event_ids[0], reason="synthetic", now=datetime.now(UTC)
        )
    assert await count(store) == 0
    docs = await cache.documents("siro", "owner", ROUTE, PROFILE, 100)
    assert [d.memory.text for d in docs] == (["更正"] if operation == "correct" else [])


@pytest.mark.asyncio
async def test_scope_candidate_expiry_future_and_privacy_before_embedding(tmp_path: Path) -> None:
    store, repo, cache = await setup(tmp_path / "filters.sqlite")
    await add(repo, "local")
    await add(repo, "other-person", person_id="guest")
    await add(repo, "candidate", status=MemoryStatus.CANDIDATE)
    await add(repo, "expired", valid_to=datetime.now(UTC) - timedelta(seconds=1))
    await add(repo, "future", created_at=datetime.now(UTC) + timedelta(days=1))
    event = source("cloud", Privacy.CLOUD_ALLOWED)
    cloud = Memory(uuid4(), "siro", "cloud", (event.event_id,), event.occurred_at)
    await repo.add(cloud, event)
    embedder = FakeEmbedder()
    found = await HybridMemoryRetriever(cache, embedder).recall(
        "siro", "問題", [], route=Privacy.CLOUD_ALLOWED
    )
    assert found == [cloud] and embedder.documents == ["cloud"]
    assert await cache.documents("other-identity", "owner", ROUTE, PROFILE, 100) == ()
    assert await count(store) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["correct", "revoke", "source-envelope"])
async def test_source_change_during_embedding_cannot_be_cached_or_returned(
    tmp_path: Path, mutation: str
) -> None:
    store, repo, cache = await setup(tmp_path / "race.sqlite")
    memory = await add(repo, "synthetic")

    class Racing(FakeEmbedder):
        async def embed(
            self, texts: tuple[str, ...], *, query: bool
        ) -> tuple[tuple[float, ...], ...]:
            if not query:
                if mutation == "correct":
                    await repo.correct(
                        memory.memory_id, "changed", source("changed"), reason="synthetic"
                    )
                elif mutation == "revoke":
                    await repo.revoke_source(
                        memory.source_event_ids[0], reason="synthetic", now=datetime.now(UTC)
                    )
                else:
                    await store.run_transaction(
                        lambda c: c.execute(
                            "UPDATE events SET envelope_json="
                            "json_set(envelope_json,'$.payload.text','changed')"
                        )
                    )
            return await super().embed(texts, query=query)

    with pytest.raises(RetrievalUnavailable):
        await HybridMemoryRetriever(cache, Racing()).recall("siro", "問題", [], route=ROUTE)
    assert await count(store) == 0


@pytest.mark.asyncio
async def test_cached_source_revoked_during_query_not_returned(tmp_path: Path) -> None:
    store, repo, cache = await setup(tmp_path / "query-race.sqlite")
    memory = await add(repo, "synthetic")
    await HybridMemoryRetriever(cache, FakeEmbedder()).recall("siro", "問題", [], route=ROUTE)

    class Racing(FakeEmbedder):
        async def embed(
            self, texts: tuple[str, ...], *, query: bool
        ) -> tuple[tuple[float, ...], ...]:
            if query:
                await repo.revoke_source(
                    memory.source_event_ids[0], reason="synthetic", now=datetime.now(UTC)
                )
            return await super().embed(texts, query=query)

    assert (
        await HybridMemoryRetriever(cache, Racing()).recall("siro", "問題", [], route=ROUTE) == []
    )
    assert await count(store) == 0


@pytest.mark.asyncio
async def test_corrupt_cache_rebuilt_and_corpus_cap_explicit(tmp_path: Path) -> None:
    store, repo, cache = await setup(tmp_path / "bounds.sqlite")
    await add(repo, "one")
    await HybridMemoryRetriever(cache, FakeEmbedder()).recall("siro", "問題", [], route=ROUTE)
    await store.run_transaction(lambda c: c.execute("UPDATE memory_vectors SET vector=x'00'"))
    embedder = FakeEmbedder()
    await HybridMemoryRetriever(cache, embedder).recall("siro", "問題", [], route=ROUTE)
    assert embedder.documents == ["one"]
    await add(repo, "two")
    with pytest.raises(RetrievalUnavailable, match="capacity"):
        await HybridMemoryRetriever(cache, embedder, corpus_cap=1).recall(
            "siro", "問題", [], route=ROUTE
        )


@pytest.mark.asyncio
async def test_cache_writer_joined_on_repeated_cancellation(tmp_path: Path) -> None:
    store, repo, cache = await setup(tmp_path / "cancel.sqlite")
    await add(repo, "synthetic")
    doc = (await cache.documents("siro", "owner", ROUTE, PROFILE, 100))[0]
    started, release = Event(), Event()
    original = store._run_transaction_sync

    def blocked(work):  # type: ignore[no-untyped-def]
        started.set()
        assert release.wait(5)
        return original(work)

    store._run_transaction_sync = blocked  # type: ignore[method-assign]
    task = asyncio.create_task(cache.save((replace(doc, vector=(1.0,) * 32),), PROFILE, ROUTE))
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done() and store._writer_lock.locked()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    store._run_transaction_sync = original  # type: ignore[method-assign]
    assert await count(store) == 1 and not store._writer_lock.locked()


def test_schema17_to18_preserves_checksums_and_failed_upgrade_rolls_back(tmp_path: Path) -> None:
    migrations = load_migrations()
    with sqlite3.connect(tmp_path / "schema.sqlite") as c:
        apply_migrations(c, migrations[:17])
        old = c.execute("SELECT * FROM schema_migrations").fetchall()
        broken = replace(migrations[17], sql=migrations[17].sql + "; INVALID SQL")
        with pytest.raises(sqlite3.OperationalError):
            apply_migrations(c, (*migrations[:17], broken))
        assert c.execute("SELECT * FROM schema_migrations").fetchall() == old
        assert (
            c.execute("SELECT name FROM sqlite_master WHERE name='memory_vectors'").fetchall() == []
        )
        apply_migrations(c, migrations)
        apply_migrations(c, migrations)
        assert c.execute("SELECT * FROM schema_migrations WHERE version<=17").fetchall() == old
        assert c.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == len(migrations)


class Capture:
    name = "synthetic-only"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        yield ModelChunk("text", "synthetic")
        yield ModelChunk("finished")


@pytest.mark.asyncio
@pytest.mark.parametrize("budget", [0, 2000, 3000, 8192])
async def test_actual_core_memory_packet_budget_preserves_user_and_native_dialogue(
    tmp_path: Path, budget: int
) -> None:
    store, repo, _ = await setup(tmp_path / "budget.sqlite")
    service = MemoryService(repo)
    for index in range(5):
        await add(repo, f"synthetic record {index}: " + "這是合成的完整來源內容。" * 30)
    model = Capture()
    core = CompanionCore(
        SQLiteIdentityRepository(store),
        service,
        ConversationEngine(model, SQLiteConversationRepository(store)),
        memory_context_bytes=budget,
    )
    history: list[ModelMessage] = []
    recent = (
        ModelMessage("user", "完整先前原文" * 300),
        ModelMessage("assistant", "完整助理原文" * 300),
    )
    current = "synthetic 我目前的問題原文不可被截斷" * 30
    result = await core.respond(
        "synthetic", "siro", current, message_history=history, recent_messages=recent
    )
    assert result.state is TurnState.COMPLETED
    assert history[3] == ModelMessage("user", current)
    assert history[1:3] == list(recent)
    prompt = model.requests[0].messages[0].content
    packet = START + prompt.split(START, 1)[1].split(END, 1)[0] + END
    empty = render_context("synthetic", "siro", [], None, dialogue_messages=recent)
    assert len(packet.encode()) - len(empty.encode()) <= budget
    data = json.loads(packet[len(START) : -len(END)])
    assert len(data["memories"]) == {0: 0, 2000: 0, 3000: 1, 8192: 3}[budget]
    snapshot = read_context_snapshot(prompt, "synthetic", "siro")
    if snapshot:
        assert await service.context_sources_current(snapshot)
        for item in data["memories"]:
            assert item["text"] in [m.text for m in await service.browse("siro")]


@pytest.mark.asyncio
async def test_low_similarity_is_not_recalled_and_distinct_conflicts_not_deduplicated(
    tmp_path: Path,
) -> None:
    _, repo, cache = await setup(tmp_path / "similarity.sqlite")
    left = await add(repo, "我喜歡茶")
    right = await add(repo, "我不喜歡茶")
    found = await HybridMemoryRetriever(cache, FakeEmbedder()).recall(
        "siro", "問題", [], route=ROUTE
    )
    assert {m.memory_id for m in found} == {left.memory_id, right.memory_id}

    class Orthogonal(FakeEmbedder):
        async def embed(
            self, texts: tuple[str, ...], *, query: bool
        ) -> tuple[tuple[float, ...], ...]:
            return ((0.0, 1.0) + (0.0,) * 30,) if query else await super().embed(texts, query=query)

    # Dense-only matches below the floor are dropped; lexical hits are kept.
    assert await HybridMemoryRetriever(cache, Orthogonal()).recall(
        "siro", "unrelated", [], route=ROUTE
    ) == []
    kept = await HybridMemoryRetriever(cache, Orthogonal()).recall(
        "siro", "unrelated", [left, right], route=ROUTE
    )
    assert {m.memory_id for m in kept} == {left.memory_id, right.memory_id}


@pytest.mark.asyncio
async def test_embedder_unavailable_keeps_lexical_hits(tmp_path: Path) -> None:
    from siro.ports.embeddings import RetrievalUnavailable

    _, repo, cache = await setup(tmp_path / "degrade.sqlite")
    hit = await add(repo, "我喜歡茶")

    class Down(FakeEmbedder):
        async def embed(self, texts, *, query):  # type: ignore[no-untyped-def]
            raise RetrievalUnavailable("down")

    found = await HybridMemoryRetriever(cache, Down()).recall(
        "siro", "茶", [hit], route=ROUTE
    )
    assert [m.memory_id for m in found] == [hit.memory_id]


@pytest.mark.asyncio
async def test_steady_state_recall_reads_corpus_at_most_twice(tmp_path: Path) -> None:
    _, repo, cache = await setup(tmp_path / "reads.sqlite")
    hit = await add(repo, "我喜歡茶")
    retriever = HybridMemoryRetriever(cache, FakeEmbedder())
    await retriever.recall("siro", "茶", [hit], route=ROUTE)  # warm vectors
    calls = 0
    original = cache.documents

    async def counting(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return await original(*args, **kwargs)

    cache.documents = counting  # type: ignore[method-assign]
    await retriever.recall("siro", "茶", [hit], route=ROUTE)
    assert calls <= 2


def test_release_manifest_max17_refuses_schema18(tmp_path: Path) -> None:
    from siro.core.releases import ReleaseManager, ReleaseManifest

    manager = ReleaseManager(tmp_path / "release", bytes(range(32)), current_schema=18)
    manifest = ReleaseManifest(
        version="0.0.1",
        source_sha256="0" * 64,
        signature="0" * 64,
        min_schema=1,
        max_schema=17,
        signing_format="siro-release-manifest-v2",
    )
    assert not manager._compatible(manifest)


@pytest.mark.asyncio
async def test_embedding_timeout_degrades_to_lexical_hits(tmp_path: Path) -> None:
    _, repo, cache = await setup(tmp_path / "timeout.sqlite")
    memory = await add(repo, "synthetic")

    class Slow(FakeEmbedder):
        async def embed(
            self, texts: tuple[str, ...], *, query: bool
        ) -> tuple[tuple[float, ...], ...]:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    found = await HybridMemoryRetriever(cache, Slow(), timeout=0.01).recall(
        "siro", "synthetic", [memory], route=ROUTE
    )
    assert [m.memory_id for m in found] == [memory.memory_id]


@pytest.mark.asyncio
async def test_followup_embedding_gets_bounded_user_hints_only_when_needed(tmp_path: Path) -> None:
    _, repo, cache = await setup(tmp_path / "hints.sqlite")
    await add(repo, "合成筆電充電器")
    embedder = FakeEmbedder()
    service = MemoryService(repo, retriever=HybridMemoryRetriever(cache, embedder))
    previous = "筆電充電器" + "合成" * 1000
    await service.recall_context("siro", "那繼續", recent_users=(previous,))
    assert "Recent user context" in embedder.queries[-1]
    assert previous[:512] in embedder.queries[-1] and previous not in embedder.queries[-1]
    await service.recall_context("siro", "我現在想吃什麼", recent_users=(previous,))
    assert embedder.queries[-1] == "我現在想吃什麼"
