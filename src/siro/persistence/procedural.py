"""Durable review-only procedural candidate storage."""

from __future__ import annotations

import json
import sqlite3

from siro.core.procedural import ProceduralCandidate
from siro.persistence.sqlite import SQLiteStore


class SQLiteProceduralCandidateRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def save(self, candidate: ProceduralCandidate) -> None:
        await self._store.run_transaction(
            lambda connection: connection.execute(
                "INSERT INTO procedural_candidates("
                "candidate_id,source_trace_ids_json,workflow_hash,"
                "capabilities_json,fixture_json,status,created_at) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(workflow_hash) DO NOTHING",
                (
                    str(candidate.candidate_id),
                    json.dumps([str(item) for item in candidate.source_trace_ids]),
                    candidate.workflow_hash,
                    json.dumps(candidate.capabilities),
                    candidate.model_dump_json(include={"fixture"}),
                    candidate.status,
                    candidate.created_at.isoformat(),
                ),
            )
        )

    async def candidates(self) -> tuple[ProceduralCandidate, ...]:
        def read(connection: sqlite3.Connection) -> list[sqlite3.Row]:
            return connection.execute(
                "SELECT candidate_id,source_trace_ids_json,workflow_hash,"
                "capabilities_json,fixture_json,"
                "status,created_at FROM procedural_candidates ORDER BY created_at"
            ).fetchall()

        rows = await self._store.run_transaction(read)
        return tuple(
            ProceduralCandidate.model_validate(
                {
                    "candidate_id": row["candidate_id"],
                    "source_trace_ids": json.loads(row["source_trace_ids_json"]),
                    "workflow_hash": row["workflow_hash"],
                    "capabilities": json.loads(row["capabilities_json"]),
                    "fixture": json.loads(row["fixture_json"])["fixture"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                }
            )
            for row in rows
        )
