"""SQLite repositories for identity and world-state ports."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime

from siro.core.identity import IdentityState
from siro.core.world import WorldObservation
from siro.persistence.sqlite import SQLiteStore


class ConcurrentUpdateError(RuntimeError):
    pass


class SQLiteIdentityRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def create(self, state: IdentityState, *, source_ids: Sequence[str]) -> None:
        def insert(connection: sqlite3.Connection) -> None:
            state_json = state.model_dump_json()
            connection.execute(
                "INSERT INTO identities(identity_id, core_json, core_version, created_at) "
                "VALUES (?, ?, ?, ?)",
                (state.identity_id, state_json, state.revision, state.created_at.isoformat()),
            )
            connection.execute(
                "INSERT INTO identity_revisions"
                "(identity_id, revision, patch_json, source_ids, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    state.identity_id,
                    state.revision,
                    state_json,
                    json.dumps(list(source_ids)),
                    state.updated_at.isoformat(),
                ),
            )

        await self._store.run_transaction(insert)

    async def get(self, identity_id: str) -> IdentityState | None:
        def read(connection: sqlite3.Connection) -> IdentityState | None:
            row = connection.execute(
                "SELECT core_json FROM identities WHERE identity_id = ?", (identity_id,)
            ).fetchone()
            return None if row is None else IdentityState.model_validate_json(row[0])

        return await self._store.run_transaction(read)

    async def save(
        self,
        state: IdentityState,
        *,
        expected_revision: int,
        patch: dict[str, object],
        source_ids: Sequence[str],
    ) -> None:
        def update(connection: sqlite3.Connection) -> None:
            changed = connection.execute(
                "UPDATE identities SET core_json = ?, core_version = ? "
                "WHERE identity_id = ? AND core_version = ?",
                (
                    state.model_dump_json(),
                    state.revision,
                    state.identity_id,
                    expected_revision,
                ),
            ).rowcount
            if not changed:
                raise ConcurrentUpdateError(
                    f"identity {state.identity_id} revision {expected_revision} is stale"
                )
            connection.execute(
                "INSERT INTO identity_revisions"
                "(identity_id, revision, patch_json, source_ids, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    state.identity_id,
                    state.revision,
                    json.dumps(patch),
                    json.dumps(list(source_ids)),
                    state.updated_at.isoformat(),
                ),
            )

        await self._store.run_transaction(update)


class SQLiteWorldRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def record(self, observation: WorldObservation) -> bool:
        def insert(connection: sqlite3.Connection) -> bool:
            connection.execute(
                "INSERT INTO world_observations"
                "(observation_id, entity_id, property, value_json, confidence, "
                "observed_at, expires_at, source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(observation.observation_id),
                    observation.entity_id,
                    observation.property,
                    json.dumps(observation.value),
                    observation.confidence,
                    observation.observed_at.isoformat(),
                    observation.expires_at.isoformat() if observation.expires_at else None,
                    observation.source_id,
                ),
            )
            current = connection.execute(
                "SELECT wc.revision, wo.observed_at, wo.observation_id "
                "FROM world_current wc JOIN world_observations wo "
                "ON wo.observation_id = wc.observation_id "
                "WHERE wc.entity_id = ? AND wc.property = ?",
                (observation.entity_id, observation.property),
            ).fetchone()
            if current is not None:
                current_key = (
                    datetime.fromisoformat(current["observed_at"]),
                    current["observation_id"],
                )
                new_key = (observation.observed_at, str(observation.observation_id))
                if new_key <= current_key:
                    return False
                revision = int(current["revision"]) + 1
                connection.execute(
                    "UPDATE world_current SET observation_id = ?, revision = ? "
                    "WHERE entity_id = ? AND property = ?",
                    (
                        str(observation.observation_id),
                        revision,
                        observation.entity_id,
                        observation.property,
                    ),
                )
            else:
                connection.execute(
                    "INSERT INTO world_current(entity_id, property, observation_id, revision) "
                    "VALUES (?, ?, ?, 1)",
                    (
                        observation.entity_id,
                        observation.property,
                        str(observation.observation_id),
                    ),
                )
            return True

        return await self._store.run_transaction(insert)

    async def current(self, entity_id: str, property_name: str) -> WorldObservation | None:
        def read(connection: sqlite3.Connection) -> WorldObservation | None:
            row = connection.execute(
                "SELECT wo.* FROM world_current wc JOIN world_observations wo "
                "ON wo.observation_id = wc.observation_id "
                "WHERE wc.entity_id = ? AND wc.property = ?",
                (entity_id, property_name),
            ).fetchone()
            if row is None:
                return None
            return WorldObservation.model_validate(
                {
                    "observation_id": row["observation_id"],
                    "entity_id": row["entity_id"],
                    "property": row["property"],
                    "value": json.loads(row["value_json"]),
                    "confidence": row["confidence"],
                    "observed_at": row["observed_at"],
                    "expires_at": row["expires_at"],
                    "source_id": row["source_id"],
                }
            )

        return await self._store.run_transaction(read)
