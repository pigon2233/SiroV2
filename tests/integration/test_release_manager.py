from __future__ import annotations

import hashlib
import hmac
import sqlite3
import sys
from pathlib import Path

import pytest

from siro.core.releases import ReleaseManager, ReleaseManifest


def manifest(
    manager: ReleaseManager, bundle: Path, version: str, *, minimum: int = 1
) -> ReleaseManifest:
    digest = manager._digest_v2(bundle)
    artifact = ReleaseManifest(
        version=version,
        source_sha256=digest,
        signature="0" * 64,
        min_schema=minimum,
        max_schema=max(8, minimum),
        signing_format="siro-release-manifest-v2",
    )
    signature = hmac.new(
        b"release-test-key", artifact.signing_payload(), hashlib.sha256
    ).hexdigest()
    return artifact.model_copy(update={"signature": signature})


def test_t32_staging_healthcheck_atomic_activation_and_rollback(tmp_path: Path) -> None:
    database = tmp_path / "data.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE state(value TEXT)")
        connection.execute("INSERT INTO state VALUES ('before-release')")
        connection.execute("CREATE TABLE schema_migrations(version INTEGER)")
        connection.executemany(
            "INSERT INTO schema_migrations VALUES (?)", [(n,) for n in range(1, 9)]
        )
    manager = ReleaseManager(
        tmp_path / "manager", b"release-test-key", current_schema=8, database=database
    )
    good = tmp_path / "good"
    good.mkdir()
    (good / "app.txt").write_text("v1", encoding="utf-8")
    result = manager.stage_and_activate(
        good, manifest(manager, good, "1.0.0"), (sys.executable, "-c", "pass")
    )
    assert result.status == "activated" and manager.active_version() == "1.0.0"
    with sqlite3.connect(tmp_path / "manager/backups/before-1.0.0.sqlite3") as connection:
        assert connection.execute("SELECT value FROM state").fetchone()[0] == "before-release"

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "app.txt").write_text("v2", encoding="utf-8")
    failed = manager.stage_and_activate(
        broken, manifest(manager, broken, "2.0.0"), (sys.executable, "-c", "raise SystemExit(1)")
    )
    assert failed.status == "healthcheck_failed" and manager.active_version() == "1.0.0"
    incompatible = manager.stage_and_activate(
        broken, manifest(manager, broken, "2.0.0", minimum=9), (sys.executable, "-c", "pass")
    )
    assert incompatible.status == "incompatible_schema" and manager.active_version() == "1.0.0"

    newer = manager.stage_and_activate(
        broken, manifest(manager, broken, "2.0.0"), (sys.executable, "-c", "pass")
    )
    assert newer.active_version == "2.0.0"
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE state SET value = 'after-release'")
    assert manager.rollback().active_version == "1.0.0"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM state").fetchone()[0] == "after-release"


def test_t32_interrupted_activation_keeps_previous_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = ReleaseManager(tmp_path / "manager", b"release-test-key", current_schema=8)
    first = tmp_path / "first"
    first.mkdir()
    (first / "app.txt").write_text("v1", encoding="utf-8")
    manager.stage_and_activate(
        first, manifest(manager, first, "1.0.0"), (sys.executable, "-c", "pass")
    )
    second = tmp_path / "second"
    second.mkdir()
    (second / "app.txt").write_text("v2", encoding="utf-8")
    original = manager._atomic_json

    def interrupt_active(path: Path, value: dict[str, str]) -> None:
        if path.name == "active.json":
            raise OSError("simulated activation interruption")
        original(path, value)

    monkeypatch.setattr(manager, "_atomic_json", interrupt_active)
    with pytest.raises(OSError, match="interruption"):
        manager.stage_and_activate(
            second, manifest(manager, second, "2.0.0"), (sys.executable, "-c", "pass")
        )
    assert manager.active_version() == "1.0.0"
