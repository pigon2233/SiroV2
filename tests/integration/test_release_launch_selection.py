from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import stat
import subprocess
from collections.abc import Callable
from contextlib import closing
from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path
from typing import cast

import pytest

import siro.core.releases as release_module
from siro.core.releases import ReleaseManager

KEY = b"synthetic-d52-selection-key"  # pragma: allowlist secret
REQUIRED_FILES = (
    "src/siro/__init__.py",
    "src/siro/core/releases.py",
    "src/siro/services/presentation/gateway.py",
)


@dataclass(frozen=True)
class SelectionFixture:
    manager: ReleaseManager
    root: Path
    database: Path
    configuration: Path


def source_digest(directory: Path) -> str:
    """Independent implementation of the framed v2 source tree byte format."""
    files = sorted(path for path in directory.rglob("*") if path.is_file())
    wire = bytearray(b"siro-release-source-v2\0")
    wire.extend(len(files).to_bytes(8, "big"))
    for path in files:
        relative = path.relative_to(directory).as_posix().encode("utf-8")
        content = path.read_bytes()
        wire.extend(len(relative).to_bytes(8, "big"))
        wire.extend(relative)
        wire.extend(len(content).to_bytes(8, "big"))
        wire.extend(content)
    return hashlib.sha256(wire).hexdigest()


def set_schema(database: Path, versions: list[object]) -> None:
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("DROP TABLE IF EXISTS schema_migrations")
        connection.execute("CREATE TABLE schema_migrations(version)")
        connection.executemany("INSERT INTO schema_migrations VALUES (?)", [(n,) for n in versions])


def write_receipt(
    root: Path,
    version: str,
    *,
    minimum: int = 1,
    maximum: int = 8,
    values: dict[str, object] | None = None,
) -> dict[str, object]:
    unsigned: dict[str, object] = {
        "version": version,
        "source_sha256": source_digest(root / "releases" / version),
        "min_schema": minimum,
        "max_schema": maximum,
        "signing_format": "siro-release-manifest-v2",
    }
    if values is not None:
        unsigned.update(values)
    unsigned.pop("signature", None)
    payload = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    signed = {**unsigned, "signature": hmac.new(KEY, payload, hashlib.sha256).hexdigest()}
    path = root / "manifests" / f"{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(signed), encoding="utf-8")
    return signed


@pytest.fixture
def selection(tmp_path: Path) -> SelectionFixture:
    root = tmp_path / "synthetic-releases"
    root.mkdir()
    for version in ("1.0.0", "2.0.0"):
        target = root / "releases" / version
        for relative in REQUIRED_FILES:
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# synthetic signed source for {version}: {relative}\n")
        (target / "ordinary-data.txt").write_text(f"signed extra bytes for {version}")
        write_receipt(root, version)
    (root / "active.json").write_text('{"version":"2.0.0"}')
    (root / "last-known-good.json").write_text('{"version":"1.0.0"}')
    backup = root / "backups" / "before-2.0.0.sqlite3"
    backup.parent.mkdir()
    backup.write_bytes(b"historical backup must never be opened by launch selection")
    database = tmp_path / "synthetic.sqlite3"
    with closing(sqlite3.connect(database)) as connection, connection:
        for table in ("conversation", "memory", "ledger"):
            connection.execute(f"CREATE TABLE {table}(value TEXT)")
            connection.execute(f"INSERT INTO {table} VALUES (?)", ("latest completed data",))
    set_schema(database, list(range(1, 9)))
    configuration = tmp_path / "synthetic-config.json"
    configuration.write_text('{"synthetic": "preserve this configuration"}')
    manager = ReleaseManager(root, KEY, current_schema=8, database=database)
    return SelectionFixture(manager, root, database, configuration)


def tree_snapshot(root: Path) -> dict[str, tuple[int, bytes | str | None]]:
    result: dict[str, tuple[int, bytes | str | None]] = {}
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        content: bytes | str | None = None
        if stat.S_ISLNK(mode):
            content = os.readlink(path)
        elif stat.S_ISREG(mode):
            content = path.read_bytes()
        result[str(path.relative_to(root))] = (stat.S_IFMT(mode), content)
    return result


