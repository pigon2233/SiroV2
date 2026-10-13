from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import threading
import zipfile
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import pytest

from siro.cli import main
from siro.config import SiroSettings
from siro.persistence import sqlite as persistence
from siro.persistence.sqlite import Migration, MigrationError, SQLiteStore, apply_migrations


def seed(path: Path, value: str, *, version: int | None = None) -> None:
    migrations = persistence.load_migrations()
    with closing(sqlite3.connect(path)) as connection, connection:
        apply_migrations(connection, migrations if version is None else migrations[:version])
        for table in ("acceptance_conversation", "acceptance_memory", "acceptance_ledger"):
            connection.execute(f"CREATE TABLE {table}(value TEXT)")
            connection.execute(f"INSERT INTO {table} VALUES (?)", (value,))
        if version is None:
            connection.execute(
                "INSERT INTO inbox(consumer_id,event_id,processed_at) VALUES (?,?,?)",
                ("completed-effect", value, "synthetic"),
            )


def snapshot(path: Path) -> tuple[str, ...]:
    with closing(sqlite3.connect(path)) as connection:
        return tuple(connection.iterdump())


def values(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        return [row[0] for row in connection.execute("SELECT value FROM acceptance_conversation")]


def damage_metadata(path: Path, kind: str) -> None:
    with closing(sqlite3.connect(path)) as connection, connection:
        if kind in {"checksum", "name"}:
            connection.execute(f"UPDATE schema_migrations SET {kind}='modified' WHERE version=1")
        elif kind == "gap":
            connection.execute("DELETE FROM schema_migrations WHERE version=2")
        elif kind == "future":
            connection.execute(
                "INSERT INTO schema_migrations VALUES (999,'future','unknown','synthetic')"
            )
        else:
            rows = list(connection.execute("SELECT * FROM schema_migrations ORDER BY version"))
            connection.execute("DROP TABLE schema_migrations")
            connection.execute(
                "CREATE TABLE schema_migrations(version, name TEXT, checksum TEXT, applied_at TEXT)"
            )
            bad_version: object = {
                "negative": -1,
                "string": "1",
                "fraction": 1.5,
                "null": None,
            }.get(kind, rows[0][0])
            rows[0] = (bad_version, *rows[0][1:])
            if kind == "duplicate":
                rows.append(rows[0])
            connection.executemany("INSERT INTO schema_migrations VALUES (?,?,?,?)", rows)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    ["checksum", "name", "gap", "future", "negative", "string", "fraction", "null", "duplicate"],
)
async def test_rejected_metadata_keeps_entire_latest_database_and_source(
    tmp_path: Path, kind: str
) -> None:
    live, source = tmp_path / "latest.db", tmp_path / "old.db"
    seed(live, "latest-completed")
    seed(source, "old-snapshot")
    damage_metadata(source, kind)
    latest = snapshot(live)
    source_bytes = source.read_bytes()
    store = SQLiteStore(live)

    with pytest.raises(MigrationError):
        await store.restore_from(source)

    assert snapshot(live) == latest
    assert source.read_bytes() == source_bytes
    assert await store.integrity_check() == "ok"
    assert (
        await store.run_transaction(lambda connection: connection.execute("SELECT 1").fetchone()[0])
        == 1
    )


