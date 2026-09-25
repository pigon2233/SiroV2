"""Versioned, source-scoped durable memory."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from uuid import UUID

from siro.contracts.events import Event
from siro.core.memory import Memory, MemoryKind, MemoryRevision, MemoryStatus, SemanticFact
from siro.persistence.sqlite import SQLiteStore


class SQLiteMemoryRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def add(self, memory: Memory, source_event: Event) -> None:
        def write(connection: sqlite3.Connection) -> None:
            self._add_memory(connection, memory, source_event)

        await self._store.run_transaction(write)

    async def add_fact(self, memory: Memory, source_event: Event, fact: SemanticFact) -> None:
        def write(connection: sqlite3.Connection) -> None:
            self._add_memory(connection, memory, source_event)
            connection.execute(
                "INSERT INTO semantic_facts"
                "(memory_id, subject, predicate, object_json, verification) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    str(fact.memory_id),
                    fact.subject,
                    fact.predicate,
                    json.dumps(fact.value, ensure_ascii=False),
                    fact.verification,
                ),
            )

        await self._store.run_transaction(write)

    async def facts(
        self, identity_id: str, subject: str, predicate: str, *, person_id: str = "owner"
    ) -> list[SemanticFact]:
        def read(connection: sqlite3.Connection) -> list[SemanticFact]:
            rows = connection.execute(
                "SELECT f.memory_id, f.subject, f.predicate, f.object_json, f.verification "
                "FROM semantic_facts f JOIN memories m ON m.memory_id = f.memory_id "
                "WHERE m.identity_id = ? AND m.person_id = ? AND m.status = 'committed' "
                "AND m.deleted_at IS NULL AND f.subject = ? AND f.predicate = ? "
                "ORDER BY m.valid_from DESC",
                (identity_id, person_id, subject, predicate),
            ).fetchall()
            return [
                SemanticFact(
                    UUID(str(row["memory_id"])),
                    str(row["subject"]),
                    str(row["predicate"]),
                    json.loads(str(row["object_json"])),
                    str(row["verification"]),
                )
                for row in rows
            ]

        return await self._store.run_transaction(read)

    async def search(
        self,
        identity_id: str,
        query: str,
        *,
        person_id: str = "owner",
        kinds: tuple[MemoryKind, ...] = (),
        as_of: datetime | None = None,
        source_event_id: UUID | None = None,
        limit: int = 5,
    ) -> list[Memory]:
        if not query.strip() or not 1 <= limit <= 100 or not identity_id or not person_id:
            return []

        def read(connection: sqlite3.Connection) -> list[Memory]:
            params: list[object] = [identity_id, person_id]
            where = [
                "m.identity_id = ?",
                "m.person_id = ?",
                "m.status = 'committed'",
                "m.deleted_at IS NULL",
            ]
            if kinds:
                where.append(f"m.kind IN ({','.join('?' for _ in kinds)})")
                params.extend(kinds)
            if as_of is not None:
                timestamp = as_of.isoformat()
                where.extend(["m.valid_from <= ?", "(m.valid_to IS NULL OR m.valid_to > ?)"])
                params.extend((timestamp, timestamp))
            if source_event_id is not None:
                where.append(
                    "EXISTS (SELECT 1 FROM memory_sources ms WHERE ms.memory_id = m.memory_id "
                    "AND ms.source_event_id = ?)"
                )
                params.append(str(source_event_id))
            rows = connection.execute(
                "SELECT m.* FROM memories m WHERE " + " AND ".join(where), params
            ).fetchall()
            tokens = tuple(dict.fromkeys(token.lower() for token in query.split() if token))
            phrase = query.strip().lower()
            fts_query = " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
            fts_rank: dict[str, float] = {}
            if fts_query:
                fts_rank = {
                    str(row["memory_id"]): float(row["rank"])
                    for row in connection.execute(
                        "SELECT memory_id, bm25(memory_fts) AS rank FROM memory_fts "
                        "WHERE memory_fts MATCH ? AND identity_id = ? AND person_id = ?",
                        (fts_query, identity_id, person_id),
                    )
                }

            def score(row: sqlite3.Row) -> tuple[int, int, float, str]:
                text = str(row["text"]).lower()
                rank = fts_rank.get(str(row["memory_id"]), 0.0)
                return (
                    int(phrase in text),
                    sum(token in text for token in tokens),
                    -rank,
                    str(row["valid_from"] or ""),
                )

            ranked = sorted(
                (row for row in rows if score(row)[1] == len(tokens)), key=score, reverse=True
            )
            return [self._to_memory(connection, row) for row in ranked[:limit]]

        return await self._store.run_transaction(read)

    async def correct(
        self, memory_id: UUID, text: str, source_event: Event, *, reason: str
    ) -> Memory:
        def write(connection: sqlite3.Connection) -> Memory:
            row = connection.execute(
                "SELECT * FROM memories WHERE memory_id = ? AND deleted_at IS NULL",
                (str(memory_id),),
            ).fetchone()
            if row is None:
                raise KeyError(memory_id)
            self._insert_event(connection, source_event)
            connection.execute(
                "INSERT OR IGNORE INTO memory_sources(memory_id, source_event_id) VALUES (?, ?)",
                (str(memory_id), str(source_event.event_id)),
            )
            revision = int(row["revision"]) + 1
            changed_at = source_event.occurred_at
            connection.execute(
                "UPDATE memories SET text = ?, revision = ?, valid_from = ? WHERE memory_id = ?",
                (text, revision, changed_at.isoformat(), str(memory_id)),
            )
            updated = connection.execute(
                "SELECT * FROM memories WHERE memory_id = ?", (str(memory_id),)
            ).fetchone()
            assert updated is not None
            memory = self._to_memory(connection, updated)
            self._insert_revision(connection, memory, reason=reason, changed_at=changed_at)
            connection.execute("DELETE FROM memory_fts WHERE memory_id = ?", (str(memory_id),))
            self._index(connection, memory)
            return memory

        return await self._store.run_transaction(write)

    async def delete(self, memory_id: UUID, *, reason: str, deleted_at: datetime) -> bool:
        def write(connection: sqlite3.Connection) -> bool:
            descendants = connection.execute(
                "WITH RECURSIVE descendants(memory_id) AS ("
                "SELECT child_memory_id FROM memory_derivations WHERE parent_memory_id = ? "
                "UNION SELECT d.child_memory_id FROM memory_derivations d "
                "JOIN descendants p ON d.parent_memory_id = p.memory_id) "
                "SELECT memory_id FROM descendants",
                (str(memory_id),),
            ).fetchall()
            ids = [str(memory_id), *(str(row["memory_id"]) for row in descendants)]
            row = connection.execute(
                "SELECT 1 FROM memories WHERE memory_id = ? AND deleted_at IS NULL",
                (str(memory_id),),
            ).fetchone()
            if row is None:
                return False
            for current_id in ids:
                current = connection.execute(
                    "SELECT * FROM memories WHERE memory_id = ? AND deleted_at IS NULL",
                    (current_id,),
                ).fetchone()
                if current is None:
                    continue
                revision = int(current["revision"]) + 1
                connection.execute(
                    "UPDATE memories SET status = 'deleted', deleted_at = ?, revision = ? "
                    "WHERE memory_id = ?",
                    (deleted_at.isoformat(), revision, current_id),
                )
                updated = connection.execute(
                    "SELECT * FROM memories WHERE memory_id = ?", (current_id,)
                ).fetchone()
                assert updated is not None
                memory = self._to_memory(connection, updated)
                self._insert_revision(
                    connection,
                    memory,
                    reason=reason if current_id == str(memory_id) else "source deleted",
                    changed_at=deleted_at,
                )
                connection.execute("DELETE FROM memory_fts WHERE memory_id = ?", (current_id,))
            return True

        return await self._store.run_transaction(write)

    async def revisions(self, memory_id: UUID) -> list[MemoryRevision]:
        def read(connection: sqlite3.Connection) -> list[MemoryRevision]:
            rows = connection.execute(
                "SELECT revision, text, status, reason, changed_at, source_ids_json "
                "FROM memory_revisions WHERE memory_id = ? ORDER BY revision",
                (str(memory_id),),
            ).fetchall()
            return [
                MemoryRevision(
                    memory_id=memory_id,
                    revision=int(row["revision"]),
                    text=str(row["text"]),
                    status=MemoryStatus(str(row["status"])),
                    reason=str(row["reason"]),
                    changed_at=datetime.fromisoformat(str(row["changed_at"])),
                    source_event_ids=tuple(
                        UUID(value) for value in json.loads(row["source_ids_json"])
                    ),
                )
                for row in rows
            ]

        return await self._store.run_transaction(read)

    async def list_active(
        self, identity_id: str, *, person_id: str = "owner", limit: int = 100
    ) -> list[Memory]:
        if not 1 <= limit <= 1000:
            raise ValueError("memory browse limit must be between 1 and 1000")

        def read(connection: sqlite3.Connection) -> list[Memory]:
            rows = connection.execute(
                "SELECT * FROM memories WHERE identity_id = ? AND person_id = ? "
                "AND status = 'committed' AND deleted_at IS NULL "
                "ORDER BY valid_from DESC LIMIT ?",
                (identity_id, person_id, limit),
            ).fetchall()
            return [self._to_memory(connection, row) for row in rows]

        return await self._store.run_transaction(read)

    async def rebuild_index(self) -> None:
        def write(connection: sqlite3.Connection) -> None:
            connection.execute("DELETE FROM memory_fts")
            connection.execute(
                "INSERT INTO memory_fts(memory_id, identity_id, person_id, text) "
                "SELECT memory_id, identity_id, person_id, text FROM memories "
                "WHERE status = 'committed' AND deleted_at IS NULL"
            )

        await self._store.run_transaction(write)

    @staticmethod
    def _insert_event(connection: sqlite3.Connection, event: Event) -> None:
        connection.execute(
            "INSERT OR IGNORE INTO events(event_id, type, envelope_json, received_at, trace_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                str(event.event_id),
                event.type,
                event.model_dump_json(),
                event.received_at.isoformat(),
                event.trace_id,
            ),
        )

    def _add_memory(
        self, connection: sqlite3.Connection, memory: Memory, source_event: Event
    ) -> None:
        self._insert_event(connection, source_event)
        connection.execute(
            "INSERT INTO memories(memory_id, identity_id, kind, person_id, text, status, "
            "confidence, valid_from, valid_to, revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(memory.memory_id),
                memory.identity_id,
                memory.kind,
                memory.person_id,
                memory.text,
                memory.status,
                memory.confidence,
                memory.created_at.isoformat(),
                memory.valid_to.isoformat() if memory.valid_to else None,
                memory.revision,
            ),
        )
        for source_id in memory.source_event_ids:
            connection.execute(
                "INSERT INTO memory_sources(memory_id, source_event_id) VALUES (?, ?)",
                (str(memory.memory_id), str(source_id)),
            )
        self._insert_revision(connection, memory, reason="created", changed_at=memory.created_at)
        if memory.status is MemoryStatus.COMMITTED:
            self._index(connection, memory)

    @staticmethod
    def _index(connection: sqlite3.Connection, memory: Memory) -> None:
        connection.execute(
            "INSERT INTO memory_fts(memory_id, identity_id, person_id, text) VALUES (?, ?, ?, ?)",
            (str(memory.memory_id), memory.identity_id, memory.person_id, memory.text),
        )

    @staticmethod
    def _source_ids(connection: sqlite3.Connection, memory_id: str) -> tuple[UUID, ...]:
        return tuple(
            UUID(str(row["source_event_id"]))
            for row in connection.execute(
                "SELECT source_event_id FROM memory_sources WHERE memory_id = ? "
                "ORDER BY source_event_id",
                (memory_id,),
            )
        )

    def _to_memory(self, connection: sqlite3.Connection, row: sqlite3.Row) -> Memory:
        memory_id = str(row["memory_id"])
        return Memory(
            memory_id=UUID(memory_id),
            identity_id=str(row["identity_id"]),
            text=str(row["text"]),
            source_event_ids=self._source_ids(connection, memory_id),
            created_at=datetime.fromisoformat(str(row["valid_from"])),
            kind=MemoryKind(str(row["kind"])),
            person_id=str(row["person_id"]),
            confidence=float(row["confidence"]),
            valid_to=datetime.fromisoformat(str(row["valid_to"])) if row["valid_to"] else None,
            status=MemoryStatus(str(row["status"])),
            revision=int(row["revision"]),
        )

    def _insert_revision(
        self, connection: sqlite3.Connection, memory: Memory, *, reason: str, changed_at: datetime
    ) -> None:
        connection.execute(
            "INSERT INTO memory_revisions(memory_id, revision, kind, person_id, text, status, "
            "confidence, valid_from, valid_to, source_ids_json, reason, changed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(memory.memory_id),
                memory.revision,
                memory.kind,
                memory.person_id,
                memory.text,
                memory.status,
                memory.confidence,
                memory.created_at.isoformat(),
                memory.valid_to.isoformat() if memory.valid_to else None,
                json.dumps([str(value) for value in memory.source_event_ids]),
                reason,
                changed_at.astimezone(UTC).isoformat(),
            ),
        )
