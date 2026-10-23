"""Real SQLite source races around a synthetic semantic selector, not quality scores."""

from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryService
from siro.core.memory_retrieval import HybridMemoryRetriever
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.memory_vectors import SQLiteMemoryVectors
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.embeddings import EmbeddingProfile, RetrievalUnavailable
from siro.ports.memory_relevance import RelevanceCandidate


class Embedder:
    profile = EmbeddingProfile("synthetic", "a" * 64, 32)

    async def embed(self, texts: tuple[str, ...], *, query: bool) -> tuple[tuple[float, ...], ...]:
        v = (0.45, math.sqrt(1 - 0.45**2)) if query else (1.0, 0.0)
        return tuple(v + (0.0,) * 30 for _ in texts)


class Selector:
    def __init__(self, selected: tuple[int, ...] = (0,)) -> None:
        self.selected = selected
        self.seen: list[tuple[RelevanceCandidate, ...]] = []

    async def select(
        self, query: str, candidates: tuple[RelevanceCandidate, ...]
    ) -> tuple[int, ...]:
        self.seen.append(candidates)
        return self.selected


def event(text: str, privacy: Privacy = Privacy.LOCAL_ONLY) -> UserTextEvent:
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
        payload=UserTextPayload(text=text, language="en"),
    )


async def setup(
    path: Path,
) -> tuple[SQLiteStore, SQLiteMemoryRepository, SQLiteMemoryVectors, Memory]:
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
    repo = SQLiteMemoryRepository(store)
    source = event("synthetic memory")
    memory = Memory(uuid4(), "siro", source.payload.text, (source.event_id,), source.occurred_at)
    await repo.add(memory, source)
    return store, repo, SQLiteMemoryVectors(store), memory


@pytest.mark.asyncio
async def test_broader_candidates_only_with_explicit_relevance_filter(tmp_path: Path) -> None:
    _, repo, cache, memory = await setup(tmp_path / "broader.sqlite")
    assert (
        await HybridMemoryRetriever(cache, Embedder()).recall(
            "siro", "query", [], route=Privacy.LOCAL_ONLY
        )
        == []
    )
    selector = Selector()
    service = MemoryService(
        repo, retriever=HybridMemoryRetriever(cache, Embedder(), relevance=selector)
    )
    assert await service.recall_context("siro", "query") == [memory]
    assert selector.seen[0][0].text == memory.text
    assert selector.seen[0][0].source_event_types == ("conversation.user_text.v1",)
    assert memory.text not in repr(selector.seen)
    with pytest.raises(ValueError, match="requires"):
        HybridMemoryRetriever(cache, Embedder(), candidate_similarity=0.3)


@pytest.mark.asyncio
async def test_reject_unrelated_does_not_fall_back_to_lexical(tmp_path: Path) -> None:
    _, _, cache, memory = await setup(tmp_path / "deny.sqlite")
    assert (
        await HybridMemoryRetriever(cache, Embedder(), relevance=Selector(())).recall(
            "siro", "query", [memory], route=Privacy.LOCAL_ONLY
        )
        == []
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["correct", "delete", "revoke", "privacy", "expiry", "envelope", "event_type"]
)
async def test_mutation_while_selecting_cannot_return_old_sources(
    tmp_path: Path, change: str
) -> None:
    store, repo, cache, memory = await setup(tmp_path / "race.sqlite")

    class Racing(Selector):
        async def select(
            self, query: str, candidates: tuple[RelevanceCandidate, ...]
        ) -> tuple[int, ...]:
            if change == "correct":
                await repo.correct(
                    memory.memory_id, "changed", event("changed"), reason="synthetic"
                )
            elif change == "delete":
                await repo.delete(
                    memory.memory_id, reason="synthetic", deleted_at=datetime.now(UTC)
                )
            elif change == "revoke":
                await repo.revoke_source(
                    memory.source_event_ids[0], reason="synthetic", now=datetime.now(UTC)
                )
            elif change == "privacy":
                await store.run_transaction(
                    lambda c: c.execute(
                        "UPDATE events SET envelope_json="
                        "json_set(envelope_json,'$.privacy','local_only')"
                    )
                )
            elif change == "expiry":
                await store.run_transaction(
                    lambda c: c.execute("UPDATE memories SET valid_to='2000-01-01T00:00:00+00:00'")
                )
            elif change == "event_type":
                await store.run_transaction(
                    lambda c: c.execute(
                        "UPDATE events SET envelope_json="
                        "json_set(envelope_json,'$.type','conversation.text_delta.v1')"
                    )
                )
            else:
                await store.run_transaction(
                    lambda c: c.execute(
                        "UPDATE events SET envelope_json="
                        "json_set(envelope_json,'$.payload.text','changed')"
                    )
                )
            return (0,)

    if change == "privacy":
        await store.run_transaction(
            lambda c: c.execute(
                "UPDATE events SET envelope_json="
                "json_set(envelope_json,'$.privacy','cloud_allowed')"
            )
        )
    with pytest.raises(RetrievalUnavailable, match="sources changed"):
        await HybridMemoryRetriever(cache, Embedder(), relevance=Racing()).recall(
            "siro",
            "query",
            [],
            route=Privacy.CLOUD_ALLOWED if change == "privacy" else Privacy.LOCAL_ONLY,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", [(True,), (-1,), (9,), (0, 0), ([],)])
async def test_invalid_filter_indices_rejected(tmp_path: Path, selected: Any) -> None:
    _, _, cache, _ = await setup(tmp_path / "indices.sqlite")
    with pytest.raises(RetrievalUnavailable, match="invalid relevance"):
        await HybridMemoryRetriever(cache, Embedder(), relevance=Selector(selected)).recall(
            "siro", "query", [], route=Privacy.LOCAL_ONLY
        )


@pytest.mark.asyncio
async def test_filter_cancellation_propagates_and_next_recall_can_run(tmp_path: Path) -> None:
    _, _, cache, _ = await setup(tmp_path / "cancel.sqlite")
    started = asyncio.Event()
    closed = asyncio.Event()

    class Slow(Selector):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        async def select(
            self, query: str, candidates: tuple[RelevanceCandidate, ...]
        ) -> tuple[int, ...]:
            self.calls += 1
            if self.calls > 1:
                return ()
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()
            raise AssertionError("unreachable")

    retriever = HybridMemoryRetriever(cache, Embedder(), relevance=Slow())
    task = asyncio.create_task(retriever.recall("siro", "query", [], route=Privacy.LOCAL_ONLY))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set() and not retriever._lock.locked()
    assert await retriever.recall("siro", "query", [], route=Privacy.LOCAL_ONLY) == []
