"""SQLite-backed installed-skill state."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from siro.core.skills import (
    InstalledSkill,
    SkillApprovalRequired,
    SkillState,
    is_package_hash,
    load_skill,
)
from siro.persistence.sqlite import SQLiteStore


class SQLiteSkillRegistry:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def install(self, skill: InstalledSkill, *, enabled: bool = False) -> None:
        try:
            current = await asyncio.to_thread(load_skill, skill.root)
        except (OSError, ValueError) as error:
            raise SkillApprovalRequired(
                "skill requires package verification and approval"
            ) from error
        if current != skill:
            raise SkillApprovalRequired("skill requires package verification and approval")
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
        row = await self._store.run_transaction(
            lambda connection: connection.execute(
                "SELECT manifest_hash, path_ref FROM skills WHERE skill_id = ? AND version = ?",
                (skill_id, version),
            ).fetchone()
        )
        if row is None:
            return False
        if enabled:
            try:
                current = await asyncio.to_thread(load_skill, Path(row["path_ref"]))
            except (OSError, ValueError) as error:
                raise SkillApprovalRequired(
                    "skill requires package verification and approval"
                ) from error
            if (
                not is_package_hash(row["manifest_hash"])
                or current.manifest.id != skill_id
                or current.manifest.version != version
                or current.manifest_hash != row["manifest_hash"]
                or str(current.root) != row["path_ref"]
            ):
                raise SkillApprovalRequired("skill requires package verification and approval")

        def update(connection: sqlite3.Connection) -> bool:
            return bool(
                connection.execute(
                    "UPDATE skills SET state = ? WHERE skill_id = ? AND version = ? "
                    "AND manifest_hash = ? AND path_ref = ?",
                    (state, skill_id, version, row["manifest_hash"], row["path_ref"]),
                ).rowcount
            )

        return await self._store.run_transaction(update)

    async def is_enabled(
        self, skill_id: str, version: str, *, identity: InstalledSkill | None = None
    ) -> bool:
        def read(connection: sqlite3.Connection) -> bool:
            row = connection.execute(
                "SELECT state, manifest_hash, path_ref FROM skills "
                "WHERE skill_id = ? AND version = ?",
                (skill_id, version),
            ).fetchone()
            if (
                row is None
                or row["state"] != SkillState.ENABLED
                or not is_package_hash(row["manifest_hash"])
            ):
                return False
            return identity is None or (
                identity.manifest.id == skill_id
                and identity.manifest.version == version
                and row["manifest_hash"] == identity.manifest_hash
                and row["path_ref"] == str(identity.root)
            )

        return await self._store.run_transaction(read)
