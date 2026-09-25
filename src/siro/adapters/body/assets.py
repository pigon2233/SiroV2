"""Licensed body asset manifest validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class BodyAssetFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class BodyAssetManifest(BaseModel):
    """Evidence required before a model can be loaded by the renderer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=1, ge=1, le=1)
    asset_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    source_url: HttpUrl
    license_name: str = Field(min_length=1, max_length=256)
    license_url: HttpUrl
    accepted_by: str = Field(min_length=1, max_length=256)
    accepted_at: str = Field(min_length=1, max_length=64)
    files: tuple[BodyAssetFile, ...] = Field(min_length=1)


def load_verified_manifest(path: Path) -> BodyAssetManifest:
    """Load an asset manifest and verify every declared local file."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    manifest = BodyAssetManifest.model_validate(raw)
    root = path.parent.resolve()
    for item in manifest.files:
        candidate = (root / item.path).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError(f"asset path escapes manifest directory: {item.path}")
        if not candidate.is_file():
            raise ValueError(f"asset file is missing: {item.path}")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if digest != item.sha256:
            raise ValueError(f"asset checksum mismatch: {item.path}")
    return manifest
