"""Signed, staged releases with atomic last-known-good activation."""

from __future__ import annotations

import hashlib
import hmac
import json
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReleaseManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    min_schema: int = Field(ge=1, strict=True)
    max_schema: int = Field(ge=1, strict=True)
    signing_format: Literal["siro-release-manifest-v1"] | None = None

    @model_validator(mode="after")
    def _valid_schema_range(self) -> Self:
        if self.min_schema > self.max_schema:
            raise ValueError("min_schema must not exceed max_schema")
        return self

    def signing_payload(self) -> bytes:
        validated = ReleaseManifest.model_validate(self.model_dump(warnings=False))
        if validated.signing_format is None:
            raise ValueError("legacy release manifest has no complete signing format")
        return json.dumps(
            validated.model_dump(mode="json", exclude={"signature"}),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ReleaseResult:
    status: str
    active_version: str | None


class ReleaseManager:
    def __init__(
        self, root: Path, signing_key: bytes, *, current_schema: int, database: Path | None = None
    ) -> None:
        self._root = root
        self._key = signing_key
        self._schema = current_schema
        self._database = database

    def stage_and_activate(
        self, bundle: Path, manifest: ReleaseManifest, healthcheck: tuple[str, ...]
    ) -> ReleaseResult:
        try:
            manifest = ReleaseManifest.model_validate(manifest.model_dump(warnings=False))
        except ValueError:
            return ReleaseResult("invalid_manifest", self.active_version())
        if not self._compatible(manifest):
            return ReleaseResult("incompatible_schema", self.active_version())
        if not self._verified(bundle, manifest):
            return ReleaseResult("invalid_manifest", self.active_version())
        backup: Path | None = None
        if self._database is not None:
            backup = self._root / "backups" / f"before-{manifest.version}.sqlite3"
            self._backup_database(backup)
        staging = self._root / "staging" / manifest.version
        release = self._root / "releases" / manifest.version
        staging.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(bundle, staging)
        completed = subprocess.run(
            healthcheck, cwd=staging, capture_output=True, timeout=30, check=False
        )
        if completed.returncode != 0:
            shutil.rmtree(staging, ignore_errors=True)
            return ReleaseResult("healthcheck_failed", self.active_version())
        release.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(release, ignore_errors=True)
        staging.replace(release)
        previous = self.active_version()
        if previous is not None:
            history = {"version": previous}
            if backup is not None:
                history["database_backup"] = str(backup)
            self._atomic_json(self._root / "last-known-good.json", history)
        self._atomic_json(self._root / "active.json", {"version": manifest.version})
        return ReleaseResult("activated", manifest.version)

    def active_version(self) -> str | None:
        path = self._root / "active.json"
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return (
            value.get("version")
            if isinstance(value, dict) and isinstance(value.get("version"), str)
            else None
        )

    def rollback(self) -> ReleaseResult:
        history = self._root / "last-known-good.json"
        if not history.exists():
            return ReleaseResult("no_last_known_good", self.active_version())
        value = json.loads(history.read_text(encoding="utf-8"))
        version = value.get("version")
        if not isinstance(version, str) or not (self._root / "releases" / version).is_dir():
            return ReleaseResult("no_last_known_good", self.active_version())
        backup = value.get("database_backup")
        if self._database is not None:
            if not isinstance(backup, str) or not Path(backup).is_file():
                return ReleaseResult("database_backup_missing", self.active_version())
            self._restore_database(Path(backup))
        self._atomic_json(self._root / "active.json", {"version": version})
        return ReleaseResult("rolled_back", version)

    def _verified(self, bundle: Path, manifest: ReleaseManifest) -> bool:
        try:
            payload = manifest.signing_payload()
        except ValueError:
            return False
        digest = self._digest(bundle)
        expected = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, manifest.source_sha256) and hmac.compare_digest(
            expected, manifest.signature
        )

    def _compatible(self, manifest: ReleaseManifest) -> bool:
        return manifest.min_schema <= self._schema <= manifest.max_schema

    @staticmethod
    def _digest(directory: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                digest.update(str(path.relative_to(directory)).encode())
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def _atomic_json(self, path: Path, value: dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value), encoding="utf-8")
        temporary.replace(path)

    def _backup_database(self, destination: Path) -> None:
        if self._database is None:
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        with sqlite3.connect(self._database) as source, sqlite3.connect(temporary) as target:
            source.backup(target)
            result = target.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise sqlite3.DatabaseError("release backup integrity check failed")
        temporary.replace(destination)

    def _restore_database(self, source: Path) -> None:
        if self._database is None:
            return
        self._database.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._database.with_suffix(".rollback.tmp")
        temporary.unlink(missing_ok=True)
        try:
            with sqlite3.connect(source) as backup, sqlite3.connect(temporary) as target:
                result = backup.execute("PRAGMA integrity_check").fetchone()
                if result is None or result[0] != "ok":
                    raise sqlite3.DatabaseError("release rollback backup integrity check failed")
                backup.backup(target)
            temporary.replace(self._database)
        finally:
            temporary.unlink(missing_ok=True)
