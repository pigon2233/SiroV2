"""SQLite consolidation checkpoints and clamped projections."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from siro.core.consolidation import ConsolidationCandidate
from siro.persistence.sqlite import SQLiteStore


class SQLiteConsolidationRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def start_or_resume(
        self, run_key: str, identity_id: str, now: datetime
    ) -> tuple[str, int]:
        def write(connection: sqlite3.Connection) -> tuple[str, int]:
            row = connection.execute(
                "SELECT run_id, checkpoint, identity_id FROM consolidation_runs WHERE run_key = ?",
                (run_key,),
            ).fetchone()
            if row is not None:
                if row["identity_id"] != identity_id:
                    raise ValueError("consolidation run identity mismatch")
                checkpoint = int(row["checkpoint"] or 0)
                connection.execute(
                    "UPDATE consolidation_runs SET status = 'running', updated_at = ? "
                    "WHERE run_id = ?",
                    (now.astimezone(UTC).isoformat(), str(row["run_id"])),
                )
                return str(row["run_id"]), checkpoint
            run_id = str(uuid4())
            timestamp = now.astimezone(UTC).isoformat()
            connection.execute(
                "INSERT INTO consolidation_runs(run_id, status, checkpoint, identity_id, run_key, "
                "created_at, updated_at) VALUES (?, 'running', '0', ?, ?, ?, ?)",
                (run_id, identity_id, run_key, timestamp, timestamp),
            )
            return run_id, 0

        return await self._store.run_transaction(write)

    async def commit_candidate(
        self,
        run_id: str,
        identity_id: str,
        candidate: ConsolidationCandidate,
        checkpoint: int,
        now: datetime,
    ) -> bool:
        scoped_key = hashlib.sha256(json.dumps([identity_id, candidate.key]).encode()).hexdigest()

        def write(connection: sqlite3.Connection) -> bool:
            owner = connection.execute(
                "SELECT identity_id FROM consolidation_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if owner is None or owner["identity_id"] != identity_id:
                raise ValueError("consolidation run identity mismatch")
            existing = connection.execute(
                "SELECT 1 FROM consolidation_outputs o JOIN memories m "
                "ON m.memory_id = o.memory_id WHERE o.candidate_key IN (?, ?) "
                "AND m.identity_id = ?",
                (scoped_key, candidate.key, identity_id),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    "UPDATE consolidation_runs SET checkpoint = ?, updated_at = ? WHERE run_id = ?",
                    (str(checkpoint), now.astimezone(UTC).isoformat(), run_id),
                )
                return False
            if any(
                connection.execute(
                    "SELECT 1 FROM memory_source_revocations WHERE source_event_id=?",
                    (str(source),),
                ).fetchone()
                for source in candidate.source_event_ids
            ):
                raise ValueError("candidate source revoked")
            if any(
                connection.execute(
                    "SELECT 1 FROM memory_sources s JOIN memories m ON m.memory_id=s.memory_id "
                    "WHERE s.source_event_id=? AND (m.deleted_at IS NOT NULL "
                    "OR m.status='superseded' OR m.revision>1) LIMIT 1",
                    (str(source),),
                ).fetchone()
                for source in candidate.source_event_ids
            ):
                raise ValueError(
                    "candidate source has changed memory history; use bound derivation"
                )
            placeholders = ",".join("?" for _ in candidate.source_event_ids)
            count = connection.execute(
                f"SELECT count(*) FROM events WHERE event_id IN ({placeholders})",
                tuple(str(value) for value in candidate.source_event_ids),
            ).fetchone()[0]
            if int(count) != len(set(candidate.source_event_ids)):
                raise ValueError("candidate references unknown source events")
            legacy_key_taken = (
                connection.execute(
                    "SELECT 1 FROM consolidation_outputs WHERE candidate_key = ?", (candidate.key,)
                ).fetchone()
                is not None
            )
            # Keep single-identity keys compatible with older releases. Scope only collisions.
            storage_key = scoped_key if legacy_key_taken else candidate.key
            memory_id = str(uuid5(NAMESPACE_URL, f"siro:consolidation:{storage_key}"))
            timestamp = now.astimezone(UTC).isoformat()
            status = (
                "candidate"
                if candidate.inferred and len(set(candidate.source_event_ids)) < 3
                else "committed"
            )
            connection.execute(
                "INSERT INTO memories(memory_id, identity_id, kind, person_id, text, status, "
                "confidence, valid_from, revision) VALUES (?, ?, ?, 'owner', ?, ?, ?, ?, 1)",
                (
                    memory_id,
                    identity_id,
                    candidate.kind,
                    candidate.text,
                    status,
                    candidate.confidence,
                    timestamp,
                ),
            )
            for source_id in candidate.source_event_ids:
                connection.execute(
                    "INSERT INTO memory_sources(memory_id, source_event_id) VALUES (?, ?)",
                    (memory_id, str(source_id)),
                )
            source_json = json.dumps([str(value) for value in candidate.source_event_ids])
            connection.execute(
                "INSERT INTO memory_revisions(memory_id, revision, kind, person_id, text, status, "
                "confidence, valid_from, source_ids_json, reason, changed_at) "
                "VALUES (?, 1, ?, 'owner', ?, ?, ?, ?, ?, 'consolidation', ?)",
                (
                    memory_id,
                    candidate.kind,
                    candidate.text,
                    status,
                    candidate.confidence,
                    timestamp,
                    source_json,
                    timestamp,
                ),
            )
            if status == "committed":
                connection.execute(
                    "INSERT INTO memory_fts(memory_id, identity_id, person_id, text) "
                    "VALUES (?, ?, 'owner', ?)",
                    (memory_id, identity_id, candidate.text),
                )
            connection.execute(
                "INSERT INTO consolidation_outputs(candidate_key, run_id, memory_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (storage_key, run_id, memory_id, timestamp),
            )
            connection.execute(
                "UPDATE consolidation_runs SET checkpoint = ?, updated_at = ? WHERE run_id = ?",
                (str(checkpoint), timestamp, run_id),
            )
            return True

        return await self._store.run_transaction(write)

    async def finish_run(self, run_id: str, state: str, checkpoint: int, now: datetime) -> None:
        await self._store.run_transaction(
            lambda connection: connection.execute(
                "UPDATE consolidation_runs SET status = ?, checkpoint = ?, updated_at = ? "
                "WHERE run_id = ?",
                (state, str(checkpoint), now.astimezone(UTC).isoformat(), run_id),
            )
        )

    async def apply_trait(
        self,
        identity_id: str,
        trait: str,
        requested_delta: float,
        source_ids: tuple[UUID, ...],
        *,
        now: datetime,
    ) -> float:
        if len(set(source_ids)) < 3:
            raise ValueError("trait evolution requires three independent sources")
        per_run = max(-0.01, min(0.01, requested_delta))
        week_start = (now - timedelta(days=now.weekday())).date().isoformat()

        def write(connection: sqlite3.Connection) -> float:
            placeholders = ",".join("?" for _ in source_ids)
            known = connection.execute(
                f"SELECT count(*) FROM events WHERE event_id IN ({placeholders})",
                tuple(str(value) for value in source_ids),
            ).fetchone()[0]
            if int(known) != len(set(source_ids)):
                raise ValueError("trait references unknown source events")
            row = connection.execute(
                "SELECT value, weekly_delta, week_start, revision FROM trait_projections "
                "WHERE identity_id = ? AND trait = ?",
                (identity_id, trait),
            ).fetchone()
            value, weekly, revision = (
                (0.0, 0.0, 0)
                if row is None
                else (
                    float(row["value"]),
                    float(row["weekly_delta"]) if str(row["week_start"]) == week_start else 0.0,
                    int(row["revision"]),
                )
            )
            allowed = max(-0.05 - weekly, min(0.05 - weekly, per_run))
            new_value = max(-1.0, min(1.0, value + allowed))
            connection.execute(
                "INSERT INTO trait_projections(identity_id, trait, value, weekly_delta, "
                "week_start, revision, source_ids_json) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(identity_id, trait) DO UPDATE SET value=excluded.value, "
                "weekly_delta=excluded.weekly_delta, week_start=excluded.week_start, "
                "revision=excluded.revision, source_ids_json=excluded.source_ids_json",
                (
                    identity_id,
                    trait,
                    new_value,
                    weekly + allowed,
                    week_start,
                    revision + 1,
                    json.dumps([str(v) for v in source_ids]),
                ),
            )
            return new_value

        return await self._store.run_transaction(write)

    async def revise_relationship(
        self,
        identity_id: str,
        person_id: str,
        state: dict[str, object],
        source_ids: tuple[UUID, ...],
    ) -> int:
        if not source_ids:
            raise ValueError("relationship revision requires provenance")

        def write(connection: sqlite3.Connection) -> int:
            known = connection.execute(
                f"SELECT count(*) FROM events WHERE event_id IN "
                f"({','.join('?' for _ in source_ids)})",
                tuple(str(value) for value in source_ids),
            ).fetchone()[0]
            if int(known) != len(set(source_ids)):
                raise ValueError("relationship references unknown sources")
            row = connection.execute(
                "SELECT max(revision) FROM relationships WHERE identity_id = ? AND person_id = ?",
                (identity_id, person_id),
            ).fetchone()
            revision = int(row[0] or 0) + 1
            connection.execute(
                "INSERT INTO relationships"
                "(identity_id, person_id, revision, state_json, source_ids) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    identity_id,
                    person_id,
                    revision,
                    json.dumps(state, ensure_ascii=False),
                    json.dumps([str(value) for value in source_ids]),
                ),
            )
            return revision

        return await self._store.run_transaction(write)
