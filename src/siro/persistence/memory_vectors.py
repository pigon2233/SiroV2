"""Version-bound local vector cache in the authoritative Memory SQLite database."""

from __future__ import annotations

import asyncio
import sqlite3
import struct
from contextlib import suppress
from datetime import UTC, datetime
from typing import TypeVar

from siro.contracts.events import Privacy
from siro.core.memory_retrieval import VectorDocument
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.ports.embeddings import EmbeddingProfile, RetrievalUnavailable, normalized
from siro.ports.persistence import Transaction

T = TypeVar("T")


class SQLiteMemoryVectors:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store
        self._memory = SQLiteMemoryRepository(store)

    async def documents(
        self,
        identity_id: str,
        person_id: str,
        route: Privacy,
        profile: EmbeddingProfile,
        cap: int,
    ) -> tuple[VectorDocument, ...]:
        if not identity_id or not person_id or not 1 <= cap <= 1000:
            raise ValueError("invalid vector corpus scope or bound")

        def read(c: sqlite3.Connection) -> tuple[VectorDocument, ...]:
            now = datetime.now(UTC)
            rows = c.execute(
                "SELECT memory_id FROM memories WHERE identity_id=? AND person_id=? "
                "AND status='committed' AND deleted_at IS NULL ORDER BY memory_id LIMIT ?",
                (identity_id, person_id, cap + 1),
            ).fetchall()
            # Explicit failure beats silently omitting older/less recently used memories.
            if len(rows) > cap:
                raise RetrievalUnavailable("vector corpus capacity exceeded")
            result = []
            for item in rows:
                try:
                    row = self._memory._parent(
                        c,
                        item["memory_id"],
                        identity_id,
                        person_id,
                        now,
                        route,
                    )
                except ValueError:
                    continue
                source_hash = self._memory._source_hash(c, row)
                cached = c.execute(
                    "SELECT vector,dimensions FROM memory_vectors WHERE memory_id=? "
                    "AND profile_key=? AND revision=? AND source_hash=?",
                    (row["memory_id"], profile.key, row["revision"], source_hash),
                ).fetchone()
                vector = None
                if cached is not None and cached["dimensions"] == profile.dimensions:
                    with suppress(struct.error, RetrievalUnavailable):
                        vector = normalized(
                            struct.unpack(f"<{profile.dimensions}f", cached["vector"]),
                            profile.dimensions,
                        )
                result.append(VectorDocument(self._memory._to_memory(c, row), source_hash, vector))
            return tuple(result)

        return await self._transaction(read)

    async def save(
        self,
        documents: tuple[VectorDocument, ...],
        profile: EmbeddingProfile,
        route: Privacy,
    ) -> None:
        if not 1 <= len(documents) <= 32:
            raise ValueError("vector write batch bounds exceeded")

        def write(c: sqlite3.Connection) -> None:
            for doc in documents:
                memory = doc.memory
                try:
                    row = self._memory._parent(
                        c,
                        str(memory.memory_id),
                        memory.identity_id,
                        memory.person_id,
                        datetime.now(UTC),
                        route,
                    )
                except ValueError:
                    raise RetrievalUnavailable("embedding source became unavailable") from None
                if (
                    row["status"] != "committed"
                    or self._memory._to_memory(c, row) != memory
                    or self._memory._source_hash(c, row) != doc.source_hash
                    or doc.vector is None
                ):
                    raise RetrievalUnavailable("embedding source changed")
                vector = normalized(doc.vector, profile.dimensions)
                c.execute(
                    "INSERT INTO memory_vectors VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT(memory_id,profile_key) DO UPDATE SET revision=excluded.revision, "
                    "source_hash=excluded.source_hash,dimensions=excluded.dimensions,vector=excluded.vector",
                    (
                        str(memory.memory_id),
                        profile.key,
                        memory.revision,
                        doc.source_hash,
                        profile.dimensions,
                        struct.pack(f"<{profile.dimensions}f", *vector),
                    ),
                )

        await self._transaction(write)

    async def _transaction(self, work: Transaction[T]) -> T:
        # SQLite runs in a worker thread. Join terminal transaction on cancellation so the
        # store's one-writer lock is not released while its transaction still runs.
        task = asyncio.create_task(self._store.run_transaction(work))
        cancelled = False
        while True:
            try:
                await asyncio.shield(task)
                break
            except asyncio.CancelledError:
                cancelled = True
                if task.done():
                    break
            except Exception:
                if not cancelled:
                    raise
                break
        if cancelled:
            if not task.cancelled():
                task.exception()  # Observe a failure without replacing caller cancellation.
            raise asyncio.CancelledError
        return task.result()
