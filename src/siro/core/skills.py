"""Versioned skill manifests and deny-by-default registry rules."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SKILL_PACKAGE_MAX_FILES = 512
SKILL_PACKAGE_MAX_ENTRIES = 1024
SKILL_PACKAGE_MAX_DEPTH = 32
SKILL_FILE_MAX_BYTES = 4 * 1024 * 1024
SKILL_PACKAGE_MAX_BYTES = 16 * 1024 * 1024
_PACKAGE_PREFIX = "siro-skill-package-v1:"


class SkillApprovalRequired(ValueError):
    pass


def is_package_hash(value: str) -> bool:
    return re.fullmatch(r"siro-skill-package-v1:[0-9a-f]{64}", value) is not None


class SkillState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class Permission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: str = Field(min_length=1)
    scope_required: str = Field(min_length=1)


class ResourceLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_mb: int = Field(ge=16, le=4096)
    output_bytes: int = Field(ge=1, le=16 * 1024 * 1024)
    cpu_seconds: int = Field(default=2, ge=1, le=60)


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,127}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    contract_version: Literal[1]
    description: str = Field(min_length=1, max_length=500)
    entrypoint: str = Field(pattern=r"^python:[a-zA-Z_][\w.]*:[a-zA-Z_]\w*$")
    input_schema: str
    output_schema: str
    permissions: tuple[Permission, ...]
    risk: Literal["observe", "normal", "destructive", "system", "critical"]
    timeout_ms: int = Field(ge=10, le=120_000)
    concurrency: int = Field(ge=1, le=32)
    resource_limits: ResourceLimits
    network: Literal["denied"]
    idempotency: Literal["read_only", "idempotent", "action_ledger"]
    cancellation: Literal["cooperative", "process"]
    compensation: Literal["none", "declared"]


@dataclass(frozen=True, slots=True)
class InstalledSkill:
    manifest: SkillManifest
    root: Path
    manifest_hash: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]


def load_skill(root: Path) -> InstalledSkill:
    return capture_skill(root)[0]


def capture_skill(root: Path) -> tuple[InstalledSkill, dict[str, tuple[bytes, int]]]:
    """Capture bounded package bytes once; executable identity excludes only transient cache."""
    root = root.absolute()
    if root.resolve() != root:
        raise ValueError("skill root must be canonical and cannot contain symlinks")
    files = _read_package(root)
    raw = json.loads(files["manifest.json"][0].decode("utf-8"))
    manifest = SkillManifest.model_validate(raw)
    input_schema = _load_schema(files, manifest.input_schema)
    output_schema = _load_schema(files, manifest.output_schema)
    module = manifest.entrypoint.split(":")[1].replace(".", "/")
    if f"{module}.py" not in files and f"{module}/__init__.py" not in files:
        raise ValueError("skill entrypoint must have source in its package")
    digest = hashlib.sha256()
    digest.update(b"siro-skill-package-v1\0")
    for name, (data, executable) in sorted(files.items()):
        encoded = name.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(executable.to_bytes(2, "big"))
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    installed = InstalledSkill(
        manifest, root, _PACKAGE_PREFIX + digest.hexdigest(), input_schema, output_schema
    )
    return installed, files


def _load_schema(files: dict[str, tuple[bytes, int]], relative: str) -> dict[str, object]:
    if "\\" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError("skill schema path must be canonical within its package")
    if relative not in files:
        raise ValueError("skill schema is missing from its package")
    raw = json.loads(files[relative][0].decode("utf-8"))
    if not isinstance(raw, dict) or raw.get("type") != "object":
        raise ValueError("skill schemas must describe an object")
    return {str(key): value for key, value in raw.items()}


def _read_package(root: Path) -> dict[str, tuple[bytes, int]]:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise ValueError("no-follow package capture is unavailable")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", directory_flags)
    try:
        for component in root.parts[1:]:
            next_descriptor = os.open(component, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        files: dict[str, tuple[bytes, int]] = {}
        entries = 0
        total_bytes = 0

        def walk(parent: int, prefix: str, depth: int) -> None:
            nonlocal entries, total_bytes
            if depth > SKILL_PACKAGE_MAX_DEPTH:
                raise ValueError("skill package exceeds its directory depth limit")
            names: list[str] = []
            with os.scandir(parent) as iterator:
                for entry in iterator:
                    entries += 1
                    if entries > SKILL_PACKAGE_MAX_ENTRIES:
                        raise ValueError("skill package exceeds its entry limit")
                    names.append(entry.name)
            for name in sorted(names):
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                relative = prefix + name
                if stat.S_ISLNK(info.st_mode):
                    raise ValueError("skill package cannot contain symlinks")
                if stat.S_ISDIR(info.st_mode):
                    if name == "__pycache__":
                        continue
                    child = os.open(name, directory_flags, dir_fd=parent)
                    try:
                        walk(child, relative + "/", depth + 1)
                    finally:
                        os.close(child)
                    continue
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError("skill package requires unaliased regular files")
                if Path(name).suffix.lower() in {".pyc", ".pyo", ".so", ".pyd", ".dll", ".dylib"}:
                    raise ValueError("skill package executable format is unsupported")
                if len(files) >= SKILL_PACKAGE_MAX_FILES:
                    raise ValueError("skill package exceeds its file limit")
                file_descriptor = os.open(
                    name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
                )
                with os.fdopen(file_descriptor, "rb") as stream:
                    before = os.fstat(stream.fileno())
                    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                        raise ValueError("skill file changed its type during capture")
                    if before.st_size > SKILL_FILE_MAX_BYTES:
                        raise ValueError("skill file exceeds its byte limit")
                    data = stream.read(SKILL_FILE_MAX_BYTES + 1)
                    after = os.fstat(stream.fileno())
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size,
                    after.st_mtime_ns,
                    after.st_ctime_ns,
                ):
                    raise ValueError("skill file changed during capture")
                total_bytes += len(data)
                if len(data) > SKILL_FILE_MAX_BYTES or total_bytes > SKILL_PACKAGE_MAX_BYTES:
                    raise ValueError("skill package exceeds its byte limit")
                files[relative] = data, stat.S_IMODE(after.st_mode) & 0o111

        walk(descriptor, "", 0)
        if "manifest.json" not in files:
            raise ValueError("skill package has no manifest")
        return files
    finally:
        os.close(descriptor)


def validate_object(schema: dict[str, object], value: object) -> dict[str, object]:
    """Validate the bounded object-schema subset supported by contract version 1."""

    if not isinstance(value, dict):
        raise ValueError("value must be an object")
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise ValueError("invalid object schema")
    missing = [name for name in required if name not in value]
    if missing:
        raise ValueError(f"missing required fields: {missing}")
    if schema.get("additionalProperties") is False:
        extras = sorted(set(value) - set(properties))
        if extras:
            raise ValueError(f"unknown fields: {extras}")
    python_types: dict[str, type[object]] = {
        "string": str,
        "integer": int,
        "number": (int, float),  # type: ignore[dict-item]
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    for name, item in value.items():
        rule = properties.get(name)
        if not isinstance(rule, dict) or "type" not in rule:
            continue
        expected = python_types.get(str(rule["type"]))
        if expected is None or not isinstance(item, expected):
            raise ValueError(f"field {name} has the wrong type")
    return {str(key): item for key, item in value.items()}
