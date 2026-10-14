from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from siro.core.releases import ReleaseLaunchError, ReleaseManager, ReleaseManifest

KEY = b"synthetic-f20-release-key"
CURRENT = "siro-release-manifest-v2"
LEGACY = "siro-release-manifest-v1"


def tree(root: Path, files: dict[str, bytes]) -> Path:
    root.mkdir()
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


def signed(root: Path, *, legacy: bool = False) -> ReleaseManifest:
    values = {
        "version": "2.0.0",
        "min_schema": 1,
        "max_schema": 1,
        "signing_format": LEGACY if legacy else CURRENT,
        "source_sha256": ReleaseManager._digest(root)
        if legacy
        else ReleaseManager._digest_v2(root),
    }
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return ReleaseManifest.model_validate(
        {
            **values,
            "signature": hmac.new(KEY, payload, hashlib.sha256).hexdigest(),
        }
    )


def test_legacy_ambiguous_trees_never_authorize_release(tmp_path: Path) -> None:
    left = tree(tmp_path / "left", {"a": b"ALPHAb", "b": b"BRAVO"})
    right = tree(tmp_path / "right", {"a": b"ALPHA", "b": b"bBRAVO"})
    assert ReleaseManager._digest(left) == ReleaseManager._digest(right)
    approval = signed(left, legacy=True)
    manager = ReleaseManager(tmp_path / "manager", KEY, current_schema=1)
    assert not manager._verified(left, approval)
    assert not manager._verified(right, approval)


def test_v2_independent_framed_wire_and_path_order(tmp_path: Path) -> None:
    source = tree(tmp_path / "source", {"a.py": b"", "a/file": b"X"})
    # Existing Path.parts order puts a/file before a.py, unlike raw string sorting.
    wire = (
        b"siro-release-source-v2\0"
        b"\0\0\0\0\0\0\0\2"
        b"\0\0\0\0\0\0\0\6a/file"
        b"\0\0\0\0\0\0\0\1X"
        b"\0\0\0\0\0\0\0\4a.py"
        b"\0\0\0\0\0\0\0\0"
    )
    assert ReleaseManager._digest_v2(source) == hashlib.sha256(wire).hexdigest()
    assert ReleaseManager._digest(source) != ReleaseManager._digest_v2(source)


def test_v2_distinguishes_the_actual_legacy_boundary_collision(tmp_path: Path) -> None:
    left = tree(tmp_path / "left", {"a": b"ALPHAb", "b": b"BRAVO"})
    right = tree(tmp_path / "right", {"a": b"ALPHA", "b": b"bBRAVO"})
    manager = ReleaseManager(tmp_path / "manager", KEY, current_schema=1)
    artifact = signed(left)
    assert manager._verified(left, artifact)
    assert not manager._verified(right, artifact)


@pytest.mark.parametrize("change", ["name", "count", "content", "empty", "resource", "unicode"])
def test_every_source_file_identity_change_invalidates_approval(
    tmp_path: Path, change: str
) -> None:
    root = tree(tmp_path / "source", {"a.py": b"pass\n", "settings.json": b'{"value":1}'})
    artifact = signed(root)
    if change == "name":
        (root / "a.py").rename(root / "b.py")
    elif change == "count":
        (root / "extra.py").write_bytes(b"pass\n")
    elif change == "content":
        (root / "a.py").write_bytes(b"raise RuntimeError()\n")
    elif change == "empty":
        (root / "empty").touch()
    elif change == "resource":
        (root / "settings.json").write_bytes(b'{"value":2}')
    else:
        (root / "資料.txt").write_bytes("測試".encode())
    manager = ReleaseManager(tmp_path / "manager", KEY, current_schema=1)
    assert not manager._verified(root, artifact)


@pytest.mark.parametrize("legacy", [True, False])
def test_wrong_digest_algorithm_or_tag_cannot_authorize(tmp_path: Path, legacy: bool) -> None:
    root = tree(tmp_path / "source", {"a": b"X"})
    manager = ReleaseManager(tmp_path / "manager", KEY, current_schema=1)
    artifact = signed(root, legacy=legacy)
    values = artifact.model_dump()
    values["source_sha256"] = (
        ReleaseManager._digest_v2(root) if legacy else ReleaseManager._digest(root)
    )
    values["signature"] = hmac.new(
        KEY,
        json.dumps(
            {k: v for k, v in values.items() if k != "signature"},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    assert not manager._verified(root, ReleaseManifest.model_validate(values))


def test_legacy_stage_is_zero_effect_before_even_reading_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tree(tmp_path / "source", {"a": b"X"})
    approval = signed(source, legacy=True)
    manager = ReleaseManager(tmp_path / "manager", KEY, current_schema=1)
    effects: list[object] = []

    def health(*args: Any, **kwargs: Any) -> SimpleNamespace:
        effects.append("healthcheck")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", health)
    outcome = manager.stage_and_activate(source, approval, ("never-execute",))
    assert outcome.status == "invalid_manifest" and not effects
    assert not manager._root.exists()


def test_legacy_refusal_does_not_hash_or_reapprove_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tree(tmp_path / "source", {"a": b"X"})
    approval = signed(source, legacy=True)
    manager = ReleaseManager(tmp_path / "manager", KEY, current_schema=1)

    def forbidden(path: Path) -> str:
        raise AssertionError("legacy execution must refuse before source read")

    monkeypatch.setattr(manager, "_digest", forbidden)
    assert not manager._verified(source, approval)


def test_legacy_selector_and_rollback_keep_receipts_pointers_and_data(tmp_path: Path) -> None:
    manager_root = tmp_path / "manager"
    target = tree(
        tmp_path / "source",
        {
            "src/siro/__init__.py": b"# fixture\n",
            "src/siro/core/releases.py": b"# fixture\n",
            "src/siro/services/presentation/gateway.py": b"# fixture\n",
        },
    )
    artifact = signed(target, legacy=True)
    release = manager_root / "releases/2.0.0"
    release.parent.mkdir(parents=True)
    target.rename(release)
    receipt = manager_root / "manifests/2.0.0.json"
    receipt.parent.mkdir()
    receipt.write_text(artifact.model_dump_json())
    (manager_root / "active.json").write_text('{"version":"2.0.0"}')
    (manager_root / "last-known-good.json").write_text('{"version":"2.0.0"}')
    database = tmp_path / "siro.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE schema_migrations(version INTEGER)")
        db.execute("INSERT INTO schema_migrations VALUES(1)")
        db.execute("CREATE TABLE latest(value TEXT)")
        db.execute("INSERT INTO latest VALUES('committed-after-release')")
    manager = ReleaseManager(manager_root, KEY, current_schema=1, database=database)
    before = {
        str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }
    with pytest.raises(ReleaseLaunchError, match="invalid_release_target"):
        manager.resolve_launch_target()
    assert manager.rollback().status == "invalid_rollback_target"
    assert {
        str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    } == before


def test_v2_stages_and_rejects_later_source_tamper(tmp_path: Path) -> None:
    root = tree(tmp_path / "source", {"a": b"X", "b": b"Y"})
    manager = ReleaseManager(tmp_path / "manager", KEY, current_schema=1)
    artifact = signed(root)
    result = manager.stage_and_activate(root, artifact, ("/bin/true",))
    assert result.status == "activated"
    (manager._root / "releases/2.0.0/b").write_bytes(b"different")
    assert not manager._verified(manager._root / "releases/2.0.0", artifact)
