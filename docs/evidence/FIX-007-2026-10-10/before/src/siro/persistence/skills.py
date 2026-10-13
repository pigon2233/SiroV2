"""SQLite-backed installed-skill state."""

from __future__ import annotations

import sqlite3

from siro.core.skills import InstalledSkill, SkillState
from siro.persistence.sqlite import SQLiteStore


class SQLiteSkillRegistry:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def install(self, skill: InstalledSkill, *, enabled: bool = False) -> None:
        state = SkillState.ENABLED if enabled else SkillState.DISABLED
        await self._store.run_transaction(
            lambda connection: connection.execute(
                "INSERT INTO skills(skill_id, version, manifest_hash, state, path_ref) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(skill_id, version) DO UPDATE SET "
                "manifest_hash=excluded.manifest_hash, state=excluded.state, "
                "path_ref=excluded.path_ref",
                (
                    skill.manifest.id,
                    skill.manifest.version,
                    skill.manifest_hash,
                    state,
                    str(skill.root),
                ),
            )
        )

    async def set_enabled(self, skill_id: str, version: str, *, enabled: bool) -> bool:
        state = SkillState.ENABLED if enabled else SkillState.DISABLED

        def update(connection: sqlite3.Connection) -> bool:
            return bool(
                connection.execute(
                    "UPDATE skills SET state = ? WHERE skill_id = ? AND version = ?",
                    (state, skill_id, version),
                ).rowcount
            )

        return await self._store.run_transaction(update)

    async def is_enabled(self, skill_id: str, version: str) -> bool:
        def read(connection: sqlite3.Connection) -> bool:
            row = connection.execute(
                "SELECT state FROM skills WHERE skill_id = ? AND version = ?",
                (skill_id, version),
            ).fetchone()
            return row is not None and row["state"] == SkillState.ENABLED

        return await self._store.run_transaction(read)
