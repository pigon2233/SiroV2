from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from siro.cli import main
from siro.core.releases import ReleaseManager, ReleaseManifest
from siro.persistence.sqlite import SQLiteStore, load_migrations

KEY = b"synthetic-d48-test-key"
HEALTH = (sys.executable, "-c", "pass")


def signed(bundle: Path, version: str, *, minimum: int = 1, maximum: int = 8) -> ReleaseManifest:
    values: dict[str, Any] = {
        "version": version,
        "source_sha256": ReleaseManager._digest(bundle),
        "min_schema": minimum,
        "max_schema": maximum,
        "signing_format": "siro-release-manifest-v1",
    }
    wire = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    values["signature"] = hmac.new(KEY, wire, hashlib.sha256).hexdigest()
    return ReleaseManifest.model_validate(values)


def bundle_at(root: Path, name: str) -> Path:
    bundle = root / name
    bundle.mkdir()
    (bundle / "app.txt").write_text(name)
    return bundle


def set_schema(database: Path, versions: list[Any]) -> None:
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("DROP TABLE IF EXISTS schema_migrations")
        connection.execute("CREATE TABLE schema_migrations(version)")
        connection.executemany("INSERT INTO schema_migrations VALUES (?)", [(n,) for n in versions])


@pytest.fixture
def releases(tmp_path: Path) -> tuple[ReleaseManager, Path]:
    database = tmp_path / "synthetic.sqlite3"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("CREATE TABLE conversation(value TEXT)")
        connection.execute("CREATE TABLE memory(value TEXT)")
        connection.execute("CREATE TABLE ledger(value TEXT)")
        for name in ("conversation", "memory", "ledger"):
            connection.execute(f"INSERT INTO {name} VALUES (?)", ("before",))
    set_schema(database, list(range(1, 9)))
    manager = ReleaseManager(tmp_path / "manager", KEY, current_schema=8, database=database)
    for name, version in (("first", "1.0.0"), ("second", "2.0.0")):
        bundle = bundle_at(tmp_path, name)
        assert (
            manager.stage_and_activate(bundle, signed(bundle, version), HEALTH).status
            == "activated"
        )
    with closing(sqlite3.connect(database)) as connection, connection:
        for name in ("conversation", "memory", "ledger"):
            connection.execute(f"INSERT INTO {name} VALUES (?)", ("latest-completed",))
    return manager, database


def rows(database: Path) -> dict[str, list[str]]:
    with closing(sqlite3.connect(database)) as connection:
        return {
            name: [row[0] for row in connection.execute(f"SELECT value FROM {name} ORDER BY rowid")]
            for name in ("conversation", "memory", "ledger")
        }


def receipt(manager: ReleaseManager, version: str = "1.0.0") -> Path:
    return manager._root / "manifests" / f"{version}.json"


def assert_rejected(manager: ReleaseManager, database: Path, status: str) -> None:
    pointer = (manager._root / "active.json").read_bytes()
    before = database.read_bytes()
    result = manager.rollback()
    assert result.status == status
    assert result.active_version == "2.0.0"
    assert (manager._root / "active.json").read_bytes() == pointer
    assert database.read_bytes() == before


@pytest.mark.parametrize("wal_writer", [False, True])
def test_code_rollback_keeps_late_conversation_memory_and_completed_ledger(
    releases: tuple[ReleaseManager, Path], wal_writer: bool
) -> None:
    manager, database = releases
    writer = sqlite3.connect(database)
    try:
        if wal_writer:
            assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
            writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO conversation VALUES ('last WAL write')")
        writer.commit()
        expected = rows(database)
        result = manager.rollback()
        assert result.status == "rolled_back" and result.active_version == "1.0.0"
        assert rows(database) == expected
        writer.execute("INSERT INTO memory VALUES ('writer still owns latest DB')")
        writer.commit()
        assert rows(database)["memory"][-1] == "writer still owns latest DB"
        assert rows(database)["ledger"] == ["before", "latest-completed"]
    finally:
        writer.close()


