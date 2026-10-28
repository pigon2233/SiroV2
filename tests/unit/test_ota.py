from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from siro.services.devices.ota import build_manifest, update_available


def test_manifest_and_version_gate(tmp_path: Path) -> None:
    image = tmp_path / "siro-node.bin"
    image.write_bytes(b"firmware")
    manifest = build_manifest(image, "1.2.0")
    assert manifest.sha256 == hashlib.sha256(b"firmware").hexdigest()
    assert manifest.size == 8
    assert update_available("1.1.9", manifest)
    assert not update_available("1.2.0", manifest)
    assert not update_available("1.10.0", manifest)


def test_rejects_bad_input(tmp_path: Path) -> None:
    image = tmp_path / "x.bin"
    image.write_bytes(b"")
    with pytest.raises(ValueError):
        build_manifest(image, "1.0.0")
    image.write_bytes(b"x")
    with pytest.raises(ValueError):
        build_manifest(image, "v1")