def resolve_without_effects(selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch) -> object:
    resolver = getattr(selection.manager, "resolve_launch_target", None)
    assert callable(resolver), "D52 requires ReleaseManager.resolve_launch_target"
    before_tree = tree_snapshot(selection.root)
    before_database = selection.database.read_bytes() if selection.database.exists() else None
    before_configuration = selection.configuration.read_bytes()
    calls: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> object:
        calls.append("release effect")
        raise AssertionError("read-only launch selection reached a release effect")

    with monkeypatch.context() as controlled:
        controlled.setattr(selection.manager, "_atomic_json", forbidden)
        controlled.setattr(selection.manager, "_backup_database", forbidden)
        controlled.setattr(selection.manager, "stage_and_activate", forbidden)
        controlled.setattr(selection.manager, "rollback", forbidden)
        controlled.setattr(shutil, "copytree", forbidden)
        controlled.setattr(subprocess, "run", forbidden)
        try:
            return cast(Callable[[], object], resolver)()
        finally:
            assert calls == []
            assert tree_snapshot(selection.root) == before_tree
            assert selection.configuration.read_bytes() == before_configuration
            if before_database is None:
                assert not selection.database.exists()
            else:
                assert selection.database.read_bytes() == before_database


def expect_error(selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    error_type = getattr(release_module, "ReleaseLaunchError", None)
    assert isinstance(error_type, type) and issubclass(error_type, Exception), (
        "D52 requires a typed ReleaseLaunchError"
    )
    with pytest.raises(error_type) as captured:
        resolve_without_effects(selection, monkeypatch)
    assert getattr(captured.value, "status", None) == status
    assert str(selection.root) not in str(captured.value)
    assert str(selection.database) not in str(captured.value)
    assert KEY.decode() not in str(captured.value)


@pytest.mark.parametrize("version", ["1.0.0", "2.0.0"])
def test_resolves_exact_signed_active_version_with_immutable_canonical_identity(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    (selection.root / "active.json").write_text(json.dumps({"version": version}))
    result = resolve_without_effects(selection, monkeypatch)
    target = selection.root / "releases" / version
    assert getattr(result, "version", None) == version
    assert getattr(result, "source_sha256", None) == source_digest(target)
    assert getattr(result, "directory", None) == target.resolve()
    assert getattr(result, "schema_version", None) == 8
    verified_type = getattr(release_module, "VerifiedRelease", None)
    assert isinstance(verified_type, type) and isinstance(result, verified_type)
    attribute = "version"
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        setattr(result, attribute, "9.9.9")


def test_selecting_signed_code_keeps_latest_wal_data_and_existing_writer(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = sqlite3.connect(selection.database)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO conversation VALUES ('latest WAL conversation')")
        writer.execute("INSERT INTO memory VALUES ('latest WAL memory')")
        writer.execute("INSERT INTO ledger VALUES ('latest completed WAL action')")
        writer.commit()
        wal = selection.database.with_name(selection.database.name + "-wal")
        wal_before = wal.read_bytes()
        resolve_without_effects(selection, monkeypatch)
        assert wal.read_bytes() == wal_before
        for table in ("conversation", "memory", "ledger"):
            assert writer.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 2
        writer.execute("INSERT INTO memory VALUES ('original writer remains usable')")
        writer.commit()
        assert writer.execute("SELECT count(*) FROM memory").fetchone()[0] == 3
    finally:
        writer.close()


def test_no_pointer_does_not_fallback_to_last_known_good_or_workspace(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    (selection.root / "active.json").unlink()
    expect_error(selection, monkeypatch, "no_active_release")


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        "null",
        "{}",
        '{"version":null}',
        '{"version":true}',
        '{"version":2}',
        '{"version":""}',
        '{"version":"v2.0.0"}',
        '{"version":"2.0"}',
        '{"version":"../2.0.0"}',
        '{"version":"/tmp/synthetic-target"}',
        '{"version":"2.0.0/.."}',
        '{"version":"2.0.0","extra":1}',
        '{"version":"1.0.0","version":"2.0.0"}',
        '{"version":"2.0.0"}' + " " * 65536,
    ],
)
def test_malformed_active_record_is_rejected_without_fallback(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    (selection.root / "active.json").write_text(raw)
    expect_error(selection, monkeypatch, "invalid_active_release")


@pytest.mark.parametrize("alias", ["symlink", "hardlink", "directory"])
def test_active_record_must_be_a_bounded_ordinary_unaliased_file(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, alias: str
) -> None:
    active = selection.root / "active.json"
    original = selection.root / "synthetic-pointer-target.json"
    active.rename(original)
    if alias == "symlink":
        active.symlink_to(original)
    elif alias == "hardlink":
        os.link(original, active)
    else:
        active.mkdir()
    expect_error(selection, monkeypatch, "invalid_active_release")


@pytest.mark.parametrize("missing", ["release", "receipt", *REQUIRED_FILES])
def test_missing_signed_target_or_required_runtime_file_is_rejected(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    target = selection.root / "releases" / "2.0.0"
    if missing == "release":
        shutil.rmtree(target)
    elif missing == "receipt":
        (selection.root / "manifests" / "2.0.0.json").unlink()
    else:
        (target / missing).unlink()
        write_receipt(selection.root, "2.0.0")
    expect_error(selection, monkeypatch, "invalid_release_target")


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "digest",
        "signature",
        "version",
        "unsigned-range",
        "legacy",
        "null-format",
        "extra",
    ],
)
def test_full_signed_receipt_and_actual_source_bytes_are_required(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    receipt = selection.root / "manifests" / "2.0.0.json"
    values = json.loads(receipt.read_text())
    if change == "source":
        (selection.root / "releases" / "2.0.0" / "ordinary-data.txt").write_text("tampered bytes")
    elif change == "digest":
        values["source_sha256"] = "0" * 64
    elif change == "signature":
        values["signature"] = "0" * 64
    elif change == "version":
        write_receipt(selection.root, "2.0.0", values={"version": "1.0.0"})
    elif change == "unsigned-range":
        values["max_schema"] = 4096
    elif change == "legacy":
        values.pop("signing_format")
    elif change == "null-format":
        values["signing_format"] = None
    else:
        values["unexpected"] = "not part of the signed contract"
    if change not in {"source", "version"}:
        receipt.write_text(json.dumps(values))
    expect_error(selection, monkeypatch, "invalid_release_target")


@pytest.mark.parametrize("record", ["duplicate", "array", "oversized", "symlink", "hardlink"])
def test_receipt_records_are_strict_bounded_and_unaliased(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, record: str
) -> None:
    receipt = selection.root / "manifests" / "2.0.0.json"
    if record == "duplicate":
        raw = receipt.read_text()
        receipt.write_text(raw[:-1] + ',"version":"2.0.0"}')
    elif record == "array":
        receipt.write_text("[]")
    elif record == "oversized":
        receipt.write_text(receipt.read_text() + " " * 65536)
    else:
        original = selection.root / "synthetic-receipt-target.json"
        receipt.rename(original)
        if record == "symlink":
            receipt.symlink_to(original)
        else:
            os.link(original, receipt)
    expect_error(selection, monkeypatch, "invalid_release_target")


@pytest.mark.parametrize("alias", ["release", "releases-parent", "source-file", "source-directory"])
def test_signed_source_symlink_aliases_are_rejected_even_with_matching_digest(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, alias: str
) -> None:
    target = selection.root / "releases" / "2.0.0"
    if alias == "release":
        actual = selection.root / "synthetic-release-alias"
        target.rename(actual)
        target.symlink_to(actual, target_is_directory=True)
    elif alias == "releases-parent":
        actual = selection.root / "synthetic-releases-alias"
        target.parent.rename(actual)
        target.parent.symlink_to(actual, target_is_directory=True)
    elif alias == "source-file":
        path = target / "ordinary-data.txt"
        actual = selection.root / "synthetic-source-alias.txt"
        path.rename(actual)
        path.symlink_to(actual)
    else:
        path = target / "src" / "siro" / "core"
        actual = selection.root / "synthetic-core-alias"
        path.rename(actual)
        path.symlink_to(actual, target_is_directory=True)
        write_receipt(selection.root, "2.0.0")
    expect_error(selection, monkeypatch, "invalid_release_target")


def test_constructor_root_symlink_is_rejected_instead_of_selecting_an_alias(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    alias = selection.root.parent / "synthetic-manager-alias"
    alias.symlink_to(selection.root, target_is_directory=True)
    manager = ReleaseManager(alias, KEY, current_schema=8, database=selection.database)
    aliased = SelectionFixture(manager, selection.root, selection.database, selection.configuration)
    expect_error(aliased, monkeypatch, "invalid_release_target")


@pytest.mark.parametrize("node", ["hardlink", "fifo"])
def test_source_special_or_multiply_linked_files_are_rejected(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, node: str
) -> None:
    target = selection.root / "releases" / "2.0.0"
    path = target / "ordinary-data.txt"
    if node == "hardlink":
        os.link(path, selection.root / "synthetic-hardlinked-source.txt")
    else:
        os.mkfifo(target / "synthetic-special-node")
    expect_error(selection, monkeypatch, "invalid_release_target")


@pytest.mark.parametrize(
    "versions", [[], [1, 3], [1, 1], [0, 1], [1, -1], ["1"], [1.0], [None], list(range(1, 4098))]
)
def test_actual_schema_must_be_a_known_bounded_integer_prefix(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, versions: list[object]
) -> None:
    set_schema(selection.database, versions)
    expect_error(selection, monkeypatch, "schema_unknown")


@pytest.mark.parametrize("state", ["missing", "corrupt", "no-ledger", "no-database", "symlink"])
def test_missing_or_unknown_actual_database_never_uses_constructor_schema_guess(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    if state == "missing":
        selection.database.unlink()
    elif state == "corrupt":
        selection.database.write_bytes(b"synthetic bytes that are not sqlite")
    elif state == "no-ledger":
        with closing(sqlite3.connect(selection.database)) as connection, connection:
            connection.execute("DROP TABLE schema_migrations")
    elif state == "symlink":
        actual = selection.database.with_name("synthetic-database-alias.sqlite3")
        selection.database.rename(actual)
        selection.database.symlink_to(actual)
    else:
        manager = ReleaseManager(selection.root, KEY, current_schema=8)
        selection = SelectionFixture(
            manager, selection.root, selection.database, selection.configuration
        )
    expect_error(selection, monkeypatch, "schema_unknown")


@pytest.mark.parametrize("schema", [0, -1, True, "8", None])
def test_invalid_supported_schema_configuration_is_unknown(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, schema: object
) -> None:
    manager = ReleaseManager(
        selection.root, KEY, current_schema=cast(int, schema), database=selection.database
    )
    invalid = SelectionFixture(manager, selection.root, selection.database, selection.configuration)
    expect_error(invalid, monkeypatch, "schema_unknown")


@pytest.mark.parametrize("actual_schema", [3, 9])
def test_known_actual_schema_requires_signed_bounds_and_supported_runtime(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch, actual_schema: int
) -> None:
    set_schema(selection.database, list(range(1, actual_schema + 1)))
    write_receipt(selection.root, "2.0.0", minimum=4, maximum=9)
    expect_error(selection, monkeypatch, "incompatible_schema")


def test_actual_schema_compatibility_is_not_replaced_by_constructor_guess(
    selection: SelectionFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_schema(selection.database, [1, 2, 3])
    write_receipt(selection.root, "2.0.0", minimum=2, maximum=3)
    result = resolve_without_effects(selection, monkeypatch)
    assert getattr(result, "schema_version", None) == 3
    assert getattr(result, "version", None) == "2.0.0"