@pytest.mark.parametrize("backup_state", ["missing", "corrupt", "untrusted-path"])
def test_code_rollback_never_needs_or_dereferences_an_old_data_backup(
    releases: tuple[ReleaseManager, Path], backup_state: str
) -> None:
    manager, database = releases
    history = manager._root / "last-known-good.json"
    value = json.loads(history.read_text())
    backup = Path(value["database_backup"])
    if backup_state == "missing":
        backup.unlink()
    elif backup_state == "corrupt":
        backup.write_bytes(b"not a database")
    else:
        value["database_backup"] = str(manager._root / "never-exists.sqlite3")
        history.write_text(json.dumps(value))
    expected = rows(database)
    assert manager.rollback().status == "rolled_back"
    assert rows(database) == expected


@pytest.mark.parametrize("versions", [list(range(1, 10)), list(range(1, 8))])
def test_actual_schema_snapshot_not_constructor_guess_decides_compatibility(
    releases: tuple[ReleaseManager, Path], versions: list[int]
) -> None:
    manager, database = releases
    if len(versions) == 7:
        target = receipt(manager)
        values = json.loads(target.read_text())
        values["min_schema"] = 8
        unsigned = {k: v for k, v in values.items() if k != "signature"}
        wire = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        values["signature"] = hmac.new(KEY, wire, hashlib.sha256).hexdigest()
        target.write_text(json.dumps(values))
    set_schema(database, versions)
    assert_rejected(manager, database, "incompatible_schema")


@pytest.mark.parametrize(
    "metadata",
    ["missing", "empty", "gap", "text", "duplicate", "zero", "float", "overflow", "corrupt"],
)
def test_unknown_actual_schema_fails_closed_without_pointer_or_data_effects(
    releases: tuple[ReleaseManager, Path], metadata: str
) -> None:
    manager, database = releases
    variants: dict[str, list[Any]] = {
        "empty": [],
        "gap": [1, 3],
        "text": [1, "bad"],
        "duplicate": [1, 1],
        "zero": [0, 1],
        "float": [1, 2.5],
        "overflow": list(range(1, 4098)),
    }
    if metadata == "missing":
        with sqlite3.connect(database) as connection:
            connection.execute("DROP TABLE schema_migrations")
    elif metadata == "corrupt":
        database.write_bytes(b"corrupt synthetic fixture")
    else:
        set_schema(database, variants[metadata])
    assert_rejected(manager, database, "schema_unknown")


def test_missing_database_is_not_created_by_code_rollback(
    releases: tuple[ReleaseManager, Path], tmp_path: Path
) -> None:
    manager, _ = releases
    missing = tmp_path / "missing.sqlite3"
    manager._database = missing
    assert manager.rollback().status == "schema_unknown"
    assert not missing.exists()
    assert manager.active_version() == "2.0.0"


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "malformed",
        "legacy",
        "bad-signature",
        "schema-tamper",
        "wrong-version",
        "extra",
        "symlink",
        "hardlink",
        "oversized",
    ],
)
def test_stored_complete_target_approval_is_required_not_a_history_claim(
    releases: tuple[ReleaseManager, Path], tmp_path: Path, kind: str
) -> None:
    manager, database = releases
    target = receipt(manager)
    assert target.is_file(), "stage did not capture a complete signed rollback manifest"
    value = json.loads(target.read_text())
    if kind == "missing":
        target.unlink()
    elif kind == "malformed":
        target.write_text("[")
    elif kind in ("symlink", "hardlink"):
        other = tmp_path / "receipt-copy.json"
        other.write_bytes(target.read_bytes())
        target.unlink()
        if kind == "symlink":
            target.symlink_to(other)
        else:
            target.hardlink_to(other)
    elif kind == "oversized":
        target.write_text(" " * 65537 + json.dumps(value))
    else:
        if kind == "legacy":
            del value["signing_format"]
        elif kind == "bad-signature":
            value["signature"] = "0" * 64
        elif kind == "schema-tamper":
            value["max_schema"] = 100
        elif kind == "wrong-version":
            value["version"] = "0.9.0"
        else:
            value["not-signed"] = True
        target.write_text(json.dumps(value))
    assert_rejected(manager, database, "invalid_rollback_target")


@pytest.mark.parametrize("kind", ["bytes", "symlink", "hardlink"])
def test_target_bytes_and_source_aliases_cannot_bypass_stored_approval(
    releases: tuple[ReleaseManager, Path], tmp_path: Path, kind: str
) -> None:
    manager, database = releases
    target = manager._root / "releases/1.0.0/app.txt"
    if kind == "bytes":
        target.write_text("changed after approval")
    else:
        other = tmp_path / "same-content.txt"
        other.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(other) if kind == "symlink" else target.hardlink_to(other)
    assert_rejected(manager, database, "invalid_rollback_target")


