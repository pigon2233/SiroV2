from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from siro.adapters.body.assets import load_verified_manifest


def write_manifest(root: Path, asset_path: str, digest: str) -> Path:
    manifest = root / "asset-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "asset_id": "live2d.test-model",
                "source_url": "https://example.invalid/official-download",
                "license_name": "Test Asset License",
                "license_url": "https://example.invalid/license",
                "accepted_by": "owner",
                "accepted_at": "2026-09-24T00:00:00+08:00",
                "files": [{"path": asset_path, "sha256": digest}],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_asset_manifest_verifies_provenance_and_checksum(tmp_path: Path) -> None:
    model = tmp_path / "model.json"
    model.write_bytes(b'{"version": 3}')
    digest = hashlib.sha256(model.read_bytes()).hexdigest()

    manifest = load_verified_manifest(write_manifest(tmp_path, "model.json", digest))

    assert manifest.asset_id == "live2d.test-model"
    assert manifest.accepted_by == "owner"


def test_asset_manifest_rejects_tamper_and_path_escape(tmp_path: Path) -> None:
    model = tmp_path / "model.json"
    model.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_verified_manifest(write_manifest(tmp_path, "model.json", "0" * 64))

    outside = tmp_path.parent / "outside.moc3"
    outside.write_bytes(b"outside")
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="escapes"):
        load_verified_manifest(write_manifest(tmp_path, "../outside.moc3", digest))
