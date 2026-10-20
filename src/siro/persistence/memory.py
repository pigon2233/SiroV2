"""Versioned, source-scoped durable memory."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from uuid import UUID

from siro.contracts.events import Event, Privacy
from siro.core.memory import (
    Memory,
    MemoryDerivationSnapshot,
    MemoryKind,
    MemoryRevision,
    MemorySourceBinding,
    MemoryStatus,
    SemanticFact,
)
from siro.persistence.sqlite import SQLiteStore


class SQLiteMemoryRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def capture_sources(
        self,
        identity_id: str,
        person_id: str,
        parent_ids: tuple[UUID, ...],
        *,
        now: datetime,
        generator_version: str,
        policy_revision: int,
        route_privacy: Privacy = Privacy.LOCAL_ONLY,
        expected_memories: tuple[Memory, ...] | None = None,
    ) -> MemoryDerivationSnapshot:
        if not 1 <= len(parent_ids) <= 32 or len(set(parent_ids)) != len(parent_ids):
            raise ValueError("source parent bounds exceeded")
        if now.utcoffset() is None:
            raise ValueError("source time must be aware")

        def read(connection: sqlite3.Connection) -> MemoryDerivationSnapshot:
            expected = {item.memory_id: item for item in expected_memories or ()}
            if expected_memories is not None and set(expected) != set(parent_ids):
                raise ValueError("source selection mismatch")
            parents = []
            for memory_id in parent_ids:
                row = self._parent(
                    connection, str(memory_id), identity_id, person_id, now, route_privacy
                )
                if expected and self._to_memory(connection, row) != expected[memory_id]:
                    raise ValueError("source changed while selecting context")
                parents.append(
                    MemorySourceBinding(
                        memory_id,
                        int(row["revision"]),
                        self._source_hash(connection, row),
                        self._source_ids(connection, str(memory_id)),
                    )
                )
            return MemoryDerivationSnapshot(
                identity_id,
                person_id,
                tuple(parents),
                now,
                generator_version,
                policy_revision,
                route_privacy,
            )

        return await self._store.run_transaction(read)

    async def sources_current(self, snapshot: MemoryDerivationSnapshot, *, now: datetime) -> bool:
        def read(connection: sqlite3.Connection) -> bool:
            try:
                for binding in snapshot.parents:
                    row = self._parent(
                        connection,
                        str(binding.memory_id),
                        snapshot.identity_id,
                        snapshot.person_id,
                        now,
                        snapshot.route_privacy,
                    )
                    if (
                        row["revision"] != binding.revision
                        or self._source_hash(connection, row) != binding.source_hash
                        or self._source_ids(connection, str(binding.memory_id))
                        != binding.source_event_ids
                    ):
                        return False
                return True
            except ValueError:
                return False

        return await self._store.run_transaction(read)

    async def add_derived(
        self,
        memory: Memory,
        snapshot: MemoryDerivationSnapshot,
        *,
        now: datetime,
        policy_revision: int,
    ) -> None:
        if (
            now.utcoffset() is None
            or now < snapshot.captured_at
            or policy_revision != snapshot.policy_revision
        ):
            raise ValueError("source snapshot policy or time changed")
        if (memory.identity_id, memory.person_id) != (snapshot.identity_id, snapshot.person_id):
            raise ValueError("source scope mismatch")
        expected = {event for parent in snapshot.parents for event in parent.source_event_ids}
        if set(memory.source_event_ids) != expected or len(memory.source_event_ids) != len(
            expected
        ):
            raise ValueError("source event set mismatch")
        if memory.memory_id in {parent.memory_id for parent in snapshot.parents}:
            raise ValueError("source cycle")
        if memory.revision != 1 or memory.status not in (
            MemoryStatus.CANDIDATE,
            MemoryStatus.COMMITTED,
        ):
            raise ValueError("derived memory must be new candidate or committed data")
        if memory.kind is MemoryKind.WORKING or memory.created_at.utcoffset() is None:
            raise ValueError("derived memory must be durable with aware time")
        if not snapshot.captured_at <= memory.created_at <= now:
            raise ValueError("derived memory time outside source generation interval")

        def write(connection: sqlite3.Connection) -> None:
            for parent in snapshot.parents:
                row = self._parent(
                    connection,
                    str(parent.memory_id),
                    memory.identity_id,
                    memory.person_id,
                    now,
                    snapshot.route_privacy,
                )
                if (
                    int(row["revision"]) != parent.revision
                    or self._source_hash(connection, row) != parent.source_hash
                ):
                    raise ValueError("source changed after capture")
                if self._source_ids(connection, str(parent.memory_id)) != parent.source_event_ids:
                    raise ValueError("source event binding changed")
                if not self._lineage_valid(
                    connection, row, now, snapshot.route_privacy, frozenset({str(memory.memory_id)})
                ):
                    raise ValueError("source lineage exceeds derived depth bound")
                if memory.status is MemoryStatus.COMMITTED and row["status"] != "committed":
                    raise ValueError("source candidate cannot authorize committed memory")
                if row["valid_to"]:
                    expiry = datetime.fromisoformat(row["valid_to"])
                    if memory.valid_to is None or memory.valid_to > expiry:
                        raise ValueError("derived expiry exceeds source validity")
            self._add_memory(connection, memory, None)
            for parent in snapshot.parents:
                connection.execute(
                    "INSERT INTO memory_derivations("
                    "parent_memory_id,child_memory_id,revision,source_hash) "
                    "VALUES(?,?,?,?)",
                    (
                        str(parent.memory_id),
                        str(memory.memory_id),
                        parent.revision,
                        parent.source_hash,
                    ),
                )
            connection.execute(
                "INSERT INTO memory_derivation_metadata("
                "child_memory_id,generator_version,policy_revision,"
                "route_privacy,captured_at) VALUES(?,?,?,?,?)",
                (
                    str(memory.memory_id),
                    snapshot.generator_version,
                    snapshot.policy_revision,
                    snapshot.route_privacy,
                    snapshot.captured_at.isoformat(),
                ),
            )

        await self._store.run_transaction(write)

    @staticmethod
    def _source_hash(connection: sqlite3.Connection, row: sqlite3.Row) -> str:
        events = connection.execute(
            "SELECT e.event_id,e.envelope_json FROM memory_sources s JOIN events e "
            "ON e.event_id=s.source_event_id WHERE s.memory_id=? ORDER BY e.event_id",
            (row["memory_id"],),
        ).fetchall()
        payload = [dict(row), [tuple(event) for event in events]]
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    def _lineage_valid(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        now: datetime,
        route: Privacy = Privacy.LOCAL_ONLY,
        seen: frozenset[str] = frozenset(),
    ) -> bool:
        memory_id = str(row["memory_id"])
        if memory_id in seen or len(seen) >= 32:
            return False
        if row["deleted_at"] is not None or row["status"] not in ("candidate", "committed"):
            return False
        if datetime.fromisoformat(row["valid_from"]) > now:
            return False
        if row["valid_to"] and datetime.fromisoformat(row["valid_to"]) <= now:
            return False
        sources = connection.execute(
            "SELECT e.envelope_json,r.source_event_id AS revoked FROM memory_sources s "
            "LEFT JOIN events e ON e.event_id=s.source_event_id "
            "LEFT JOIN memory_source_revocations r "
            "ON r.source_event_id=s.source_event_id WHERE s.memory_id=?",
            (memory_id,),
        ).fetchall()
        if not sources:
            return False
        for source in sources:
            if source["revoked"] is not None or source["envelope_json"] is None:
                return False
            privacy = json.loads(source["envelope_json"]).get("privacy")
            if route is Privacy.CLOUD_ALLOWED and privacy != "cloud_allowed":
                return False
            if route is Privacy.TRUSTED_LAN and privacy not in ("trusted_lan", "cloud_allowed"):
                return False
        edges = connection.execute(
            "SELECT parent_memory_id,revision,source_hash FROM memory_derivations "
            "WHERE child_memory_id=?",
            (memory_id,),
        ).fetchall()
        for edge in edges:
            parent = connection.execute(
                "SELECT * FROM memories WHERE memory_id=?", (edge["parent_memory_id"],)
            ).fetchone()
            if parent is None or (parent["identity_id"], parent["person_id"]) != (
                row["identity_id"],
                row["person_id"],
            ):
                return False
            if parent["revision"] != edge["revision"]:
                return False
            if edge["source_hash"] and self._source_hash(connection, parent) != edge["source_hash"]:
                return False
            if row["status"] == "committed" and parent["status"] != "committed":
                return False
            if not self._lineage_valid(connection, parent, now, route, seen | {memory_id}):
                return False
        return True

    def _parent(
        self,
        connection: sqlite3.Connection,
        memory_id: str,
        identity: str,
        person: str,
        now: datetime,
        route: Privacy,
    ) -> sqlite3.Row:
        row: sqlite3.Row | None = connection.execute(
            "SELECT * FROM memories WHERE memory_id=?", (memory_id,)
        ).fetchone()
        if row is None or (row["identity_id"], row["person_id"]) != (identity, person):
            raise ValueError("source missing or scope mismatch")
        if not self._lineage_valid(connection, row, now, route):
            raise ValueError("source invalid, expired, revoked or unreadable")
        return row

    def _visible(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        now: datetime,
        route: Privacy = Privacy.LOCAL_ONLY,
    ) -> bool:
        revoked = connection.execute(
            "SELECT 1 FROM memory_sources s JOIN memory_source_revocations r "
            "ON r.source_event_id=s.source_event_id "
            "WHERE s.memory_id=?",
            (row["memory_id"],),
        ).fetchone()
        if revoked:
            return False
        derived = connection.execute(
            "SELECT 1 FROM memory_derivations WHERE child_memory_id=?", (row["memory_id"],)
        ).fetchone()
        return not derived or self._lineage_valid(connection, row, now, route)

    def _invalidate(
        self,
        connection: sqlite3.Connection,
        memory_id: str,
        *,
        reason: str,
        now: datetime,
        include_self: bool = False,
    ) -> None:
        descendants = connection.execute(
            "WITH RECURSIVE d(id) AS (SELECT child_memory_id FROM memory_derivations "
            "WHERE parent_memory_id=? "
            "UNION SELECT e.child_memory_id FROM memory_derivations e "
            "JOIN d ON e.parent_memory_id=d.id) "
            "SELECT id FROM d",
            (memory_id,),
        ).fetchall()
        ids = {str(item["id"]) for item in descendants}
        if include_self:
            ids.add(memory_id)
        else:
            ids.discard(memory_id)
        for current_id in ids:
            row: sqlite3.Row | None = connection.execute(
                "SELECT * FROM memories WHERE memory_id=?", (current_id,)
            ).fetchone()
            if row is None or row["deleted_at"] or row["status"] not in ("committed", "candidate"):
                continue
            connection.execute(
                "UPDATE memories SET status='superseded',revision=revision+1 WHERE memory_id=?",
                (current_id,),
            )
            updated = connection.execute(
                "SELECT * FROM memories WHERE memory_id=?", (current_id,)
            ).fetchone()
            assert updated is not None
            self._insert_revision(
                connection, self._to_memory(connection, updated), reason=reason, changed_at=now
            )
            connection.execute("DELETE FROM memory_fts WHERE memory_id=?", (current_id,))

    async def revoke_source(self, source_event_id: UUID, *, reason: str, now: datetime) -> bool:
        if not reason.strip() or now.utcoffset() is None:
            raise ValueError("source revocation requires reason and aware time")

        def write(connection: sqlite3.Connection) -> bool:
            cursor = connection.execute(
                "INSERT INTO memory_source_revocations(source_event_id,revoked_at,reason) "
                "VALUES(?,?,?) "
                "ON CONFLICT(source_event_id) DO NOTHING",
                (str(source_event_id), now.isoformat(), reason),
            )
            if not cursor.rowcount:
                return False
            rows = connection.execute(
                "SELECT memory_id FROM memory_sources WHERE source_event_id=?",
                (str(source_event_id),),
            ).fetchall()
            for row in rows:
                self._invalidate(
                    connection,
                    str(row["memory_id"]),
                    reason="source revoked",
                    now=now,
                    include_self=True,
                )
            return True

        return await self._store.run_transaction(write)

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
                "SELECT m.*, f.subject, f.predicate, f.object_json, f.verification "
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
                if self._visible(connection, row, datetime.now(UTC))
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
        route_privacy: Privacy | None = None,
        limit: int = 5,
        match_all: bool = True,
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
            if route_privacy in (Privacy.CLOUD_ALLOWED, Privacy.TRUSTED_LAN):
                allowed = (
                    ("cloud_allowed",)
                    if route_privacy is Privacy.CLOUD_ALLOWED
                    else ("trusted_lan", "cloud_allowed")
                )
                placeholders = ",".join("?" for _ in allowed)
                where.append(
                    "NOT EXISTS (SELECT 1 FROM memory_sources ms LEFT JOIN events e "
                    "ON e.event_id=ms.source_event_id WHERE ms.memory_id=m.memory_id "
                    "AND COALESCE(json_extract(e.envelope_json, '$.privacy'), '') "
                    f"NOT IN ({placeholders}))"
                )
                params.extend(allowed)
                where.append(
                    "EXISTS (SELECT 1 FROM memory_sources ms WHERE ms.memory_id=m.memory_id)"
                )
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
                (
                    row
                    for row in rows
                    if (score(row)[1] == len(tokens) if match_all else score(row)[1] > 0)
                    and self._visible(
                        connection,
                        row,
                        as_of or datetime.now(UTC),
                        route_privacy or Privacy.LOCAL_ONLY,
                    )
                ),
                key=score,
                reverse=True,
            )
            return [self._to_memory(connection, row) for row in ranked[:limit]]

        return await self._store.run_transaction(read)

    async def correct(
        self, memory_id: UUID, text: str, source_event: Event, *, reason: str
    ) -> Memory:
        def write(connection: sqlite3.Connection) -> Memory:
            row: sqlite3.Row | None = connection.execute(
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
            self._invalidate(connection, str(memory_id), reason="source corrected", now=changed_at)
            if memory.status is MemoryStatus.COMMITTED and self._visible(
                connection, updated, changed_at
            ):
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
            row: sqlite3.Row | None = connection.execute(
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
            return [
                self._to_memory(connection, row)
                for row in rows
                if self._visible(connection, row, datetime.now(UTC))
            ]

        return await self._store.run_transaction(read)

    async def rebuild_index(self) -> None:
        def write(connection: sqlite3.Connection) -> None:
            connection.execute("DELETE FROM memory_fts")
            rows = connection.execute(
                "SELECT * FROM memories WHERE status='committed' AND deleted_at IS NULL"
            ).fetchall()
            for row in rows:
                if self._visible(connection, row, datetime.now(UTC)):
                    self._index(connection, self._to_memory(connection, row))

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
        self, connection: sqlite3.Connection, memory: Memory, source_event: Event | None
    ) -> None:
        if source_event is not None:
            self._insert_event(connection, source_event)
        if any(
            connection.execute(
                "SELECT 1 FROM memory_source_revocations WHERE source_event_id=?", (str(source),)
            ).fetchone()
            for source in memory.source_event_ids
        ):
            raise ValueError("source revoked")
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
