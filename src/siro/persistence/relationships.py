"""SQLite relationship projection using immutable sourced revisions."""

from __future__ import annotations

import json
import sqlite3

from siro.core.relationships import RelationshipState, RelationshipUpdate
from siro.persistence.sqlite import SQLiteStore


class SQLiteRelationshipRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def current(self, identity_id: str, person_id: str) -> RelationshipState:
        def read(connection: sqlite3.Connection) -> RelationshipState:
            row = connection.execute(
                "SELECT revision, state_json FROM relationships "
                "WHERE identity_id = ? AND person_id = ? ORDER BY revision DESC LIMIT 1",
                (identity_id, person_id),
            ).fetchone()
            if row is None:
                return RelationshipState()
            state = json.loads(str(row["state_json"]))
            return RelationshipState(
                trust=float(state["trust"]),
                familiarity=float(state["familiarity"]),
                attachment=float(state["attachment"]),
                rupture=float(state["rupture"]),
                repair_history=int(state["repair_history"]),
                revision=int(row["revision"]),
            )

        return await self._store.run_transaction(read)

    async def record(self, identity_id: str, person_id: str, update: RelationshipUpdate) -> None:
        def write(connection: sqlite3.Connection) -> None:
            source = connection.execute(
                "SELECT 1 FROM events WHERE event_id = ?", (update.source_id,)
            ).fetchone()
            if source is None:
                raise ValueError("relationship source event does not exist")
            expected = connection.execute(
                "SELECT COALESCE(MAX(revision), 0) FROM relationships "
                "WHERE identity_id = ? AND person_id = ?",
                (identity_id, person_id),
            ).fetchone()[0]
            if update.state.revision != int(expected) + 1:
                raise RuntimeError("relationship revision conflict")
            payload = {
                "trust": update.state.trust,
                "familiarity": update.state.familiarity,
                "attachment": update.state.attachment,
                "rupture": update.state.rupture,
                "repair_history": update.state.repair_history,
                "last_event": update.event.value,
                "reason": update.reason,
            }
            connection.execute(
                "INSERT INTO relationships(identity_id, person_id, revision, state_json, "
                "source_ids) VALUES (?, ?, ?, ?, ?)",
                (
                    identity_id,
                    person_id,
                    update.state.revision,
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps([update.source_id]),
                ),
            )

        await self._store.run_transaction(write)
