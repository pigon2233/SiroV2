"""Versioned skill manifests and deny-by-default registry rules."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    manifest_path = root / "manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = SkillManifest.model_validate(raw)
    input_schema = _load_schema(root, manifest.input_schema)
    output_schema = _load_schema(root, manifest.output_schema)
    digest = hashlib.sha256()
    for path in (manifest_path, root / manifest.input_schema, root / manifest.output_schema):
        digest.update(path.read_bytes())
    return InstalledSkill(manifest, root.resolve(), digest.hexdigest(), input_schema, output_schema)


def _load_schema(root: Path, relative: str) -> dict[str, object]:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError("skill schema escapes its root") from error
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("type") != "object":
        raise ValueError("skill schemas must describe an object")
    return {str(key): value for key, value in raw.items()}


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
