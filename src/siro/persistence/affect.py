"""SQLite affect state, emotion episode, and preference persistence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from siro.contracts.events import Privacy
from siro.core.affect import (
    ALGORITHM_VERSION,
    AffectResult,
    AffectState,
    CopingStrategy,
    DriveState,
    MoodState,
)
from siro.persistence.sqlite import SQLiteStore


@dataclass(frozen=True, slots=True)
class Preference:
    preference_id: str
    identity_id: str
    person_id: str
    scope: str
    subject: str
    polarity: float
    strength: float
    confidence: float
    context: str
    status: str
    source_ids: tuple[str, ...]
    revision: int


class SQLiteAffectRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def state(self, identity_id: str, session_id: str) -> AffectState | None:
        def read(connection: sqlite3.Connection) -> AffectState | None:
            row = connection.execute(
                "SELECT emotion, valence, arousal, intensity, reason FROM affect_states "
                "WHERE identity_id = ? AND session_id = ?",
                (identity_id, session_id),
            ).fetchone()
            return (
                None
                if row is None
                else AffectState(
                    str(row["emotion"]),
                    float(row["valence"]),
                    float(row["arousal"]),
                    float(row["intensity"]),
                    str(row["reason"]),
                )
            )

        return await self._store.run_transaction(read)

    async def record(
        self, identity_id: str, session_id: str, state: AffectState, source_id: str
    ) -> None:
        now = datetime.now(UTC).isoformat()

        def write(connection: sqlite3.Connection) -> None:
            row = connection.execute(
                "SELECT revision FROM affect_states WHERE identity_id = ? AND session_id = ?",
                (identity_id, session_id),
            ).fetchone()
            revision = 1 if row is None else int(row["revision"]) + 1
            connection.execute(
                "INSERT INTO affect_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(identity_id, session_id) DO UPDATE SET emotion=excluded.emotion, "
                "valence=excluded.valence, arousal=excluded.arousal, intensity=excluded.intensity, "
                "reason=excluded.reason, revision=excluded.revision, "
                "updated_at=excluded.updated_at",
                (
                    identity_id,
                    session_id,
                    state.emotion,
                    state.valence,
                    state.arousal,
                    state.intensity,
                    state.reason,
                    revision,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO emotion_episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    identity_id,
                    session_id,
                    state.emotion,
                    state.valence,
                    state.arousal,
                    state.intensity,
                    state.reason,
                    source_id,
                    now,
                ),
            )

        await self._store.run_transaction(write)

    async def dynamics(
        self, identity_id: str, session_id: str
    ) -> tuple[MoodState | None, DriveState | None]:
        def read(connection: sqlite3.Connection) -> tuple[MoodState | None, DriveState | None]:
            mood_row = connection.execute(
                "SELECT pleasure, arousal, dominance FROM mood_states "
                "WHERE identity_id = ? AND session_id = ?",
                (identity_id, session_id),
            ).fetchone()
            drive_row = connection.execute(
                "SELECT safety, connection, competence, curiosity, autonomy, rest "
                "FROM drive_states WHERE identity_id = ? AND session_id = ?",
                (identity_id, session_id),
            ).fetchone()
            mood = (
                None
                if mood_row is None
                else MoodState(
                    float(mood_row["pleasure"]),
                    float(mood_row["arousal"]),
                    float(mood_row["dominance"]),
                )
            )
            drives = (
                None
                if drive_row is None
                else DriveState(
                    float(drive_row["safety"]),
                    float(drive_row["connection"]),
                    float(drive_row["competence"]),
                    float(drive_row["curiosity"]),
                    float(drive_row["autonomy"]),
                    float(drive_row["rest"]),
                )
            )
            return mood, drives

        return await self._store.run_transaction(read)

    async def elapsed_hours(self, identity_id: str, session_id: str, now: datetime) -> float:
        def read(connection: sqlite3.Connection) -> float:
            row = connection.execute(
                "SELECT updated_at FROM mood_states WHERE identity_id = ? AND session_id = ?",
                (identity_id, session_id),
            ).fetchone()
            if row is None:
                return 0.0
            updated = datetime.fromisoformat(str(row["updated_at"]))
            return max(0.0, (now - updated).total_seconds() / 3600.0)

        return await self._store.run_transaction(read)

    async def latest_coping(self, identity_id: str, session_id: str) -> CopingStrategy | None:
        def read(connection: sqlite3.Connection) -> CopingStrategy | None:
            row = connection.execute(
                "SELECT c.strategy FROM coping_decisions c "
                "JOIN appraisal_records a ON a.appraisal_id = c.appraisal_id "
                "WHERE a.identity_id = ? AND a.session_id = ? "
                "ORDER BY a.occurred_at DESC, a.rowid DESC LIMIT 1",
                (identity_id, session_id),
            ).fetchone()
            return None if row is None else CopingStrategy(str(row["strategy"]))

        return await self._store.run_transaction(read)

    async def record_result(
        self,
        identity_id: str,
        session_id: str,
        result: AffectResult,
        source_id: str,
        *,
        algorithm_config: dict[str, object] | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        appraisal_id = str(uuid4())
        appraisal = result.appraisal
        payload = {
            "algorithm_version": ALGORITHM_VERSION,
            "algorithm_config": algorithm_config or {"version": ALGORITHM_VERSION},
            "event_id": appraisal.event_id,
            "novelty": appraisal.novelty,
            "pleasantness": appraisal.pleasantness,
            "goal_relevance": appraisal.goal_relevance,
            "goal_conduciveness": appraisal.goal_conduciveness,
            "certainty": appraisal.certainty,
            "agency": appraisal.agency.value,
            "controllability": appraisal.controllability,
            "power": appraisal.power,
            "norm_compatibility": appraisal.norm_compatibility,
            "relationship_significance": appraisal.relationship_significance,
            "urgency": appraisal.urgency,
            "drive_changes": appraisal.drive_changes,
        }

        def write(connection: sqlite3.Connection) -> None:
            connection.execute(
                "INSERT INTO appraisal_records VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    appraisal_id,
                    identity_id,
                    session_id,
                    source_id,
                    appraisal.event_id,
                    json.dumps(payload),
                    now,
                ),
            )
            connection.executemany(
                "INSERT INTO emotion_activations VALUES (?, ?, ?, ?)",
                [
                    (appraisal_id, item.emotion, item.intensity, item.reason)
                    for item in result.emotions
                ],
            )
            connection.execute(
                "INSERT INTO coping_decisions VALUES (?, ?, ?, ?)",
                (
                    appraisal_id,
                    result.coping.strategy.value,
                    result.coping.urgency,
                    result.coping.reason,
                ),
            )
            connection.execute(
                "INSERT INTO mood_states VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(identity_id, session_id) DO UPDATE SET "
                "pleasure=excluded.pleasure, arousal=excluded.arousal, "
                "dominance=excluded.dominance, updated_at=excluded.updated_at",
                (
                    identity_id,
                    session_id,
                    result.mood.pleasure,
                    result.mood.arousal,
                    result.mood.dominance,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO drive_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(identity_id, session_id) DO UPDATE SET "
                "safety=excluded.safety, connection=excluded.connection, "
                "competence=excluded.competence, curiosity=excluded.curiosity, "
                "autonomy=excluded.autonomy, rest=excluded.rest, updated_at=excluded.updated_at",
                (
                    identity_id,
                    session_id,
                    result.drives.safety,
                    result.drives.connection,
                    result.drives.competence,
                    result.drives.curiosity,
                    result.drives.autonomy,
                    result.drives.rest,
                    now,
                ),
            )

        await self._store.run_transaction(write)

    async def put_preference(self, preference: Preference) -> None:
        if not preference.source_ids:
            raise ValueError("preference requires provenance")
        now = datetime.now(UTC).isoformat()

        def write(connection: sqlite3.Connection) -> None:
            row = connection.execute(
                "SELECT source_ids_json FROM preferences WHERE identity_id = ? AND person_id = ? "
                "AND scope = ? AND subject = ? AND context = ?",
                (
                    preference.identity_id,
                    preference.person_id,
                    preference.scope,
                    preference.subject,
                    preference.context,
                ),
            ).fetchone()
            sources = list(preference.source_ids)
            if row is not None:
                sources = list(dict.fromkeys([*json.loads(str(row["source_ids_json"])), *sources]))
            connection.execute(
                "INSERT INTO preferences VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(identity_id, person_id, scope, subject, context) DO UPDATE SET "
                "polarity=excluded.polarity, strength=excluded.strength, "
                "confidence=excluded.confidence, status=excluded.status, "
                "source_ids_json=excluded.source_ids_json, revision=preferences.revision + 1, "
                "updated_at=excluded.updated_at",
                (
                    preference.preference_id,
                    preference.identity_id,
                    preference.person_id,
                    preference.scope,
                    preference.subject,
                    preference.polarity,
                    preference.strength,
                    preference.confidence,
                    preference.context,
                    preference.status,
                    json.dumps(sources),
                    preference.revision,
                    now,
                    now,
                ),
            )

        await self._store.run_transaction(write)

    async def delete_preference(self, preference_id: str, source_id: str) -> bool:
        if not source_id:
            raise ValueError("preference deletion requires provenance")
        now = datetime.now(UTC).isoformat()

        def update(connection: sqlite3.Connection) -> bool:
            row = connection.execute(
                "SELECT source_ids_json FROM preferences WHERE preference_id = ? "
                "AND status != 'deleted'",
                (preference_id,),
            ).fetchone()
            if row is None:
                return False
            sources = [*json.loads(str(row["source_ids_json"])), source_id]
            connection.execute(
                "UPDATE preferences SET status = 'deleted', source_ids_json = ?, "
                "revision = revision + 1, updated_at = ? WHERE preference_id = ?",
                (json.dumps(list(dict.fromkeys(sources))), now, preference_id),
            )
            return True

        return await self._store.run_transaction(update)

    async def preferences(
        self, identity_id: str, person_id: str, *, route_privacy: Privacy | None = None
    ) -> list[Preference]:
        def read(connection: sqlite3.Connection) -> list[Preference]:
            where = ["identity_id = ?", "person_id = ?", "status != 'deleted'"]
            if route_privacy is Privacy.CLOUD_ALLOWED:
                where.append("json_array_length(source_ids_json) > 0")
                where.append(
                    "NOT EXISTS (SELECT 1 FROM json_each(preferences.source_ids_json) sources "
                    "LEFT JOIN events e ON e.event_id = sources.value "
                    "WHERE COALESCE(json_extract(e.envelope_json, '$.privacy'), '') "
                    "!= 'cloud_allowed')"
                )
            rows = connection.execute(
                "SELECT * FROM preferences WHERE "
                + " AND ".join(where)
                + " ORDER BY updated_at DESC",
                (identity_id, person_id),
            ).fetchall()
            return [
                Preference(
                    str(r["preference_id"]),
                    str(r["identity_id"]),
                    str(r["person_id"]),
                    str(r["scope"]),
                    str(r["subject"]),
                    float(r["polarity"]),
                    float(r["strength"]),
                    float(r["confidence"]),
                    str(r["context"]),
                    str(r["status"]),
                    tuple(json.loads(str(r["source_ids_json"]))),
                    int(r["revision"]),
                )
                for r in rows
            ]

        return await self._store.run_transaction(read)
