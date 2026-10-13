from __future__ import annotations

import hashlib
import hmac
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from siro.cli import main
from siro.core.releases import ReleaseManager, ReleaseManifest

FORMAT = "siro-release-manifest-v1"
KEY = b"synthetic-release-key"  # Synthetic fixtures only.


def signed_values(bundle: Path, *, minimum: int = 1, maximum: int = 8) -> dict[str, Any]:
    values: dict[str, Any] = {
        "signing_format": FORMAT,
        "version": "2.0.0",
        "source_sha256": ReleaseManager._digest(bundle),
        "min_schema": minimum,
        "max_schema": maximum,
    }
    # Independently implement the documented wire bytes, not the production helper.
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    values["signature"] = hmac.new(KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return values


@pytest.fixture
def release_fixture(tmp_path: Path) -> tuple[ReleaseManager, Path, Path]:
    root = tmp_path / "manager"
    root.mkdir()
    (root / "active.json").write_text('{"version":"1.0.0"}')
    (root / "last-known-good.json").write_text('{"version":"0.9.0"}')
    (root / "releases/1.0.0").mkdir(parents=True)
    (root / "releases/1.0.0/app.txt").write_text("existing release")
    database = tmp_path / "synthetic.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE state(value TEXT)")
        connection.execute("INSERT INTO state VALUES ('preserve latest data')")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "app.txt").write_text("synthetic candidate")
    return ReleaseManager(root, KEY, current_schema=8, database=database), bundle, database


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def assert_rejected_without_effects(
    manager: ReleaseManager,
    bundle: Path,
    database: Path,
    artifact: ReleaseManifest,
    monkeypatch: pytest.MonkeyPatch,
    *,
    status: str = "invalid_manifest",
) -> None:
    before = tree_bytes(manager._root)
    database_before = database.read_bytes()
    calls: list[str] = []

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        calls.append("effect")
        raise AssertionError("rejected manifest reached a release effect")

    monkeypatch.setattr(manager, "_backup_database", forbidden)
    monkeypatch.setattr(manager, "_atomic_json", forbidden)
    monkeypatch.setattr(shutil, "copytree", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    result = manager.stage_and_activate(bundle, artifact, (sys.executable, "-c", "pass"))
    assert result.status == status
    assert result.active_version == "1.0.0"
    assert calls == []
    assert tree_bytes(manager._root) == before
    assert database.read_bytes() == database_before


def test_legacy_schema_tampering_no_longer_activates(
    release_fixture: tuple[ReleaseManager, Path, Path],
) -> None:
    manager, bundle, database = release_fixture
    digest = manager._digest(bundle)
    original = ReleaseManifest(
        version="2.0.0",
        source_sha256=digest,
        signature=hmac.new(KEY, f"2.0.0:{digest}".encode(), hashlib.sha256).hexdigest(),
        min_schema=1,
        max_schema=2,
    )
    assert not manager._compatible(original)
    before = tree_bytes(manager._root)
    database_before = database.read_bytes()
    changed = original.model_copy(update={"max_schema": 8})
    result = manager.stage_and_activate(bundle, changed, (sys.executable, "-c", "pass"))
    assert result.status == "invalid_manifest", result
    assert tree_bytes(manager._root) == before
    assert database.read_bytes() == database_before


def test_canonical_payload_has_independent_fixed_bytes_and_signature() -> None:
    values = {
        "version": "2.0.0",
        "source_sha256": "0" * 64,
        "min_schema": 1,
        "max_schema": 8,
        "signing_format": FORMAT,
        "signature": "f" * 64,
    }
    expected = (
        b'{"max_schema":8,"min_schema":1,"signing_format":"siro-release-manifest-v1",'
        b'"source_sha256":"0000000000000000000000000000000000000000000000000000000000000000",'
        b'"version":"2.0.0"}'
    )
    artifact = ReleaseManifest.model_validate(values)
    assert artifact.signing_payload() == expected
    # Literal vector calculated independently for this synthetic key and fixed bytes.
    assert hmac.new(KEY, expected, hashlib.sha256).hexdigest() == (
        # pragma: allowlist nextline secret
        "c8c1be8f382d8fe63da1bd1ff6856f2ab35b3477b77fc76a69d678f443fcc814"
    )
    changed_signature = artifact.model_copy(update={"signature": "e" * 64})
    assert changed_signature.signing_payload() == expected
    reversed_json = json.dumps(dict(reversed(list(values.items()))), indent=4)
    assert ReleaseManifest.model_validate_json(reversed_json).signing_payload() == expected


@pytest.mark.parametrize(
    ("field", "value"),
    [("version", "3.0.0"), ("source_sha256", "a" * 64), ("min_schema", 2), ("max_schema", 9)],
)
def test_each_signed_decision_field_tamper_has_zero_effects(
    release_fixture: tuple[ReleaseManager, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: Any,
) -> None:
    manager, bundle, database = release_fixture
    values = signed_values(bundle)
    values[field] = value
    assert_rejected_without_effects(
        manager, bundle, database, ReleaseManifest.model_validate(values), monkeypatch
    )


@pytest.mark.parametrize("legacy_format", ["absent", None])
def test_readable_legacy_manifest_is_not_a_signature_fallback(
    release_fixture: tuple[ReleaseManager, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    legacy_format: str | None,
) -> None:
    manager, bundle, database = release_fixture
    values = signed_values(bundle)
    values["signature"] = hmac.new(
        KEY, f"2.0.0:{values['source_sha256']}".encode(), hashlib.sha256
    ).hexdigest()
    if legacy_format == "absent":
        del values["signing_format"]
    else:
        values["signing_format"] = None
    artifact = ReleaseManifest.model_validate_json(json.dumps(values))
    with pytest.raises(ValueError, match="legacy"):
        artifact.signing_payload()
    assert_rejected_without_effects(manager, bundle, database, artifact, monkeypatch)


def test_current_format_cannot_use_old_hmac_message(
    release_fixture: tuple[ReleaseManager, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, bundle, database = release_fixture
    values = signed_values(bundle)
    values["signature"] = hmac.new(
        KEY, f"2.0.0:{values['source_sha256']}".encode(), hashlib.sha256
    ).hexdigest()
    assert_rejected_without_effects(
        manager, bundle, database, ReleaseManifest.model_validate(values), monkeypatch
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("signing_format", "siro-release-manifest-v2"),
        ("signing_format", ""),
        ("signing_format", True),
        ("signing_format", 1),
        ("signing_format", 1.0),
        ("unrecognized_field", "not signed"),
        ("min_schema", 0),
        ("max_schema", 0),
        ("min_schema", 9),
        ("min_schema", True),
        ("max_schema", False),
        ("min_schema", "1"),
        ("max_schema", "8"),
        ("min_schema", 1.0),
        ("max_schema", 8.5),
    ],
)
def test_invalid_wire_format_range_and_types_are_rejected(
    release_fixture: tuple[ReleaseManager, Path, Path], field: str, value: Any
) -> None:
    manager, bundle, database = release_fixture
    before = tree_bytes(manager._root)
    database_before = database.read_bytes()
    values = signed_values(bundle)
    values[field] = value
    with pytest.raises(ValidationError):
        ReleaseManifest.model_validate_json(json.dumps(values))
    assert tree_bytes(manager._root) == before
    assert database.read_bytes() == database_before


@pytest.mark.parametrize(
    ("field", "value"),
    [("min_schema", True), ("min_schema", "1"), ("max_schema", 0), ("signing_format", "other")],
)
def test_unvalidated_model_copy_cannot_bypass_entry_validation(
    release_fixture: tuple[ReleaseManager, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: Any,
) -> None:
    manager, bundle, database = release_fixture
    artifact = ReleaseManifest.model_validate(signed_values(bundle)).model_copy(
        update={field: value}
    )
    assert_rejected_without_effects(manager, bundle, database, artifact, monkeypatch)


def test_bundle_change_is_rejected_without_release_effects(
    release_fixture: tuple[ReleaseManager, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, bundle, database = release_fixture
    artifact = ReleaseManifest.model_validate(signed_values(bundle))
    (bundle / "app.txt").write_text("changed after signing")
    assert_rejected_without_effects(manager, bundle, database, artifact, monkeypatch)


@pytest.mark.parametrize(("minimum", "maximum"), [(1, 7), (9, 9)])
def test_valid_signed_incompatible_release_retains_original_status(
    release_fixture: tuple[ReleaseManager, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    minimum: int,
    maximum: int,
) -> None:
    manager, bundle, database = release_fixture
    artifact = ReleaseManifest.model_validate(
        signed_values(bundle, minimum=minimum, maximum=maximum)
    )
    assert_rejected_without_effects(
        manager, bundle, database, artifact, monkeypatch, status="incompatible_schema"
    )


def test_valid_canonical_manifest_uses_original_staging_and_backup_flow(
    release_fixture: tuple[ReleaseManager, Path, Path],
) -> None:
    manager, bundle, database = release_fixture
    values = signed_values(bundle)
    artifact = ReleaseManifest.model_validate_json(json.dumps(dict(reversed(list(values.items())))))
    result = manager.stage_and_activate(bundle, artifact, (sys.executable, "-c", "pass"))
    assert result.status == "activated" and result.active_version == "2.0.0"
    assert (manager._root / "releases/2.0.0/app.txt").read_text() == "synthetic candidate"
    assert json.loads((manager._root / "last-known-good.json").read_text())["version"] == "1.0.0"
    with sqlite3.connect(manager._root / "backups/before-2.0.0.sqlite3") as backup:
        assert backup.execute("SELECT value FROM state").fetchone()[0] == "preserve latest data"
    with sqlite3.connect(database) as live:
        assert live.execute("SELECT value FROM state").fetchone()[0] == "preserve latest data"


@pytest.mark.parametrize("current_format", [False, True])
def test_actual_cli_stage_rejects_legacy_and_accepts_complete_signatures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, current_format: bool
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "app.txt").write_text("CLI synthetic bundle")
    values = signed_values(bundle, maximum=100)
    if not current_format:
        del values["signing_format"]
        values["signature"] = hmac.new(
            KEY, f"2.0.0:{values['source_sha256']}".encode(), hashlib.sha256
        ).hexdigest()
    artifact = tmp_path / "manifest.json"
    artifact.write_text(json.dumps(values))
    root = tmp_path / "release-root"
    marker = tmp_path / "healthcheck-ran"
    monkeypatch.setenv("SIRO_TEST_FIX009_RELEASE_KEY", KEY.decode())
    result = main(
        [
            "release",
            "--release-root",
            str(root),
            "--key-env",
            "SIRO_TEST_FIX009_RELEASE_KEY",
            "stage",
            "--bundle",
            str(bundle),
            "--manifest",
            str(artifact),
            "--healthcheck",
            json.dumps([sys.executable, "-c", f"open({str(marker)!r}, 'w').write('ran')"]),
        ]
    )
    assert result == (0 if current_format else 1)
    assert marker.exists() is current_format
    assert (root / "active.json").exists() is current_format
    assert artifact.read_text() == json.dumps(values)