@pytest.mark.asyncio
async def test_migration_sql_failure_after_one_upgrade_never_reaches_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live, source = tmp_path / "latest.db", tmp_path / "old.db"
    seed(live, "latest-completed")
    seed(source, "old-snapshot", version=1)
    latest, source_bytes = snapshot(live), source.read_bytes()
    migrations = persistence.load_migrations()
    failed = Migration(3, "synthetic-failure", "INSERT INTO missing_table VALUES (1)", "synthetic")
    monkeypatch.setattr(persistence, "load_migrations", lambda: (*migrations[:2], failed))

    with pytest.raises(sqlite3.OperationalError, match="missing_table"):
        await SQLiteStore(live).restore_from(source)

    assert snapshot(live) == latest
    assert source.read_bytes() == source_bytes


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [0, 1, 3, 10, 12, 13])
async def test_successful_explicit_restore_upgrades_candidate_and_keeps_backup_unchanged(
    tmp_path: Path, version: int
) -> None:
    live, source = tmp_path / "latest.db", tmp_path / "backup with ? and #.db"
    seed(live, "latest-completed")
    seed(source, "old-snapshot", version=version)
    source_bytes, source_mode = source.read_bytes(), source.stat().st_mode
    store = SQLiteStore(live)

    await store.restore_from(source)

    assert values(live) == ["old-snapshot"]
    assert source.read_bytes() == source_bytes and source.stat().st_mode == source_mode
    with closing(sqlite3.connect(live)) as connection:
        assert list(
            connection.execute("SELECT version FROM schema_migrations ORDER BY version")
        ) == [(migration.version,) for migration in persistence.load_migrations()]
    assert await store.integrity_check() == "ok"
    await store.run_transaction(
        lambda connection: connection.execute(
            "INSERT INTO acceptance_memory VALUES ('post-restore')"
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["missing", "corrupt", "checksum"])
async def test_invalid_source_never_creates_target_directory(tmp_path: Path, kind: str) -> None:
    source, live = tmp_path / "backup.db", tmp_path / "untouched" / "latest.db"
    if kind == "corrupt":
        source.write_bytes(b"synthetic invalid sqlite")
    elif kind == "checksum":
        seed(source, "old-snapshot")
        damage_metadata(source, kind)
    error = FileNotFoundError if kind == "missing" else (sqlite3.DatabaseError, MigrationError)

    with pytest.raises(error):
        await SQLiteStore(live).restore_from(source)

    assert not live.parent.exists()


@pytest.mark.asyncio
async def test_committed_source_wal_is_read_and_existing_live_writer_survives(
    tmp_path: Path,
) -> None:
    live, source = tmp_path / "latest.db", tmp_path / "old.db"
    seed(live, "latest-completed")
    seed(source, "old-snapshot", version=1)
    with (
        closing(sqlite3.connect(live)) as writer,
        closing(sqlite3.connect(source)) as backup_writer,
    ):
        for connection in (writer, backup_writer):
            assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
            connection.execute("PRAGMA wal_autocheckpoint=0")
        backup_writer.execute("INSERT INTO acceptance_conversation VALUES ('committed-source-WAL')")
        backup_writer.commit()
        before = snapshot(source)

        await SQLiteStore(live).restore_from(source)

        assert values(live) == ["old-snapshot", "committed-source-WAL"]
        assert snapshot(source) == before
        writer.execute("INSERT INTO acceptance_conversation VALUES ('writer-remains-usable')")
        writer.commit()
        assert values(live)[-1] == "writer-remains-usable"
        assert writer.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


@pytest.mark.asyncio
async def test_same_database_source_is_captured_before_promotion(tmp_path: Path) -> None:
    live = tmp_path / "latest.db"
    seed(live, "latest-completed")
    before = snapshot(live)

    await asyncio.wait_for(SQLiteStore(live).restore_from(live), timeout=3)

    assert snapshot(live) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("wal", [False, True])
async def test_cancel_during_unfinished_sqlite_copy_rolls_back_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wal: bool
) -> None:
    live, source = tmp_path / "latest.db", tmp_path / "old.db"
    seed(live, "latest-completed")
    seed(source, "old-snapshot")
    with closing(sqlite3.connect(source)) as connection, connection:
        connection.execute("CREATE TABLE fixture_pages(value BLOB)")
        connection.execute("INSERT INTO fixture_pages VALUES (zeroblob(1048576))")
    if wal:
        with closing(sqlite3.connect(live)) as connection:
            assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    latest = snapshot(live)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    class InterruptibleConnection(sqlite3.Connection):
        def backup(
            self,
            target: sqlite3.Connection,
            *,
            pages: int = -1,
            progress: Callable[[int, int, int], object] | None = None,
            name: str = "main",
            sleep: float = 0.250,
        ) -> None:
            def on_progress(status: int, remaining: int, total: int) -> None:
                if status == sqlite3.SQLITE_OK and remaining > 0 and not entered.is_set():
                    entered.set()
                    assert release.wait(3), "synthetic SQLite copy release missing"
                if progress is not None:
                    progress(status, remaining, total)

            try:
                super().backup(target, pages=64, progress=on_progress, name=name, sleep=sleep)
            finally:
                finished.set()

    store = SQLiteStore(live)
    original = store._connect

    def connect(path: Path | None = None) -> sqlite3.Connection:
        if path is not None and path != live:
            return sqlite3.connect(path, factory=InterruptibleConnection)
        return original(path)

    monkeypatch.setattr(store, "_connect", connect)
    restore = asyncio.create_task(store.restore_from(source))
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.002)
        restore.cancel()
        await asyncio.sleep(0.01)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(restore, 2)
        async with asyncio.timeout(2):
            while not finished.is_set():
                await asyncio.sleep(0.002)
        assert snapshot(live) == latest
    finally:
        release.set()
        await asyncio.gather(restore, return_exceptions=True)
        async with asyncio.timeout(2):
            while not finished.is_set():
                await asyncio.sleep(0.002)