@pytest.mark.parametrize(
    "value",
    [
        [],
        None,
        {"version": "../outside"},
        {"version": True},
        {"version": "1.0.0", "unexpected": "authority"},
    ],
)
def test_malformed_history_has_no_path_or_data_authority(
    releases: tuple[ReleaseManager, Path], value: Any
) -> None:
    manager, database = releases
    (manager._root / "last-known-good.json").write_text(json.dumps(value))
    assert_rejected(manager, database, "invalid_rollback_target")


def test_interrupted_code_pointer_write_retains_current_pointer_and_latest_data(
    releases: tuple[ReleaseManager, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, database = releases
    expected = rows(database)

    def interrupted(*args: Any, **kwargs: Any) -> None:
        raise OSError("controlled pointer-write failure")

    monkeypatch.setattr(manager, "_atomic_json", interrupted)
    with pytest.raises(OSError, match="pointer-write"):
        manager.rollback()
    assert manager.active_version() == "2.0.0"
    assert rows(database) == expected


def test_rollback_runs_no_healthcheck_backup_restore_or_effect_replay(
    releases: tuple[ReleaseManager, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, database = releases
    expected = rows(database)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("code rollback reached a forbidden effect")

    monkeypatch.setattr(manager, "_backup_database", forbidden)
    monkeypatch.setattr(manager, "_restore_database", forbidden, raising=False)
    monkeypatch.setattr("siro.core.releases.subprocess.run", forbidden)
    assert manager.rollback().status == "rolled_back"
    assert rows(database) == expected


@pytest.mark.parametrize("collision", ["release", "manifest"])
def test_published_version_cannot_be_overwritten_and_has_zero_release_effects(
    releases: tuple[ReleaseManager, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    collision: str,
) -> None:
    manager, database = releases
    version = "1.0.0" if collision == "release" else "3.0.0"
    if collision == "manifest":
        target = receipt(manager, version)
        target.parent.mkdir(exist_ok=True)
        target.write_text("unresolved existing receipt")
    bundle = bundle_at(tmp_path, "replacement")
    before = {
        str(p.relative_to(manager._root)): p.read_bytes()
        for p in manager._root.rglob("*")
        if p.is_file()
    }
    expected = rows(database)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("existing version reached a release effect")

    monkeypatch.setattr(manager, "_backup_database", forbidden)
    monkeypatch.setattr("siro.core.releases.subprocess.run", forbidden)
    assert (
        manager.stage_and_activate(bundle, signed(bundle, version), HEALTH).status
        == "release_version_exists"
    )
    assert {
        str(p.relative_to(manager._root)): p.read_bytes()
        for p in manager._root.rglob("*")
        if p.is_file()
    } == before
    assert rows(database) == expected


def test_manifest_save_failure_never_publishes_an_unverifiable_release(
    releases: tuple[ReleaseManager, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, database = releases
    bundle = bundle_at(tmp_path, "third")
    original = manager._atomic_json
    expected = rows(database)
    history = (manager._root / "last-known-good.json").read_bytes()

    def fail_receipt(path: Path, value: Any) -> None:
        if path.parent.name == "manifests":
            raise OSError("controlled receipt-save failure")
        original(path, value)

    monkeypatch.setattr(manager, "_atomic_json", fail_receipt)
    with pytest.raises(OSError, match="receipt-save"):
        manager.stage_and_activate(bundle, signed(bundle, "3.0.0"), HEALTH)
    assert manager.active_version() == "2.0.0"
    assert (manager._root / "last-known-good.json").read_bytes() == history
    assert rows(database) == expected


def test_actual_cli_code_rollback_preserves_new_rows_in_real_migrated_temp_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database = tmp_path / "actual.sqlite3"
    store = SQLiteStore(database)
    asyncio.run(store.initialize())
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("CREATE TABLE acceptance(value TEXT)")
        connection.execute("INSERT INTO acceptance VALUES ('original')")
    manager_root = tmp_path / "cli-manager"
    monkeypatch.setenv("SIRO_TEST_D48_RELEASE_KEY", KEY.decode())
    prefix = [
        "release",
        "--release-root",
        str(manager_root),
        "--database",
        str(database),
        "--key-env",
        "SIRO_TEST_D48_RELEASE_KEY",
    ]
    for name, version in (("cli-first", "1.0.0"), ("cli-second", "2.0.0")):
        bundle = bundle_at(tmp_path, name)
        manifest_path = tmp_path / f"{name}.json"
        manifest_path.write_text(
            signed(bundle, version, maximum=len(load_migrations())).model_dump_json()
        )
        assert (
            main(
                [
                    *prefix,
                    "stage",
                    "--bundle",
                    str(bundle),
                    "--manifest",
                    str(manifest_path),
                    "--healthcheck",
                    json.dumps(HEALTH),
                ]
            )
            == 0
        )
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("INSERT INTO acceptance VALUES ('new conversation remains')")
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 0
    assert main([*prefix, "rollback"]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {
        "status": "rolled_back",
        "active_version": "1.0.0",
    }
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT value FROM acceptance ORDER BY rowid").fetchall() == [
            ("original",),
            ("new conversation remains",),
        ]


def test_no_database_code_rollback_retains_trusted_caller_schema_compatibility(
    tmp_path: Path,
) -> None:
    manager = ReleaseManager(tmp_path / "manager", KEY, current_schema=8)
    for name, version in (("first", "1.0.0"), ("second", "2.0.0")):
        bundle = bundle_at(tmp_path, name)
        assert (
            manager.stage_and_activate(bundle, signed(bundle, version), HEALTH).status
            == "activated"
        )
    assert manager.rollback().status == "rolled_back"


def test_staging_healthcheck_cannot_mutate_the_signed_rollback_source(tmp_path: Path) -> None:
    manager = ReleaseManager(tmp_path / "manager", KEY, current_schema=8)
    bundle = bundle_at(tmp_path, "candidate")
    check = (sys.executable, "-c", "open('app.txt', 'w').write('changed by healthcheck')")
    result = manager.stage_and_activate(bundle, signed(bundle, "1.0.0"), check)
    assert result.status == "invalid_manifest"
    assert manager.active_version() is None
    assert not receipt(manager).exists()


@pytest.mark.parametrize("kind", ["directory-symlink", "manifest-parent-symlink", "duplicate-json"])
def test_target_record_and_parent_aliases_do_not_gain_rollback_authority(
    releases: tuple[ReleaseManager, Path], tmp_path: Path, kind: str
) -> None:
    manager, database = releases
    if kind == "directory-symlink":
        target = manager._root / "releases/1.0.0"
        target.rename(tmp_path / "relocated-release")
        target.symlink_to(tmp_path / "relocated-release", target_is_directory=True)
    elif kind == "manifest-parent-symlink":
        parent = manager._root / "manifests"
        parent.rename(tmp_path / "relocated-receipts")
        parent.symlink_to(tmp_path / "relocated-receipts", target_is_directory=True)
    else:
        target = receipt(manager)
        raw = target.read_text()
        target.write_text('{"version":"wrong",' + raw[1:])
    assert_rejected(manager, database, "invalid_rollback_target")


def test_actual_schema_connection_is_readonly_and_explicitly_closed(
    releases: tuple[ReleaseManager, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, database = releases
    original = sqlite3.connect
    connections: list[sqlite3.Connection] = []

    def connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        assert args[0] == database.resolve().as_uri() + "?mode=ro"
        assert kwargs["uri"] is True
        connection: sqlite3.Connection = original(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr("siro.core.releases.sqlite3.connect", connect)
    assert manager.rollback().status == "rolled_back"
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")


@pytest.mark.parametrize("schema", [0, -1, True])
def test_invalid_trusted_caller_schema_does_not_authorize_code_rollback(
    releases: tuple[ReleaseManager, Path], schema: int
) -> None:
    manager, database = releases
    manager._schema = schema
    assert_rejected(manager, database, "schema_unknown")


def test_database_symlink_is_not_followed_by_the_schema_snapshot(
    releases: tuple[ReleaseManager, Path], tmp_path: Path
) -> None:
    manager, database = releases
    alias = tmp_path / "aliased.sqlite3"
    alias.symlink_to(database)
    manager._database = alias
    assert_rejected(manager, database, "schema_unknown")
