"""Bounded hybrid recall with source-bound persistent document embeddings."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from siro.contracts.events import Privacy
from siro.core.memory import Memory
from siro.ports.embeddings import EmbeddingProfile, LocalEmbedder, RetrievalUnavailable, normalized


@dataclass(frozen=True, slots=True)
class VectorDocument:
    memory: Memory
    source_hash: str
    vector: tuple[float, ...] | None = None


class VectorRepository(Protocol):
    async def documents(
        self,
        identity_id: str,
        person_id: str,
        route: Privacy,
        profile: EmbeddingProfile,
        cap: int,
    ) -> tuple[VectorDocument, ...]: ...

    async def save(
        self,
        documents: tuple[VectorDocument, ...],
        profile: EmbeddingProfile,
        route: Privacy,
    ) -> None: ...


class HybridMemoryRetriever:
    def __init__(
        self,
        repository: VectorRepository,
        embedder: LocalEmbedder,
        *,
        corpus_cap: int = 1000,
        timeout: float = 120,
        minimum_similarity: float = 0.5,
    ) -> None:
        if not 1 <= corpus_cap <= 1000 or not 0 < timeout <= 300:
            raise ValueError("retrieval bounds exceeded")
        if not 0 <= minimum_similarity <= 1:
            raise ValueError("invalid similarity threshold")
        self._repository = repository
        self._embedder = embedder
        self._cap = corpus_cap
        self._timeout = timeout
        self._minimum = minimum_similarity
        self._lock = asyncio.Lock()

    async def recall(
        self,
        identity_id: str,
        current: str,
        lexical: list[Memory],
        *,
        route: Privacy,
    ) -> list[Memory]:
        # A single index refresh owner per instance. Cancellation releases the lock.
        try:
            async with asyncio.timeout(self._timeout), self._lock:
                return await self._recall(identity_id, current, lexical, route)
        except TimeoutError:
            raise RetrievalUnavailable("hybrid retrieval timed out") from None

    async def _recall(
        self,
        identity_id: str,
        current: str,
        lexical: list[Memory],
        route: Privacy,
    ) -> list[Memory]:
        profile = self._embedder.profile
        documents = await self._repository.documents(
            identity_id, "owner", route, profile, self._cap
        )
        if not documents:
            return []
        missing = [d for d in documents if d.vector is None]
        for start in range(0, len(missing), 32):
            batch = missing[start : start + 32]
            current_documents = {
                d.memory.memory_id: d
                for d in await self._repository.documents(
                    identity_id, "owner", route, profile, self._cap
                )
            }
            if any(
                (preflight_doc := current_documents.get(d.memory.memory_id)) is None
                or preflight_doc.memory != d.memory
                or preflight_doc.source_hash != d.source_hash
                for d in batch
            ):
                raise RetrievalUnavailable("embedding sources changed before dispatch")
            vectors = await self._embedder.embed(tuple(d.memory.text for d in batch), query=False)
            if len(vectors) != len(batch):
                raise RetrievalUnavailable("embedding batch mismatch")
            updated = tuple(
                VectorDocument(d.memory, d.source_hash, normalized(v, profile.dimensions))
                for d, v in zip(batch, vectors, strict=True)
            )
            await self._repository.save(updated, profile, route)
        query_vectors = await self._embedder.embed((current,), query=True)
        if len(query_vectors) != 1:
            raise RetrievalUnavailable("embedding query mismatch")
        query = normalized(query_vectors[0], profile.dimensions)
        # Read again after inference: never return changed/revoked/expired source bytes.
        fresh = await self._repository.documents(identity_id, "owner", route, profile, self._cap)
        dense = sorted(
            (
                (sum(a * b for a, b in zip(query, d.vector, strict=True)), d)
                for d in fresh
                if d.vector is not None
            ),
            key=lambda pair: (-pair[0], str(pair[1].memory.memory_id)),
        )
        eligible = {d.memory.memory_id: d.memory for d in fresh}
        similarity = {d.memory.memory_id: score for score, d in dense}
        # Broad lexical overlaps must not bypass the dense relevance floor.
        lexical_ids = [
            m.memory_id
            for m in lexical
            if eligible.get(m.memory_id) == m and similarity.get(m.memory_id, -1) >= self._minimum
        ]
        dense_ids = [d.memory.memory_id for score, d in dense if score >= self._minimum][:20]
        scores: dict[UUID, float] = {}
        for ranking in (lexical_ids, dense_ids):
            for rank, memory_id in enumerate(dict.fromkeys(ranking), 1):
                scores[memory_id] = scores.get(memory_id, 0) + 1 / (60 + rank)
        ranked = sorted(scores, key=lambda k: (-scores[k], str(k)))
        return [eligible[k] for k in ranked[:5]]