@pytest.mark.asyncio
async def test_target_open_failure_keeps_latest_database_and_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live, source = tmp_path / "latest.db", tmp_path / "old.db"
    seed(live, "latest-completed")
    seed(source, "old-snapshot")
    latest, source_before = snapshot(live), source.read_bytes()
    store = SQLiteStore(live)
    original = store._connect

    def connect(path: Path | None = None) -> sqlite3.Connection:
        if path is None:
            raise PermissionError("synthetic denied target")
        return original(path)

    monkeypatch.setattr(store, "_connect", connect)
    with pytest.raises(PermissionError, match="denied target"):
        await store.restore_from(source)
    assert snapshot(live) == latest and source.read_bytes() == source_before


@pytest.mark.parametrize("kind", ["checksum", "future"])
@pytest.mark.parametrize("bundle", [False, True])
@pytest.mark.parametrize("existing_target", [False, True])
def test_raw_and_zip_cli_reject_before_latest_db_or_config_changes(
    tmp_path: Path, kind: str, bundle: bool, existing_target: bool
) -> None:
    data, source = tmp_path / "target", tmp_path / "backup.db"
    config = tmp_path / "target-config.json"
    config.write_text(SiroSettings().model_dump_json())
    config_before = config.read_bytes()
    if existing_target:
        data.mkdir()
        seed(data / "siro.db", "latest-completed")
    latest = snapshot(data / "siro.db") if existing_target else None
    seed(source, "old-snapshot")
    damage_metadata(source, kind)
    source_before = source.read_bytes()
    arguments = ["restore", "--data", str(data)]
    if bundle:
        archive_path = tmp_path / "backup.zip"
        content = {
            "siro.db": source.read_bytes(),
            "config.json": SiroSettings().model_dump_json().encode(),
        }
        manifest = {
            "format": 1,
            "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in content.items()},
        }
        with zipfile.ZipFile(archive_path, "w") as archive:
            for name, raw in content.items():
                archive.writestr(name, raw)
            archive.writestr("manifest.json", json.dumps(manifest))
        arguments.extend(["--config", str(config), str(archive_path)])
    else:
        arguments.append(str(source))

    with pytest.raises(MigrationError):
        main(arguments)

    if latest is not None:
        assert snapshot(data / "siro.db") == latest
    else:
        assert not data.exists()
    assert source.read_bytes() == source_before
    assert config.read_bytes() == config_before
