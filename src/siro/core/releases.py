"""Signed, staged releases with atomic last-known-good activation."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import shutil
import sqlite3
import stat
import subprocess
from collections.abc import Mapping
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


class ReleaseLaunchError(RuntimeError):
    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(f"SIRO release launch refused: {status}")


@dataclass(frozen=True, slots=True)
class VerifiedRelease:
    version: str
    source_sha256: str
    directory: Path
    schema_version: int

    def validate_runtime(
        self,
        database: Path,
        *,
        package_file: Path,
        gateway_file: Path,
        release_file: Path,
        current_schema: int,
    ) -> None:
        expected = self.directory / "src/siro"
        origins = (
            (package_file, expected / "__init__.py"),
            (gateway_file, expected / "services/presentation/gateway.py"),
            (release_file, expected / "core/releases.py"),
        )
        if any(actual.resolve() != selected for actual, selected in origins):
            raise ReleaseLaunchError("wrong_loaded_source")
        if current_schema != self.schema_version:
            raise ReleaseLaunchError("schema_migration_required")
        if _read_data_schema(database, current_schema) != self.schema_version:
            raise ReleaseLaunchError("data_schema_changed")


def _read_data_schema(database: Path | None, maximum: int) -> int | None:
    if type(maximum) is not int or maximum < 1:
        return None
    if database is None:
        return maximum
    try:
        if not stat.S_ISREG(database.lstat().st_mode):
            return None
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
        try:
            connection.execute("PRAGMA query_only=ON")
            records = connection.execute(
                "SELECT CASE WHEN typeof(version) = 'integer' THEN version ELSE NULL END "
                "FROM schema_migrations ORDER BY version LIMIT 4097"
            ).fetchall()
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        return None
    if not records or len(records) > 4096:
        return None
    if [record[0] for record in records] != list(range(1, len(records) + 1)):
        return None
    return len(records)


class ReleaseManager:
    def __init__(
        self, root: Path, signing_key: bytes, *, current_schema: int, database: Path | None = None
    ) -> None:
        self._root = root
        self._key = signing_key
        self._schema = current_schema
        self._database = database

    def resolve_launch_target(self) -> VerifiedRelease:
        if self._root.is_symlink():
            raise ReleaseLaunchError("invalid_release_target")
        active = self._root / "active.json"
        if not active.exists() and not active.is_symlink():
            raise ReleaseLaunchError("no_active_release")
        try:
            pointer = self._json_record(active)
            version = pointer.get("version")
            if (
                set(pointer) != {"version"}
                or not isinstance(version, str)
                or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None
            ):
                raise ValueError("invalid active version")
        except (OSError, ValueError, RecursionError) as error:
            raise ReleaseLaunchError("invalid_active_release") from error
        target = self._root / "releases" / version
        try:
            if target.is_symlink() or target.parent.is_symlink() or not target.is_dir():
                raise ValueError("invalid release directory")
            for path in target.rglob("*"):
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or (
                    not stat.S_ISDIR(info.st_mode)
                    and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)
                ):
                    raise ValueError("aliased release source")
            for relative in (
                "src/siro/__init__.py",
                "src/siro/core/releases.py",
                "src/siro/services/presentation/gateway.py",
            ):
                if not (target / relative).is_file():
                    raise ValueError("missing release entrypoint")
            manifest = ReleaseManifest.model_validate(
                self._json_record(self._root / "manifests" / f"{version}.json")
            )
            if manifest.version != version or not self._verified(target, manifest):
                raise ValueError("unverified release source")
        except (OSError, ValueError, RecursionError) as error:
            raise ReleaseLaunchError("invalid_release_target") from error
        schema = None if self._database is None else self._rollback_schema()
        if schema is None:
            raise ReleaseLaunchError("schema_unknown")
        if schema > self._schema or not manifest.min_schema <= schema <= manifest.max_schema:
            raise ReleaseLaunchError("incompatible_schema")
        return VerifiedRelease(version, manifest.source_sha256, target.resolve(), schema)

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
        release = self._root / "releases" / manifest.version
        approval = self._root / "manifests" / f"{manifest.version}.json"
        if release.exists() or release.is_symlink() or approval.exists() or approval.is_symlink():
            return ReleaseResult("release_version_exists", self.active_version())
        backup: Path | None = None
        if self._database is not None:
            backup = self._root / "backups" / f"before-{manifest.version}.sqlite3"
            self._backup_database(backup)
        staging = self._root / "staging" / manifest.version
        staging.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(bundle, staging)
        completed = subprocess.run(
            healthcheck, cwd=staging, capture_output=True, timeout=30, check=False
        )
        if completed.returncode != 0:
            shutil.rmtree(staging, ignore_errors=True)
            return ReleaseResult("healthcheck_failed", self.active_version())
        if not self._verified(staging, manifest):
            shutil.rmtree(staging, ignore_errors=True)
            return ReleaseResult("invalid_manifest", self.active_version())
        release.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(release)
        self._atomic_json(approval, manifest.model_dump(mode="json"))
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
        try:
            value = self._json_record(history)
            version = value.get("version")
            if set(value) - {"version", "database_backup"} or not isinstance(version, str):
                raise ValueError("invalid rollback history")
            # Validate the path component before looking up any target filesystem path.
            ReleaseManifest.model_validate(
                {
                    "version": version,
                    "source_sha256": "0" * 64,
                    "signature": "0" * 64,
                    "min_schema": 1,
                    "max_schema": 1,
                }
            )
        except (OSError, ValueError, RecursionError):
            return ReleaseResult("invalid_rollback_target", self.active_version())
        target = self._root / "releases" / version
        if not target.is_dir():
            return ReleaseResult("no_last_known_good", self.active_version())
        try:
            if target.is_symlink() or target.parent.is_symlink():
                raise ValueError("aliased rollback target")
            for path in target.rglob("*"):
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or (
                    not stat.S_ISDIR(info.st_mode)
                    and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)
                ):
                    raise ValueError("aliased rollback source")
            manifest = ReleaseManifest.model_validate(
                self._json_record(self._root / "manifests" / f"{version}.json")
            )
            if manifest.version != version or not self._verified(target, manifest):
                raise ValueError("unverified rollback target")
        except (OSError, ValueError, RecursionError):
            return ReleaseResult("invalid_rollback_target", self.active_version())
        schema = self._rollback_schema()
        if schema is None:
            return ReleaseResult("schema_unknown", self.active_version())
        if schema > self._schema or not manifest.min_schema <= schema <= manifest.max_schema:
            return ReleaseResult("incompatible_schema", self.active_version())
        self._atomic_json(self._root / "active.json", {"version": version})
        return ReleaseResult("rolled_back", version)

    @staticmethod
    def _json_record(path: Path) -> dict[str, object]:
        info = path.lstat()
        if (
            path.parent.is_symlink()
            or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_size > 65536
        ):
            raise ValueError("invalid release record")

        def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate release record field")
                result[key] = value
            return result

        with path.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("oversized release record")
        value = json.loads(raw, object_pairs_hook=unique_object)
        if not isinstance(value, dict):
            raise ValueError("invalid release record")
        return value

    def _rollback_schema(self) -> int | None:
        return _read_data_schema(self._database, self._schema)

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

    def _atomic_json(self, path: Path, value: Mapping[str, object]) -> None:
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
