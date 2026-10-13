from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import threading
from collections.abc import Callable
from contextlib import closing
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import pytest

from siro.config import SiroSettings
from siro.operations import create_backup_bundle
from siro.persistence.sqlite import SQLiteStore, apply_migrations, load_migrations


async def _wait(event: threading.Event) -> None:
    async with asyncio.timeout(3):
        while not event.is_set():
            await asyncio.sleep(0.002)


def _database(tmp_path: Path) -> SQLiteStore:
    path = tmp_path / "source.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        apply_migrations(connection, load_migrations())
        connection.execute("CREATE TABLE backup_fixture(value TEXT NOT NULL)")
        connection.execute("INSERT INTO backup_fixture VALUES ('source-snapshot')")
        connection.commit()
    return SQLiteStore(path)


def _value(path: Path) -> str:
    with closing(sqlite3.connect(path)) as connection:
        return str(connection.execute("SELECT value FROM backup_fixture").fetchone()[0])


class _BackupPause:
    """Control only timing around actual SQLite work; never substitute a fake copy."""

    def __init__(
        self,
        store: SQLiteStore,
        monkeypatch: pytest.MonkeyPatch,
        *,
        after_copy: bool = False,
        failure: BaseException | None = None,
    ) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.paths: list[Path] = []
        self.thread_ids: list[int] = []
        original = store._backup_sync

        def copy(destination: Path, cancelled: threading.Event | None) -> None:
            if cancelled is None:
                original(destination)
            else:
                original(destination, cancelled)

        def backup(destination: Path, cancelled: threading.Event | None = None) -> None:
            self.paths.append(destination)
            self.thread_ids.append(threading.get_ident())
            try:
                if after_copy:
                    copy(destination, cancelled)
                self.entered.set()
                assert self.release.wait(4), "synthetic backup release missing"
                if failure is not None:
                    raise failure
                if not after_copy:
                    copy(destination, cancelled)
            finally:
                self.finished.set()

        monkeypatch.setattr(store, "_backup_sync", backup)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellations", [1, 3])
async def test_cancelled_backup_keeps_writer_owner_until_real_copy_finishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancellations: int
) -> None:
    store = _database(tmp_path)
    destination = tmp_path / "snapshot.db"
    pause = _BackupPause(store, monkeypatch)
    backup = asyncio.create_task(store.backup_to(destination))
    writes: list[str] = []

    def write(connection: sqlite3.Connection) -> None:
        writes.append("queued")
        connection.execute("UPDATE backup_fixture SET value='queued-write'")

    queued: asyncio.Task[None] | None = None
    try:
        await _wait(pause.entered)
        assert len(pause.thread_ids) == 1, "a canceled copy must not be implicitly retried"
        assert pause.thread_ids[0] != threading.get_ident(), "SQLite work must remain off-loop"
        queued = asyncio.create_task(store.run_transaction(write))
        await asyncio.sleep(0.01)
        assert not queued.done()
        for _ in range(cancellations):
            backup.cancel()
            await asyncio.sleep(0.01)
        assert not backup.done(), "cancelled caller must wait for its actual backup work"
        assert store._writer_lock.locked()
        assert not queued.done() and writes == [], "queued writer must not overtake backup"
        pause.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(backup, 3)
        await asyncio.wait_for(queued, 3)
        assert pause.finished.is_set()
        assert not destination.exists(), "known cancellation before copy must not publish output"
        assert _value(store.path) == "queued-write" and writes == ["queued"]
        assert not store._writer_lock.locked()
    finally:
        pause.release.set()
        if queued is not None and not queued.done():
            queued.cancel()
        await asyncio.gather(backup, *([queued] if queued else []), return_exceptions=True)
        await _wait(pause.finished)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellations", [1, 3])
async def test_cancelled_zip_backup_keeps_staging_until_join_then_removes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancellations: int
) -> None:
    store = _database(tmp_path)
    staging_root = tmp_path / "staging"
    staging_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(staging_root))
    config = tmp_path / "settings.json"
    config.write_text(SiroSettings().model_dump_json(), encoding="utf-8")
    config_before = config.read_bytes()
    source_before = _value(store.path)
    source_bytes = store.path.read_bytes()
    destination = tmp_path / "archive.zip"
    temporary_output = destination.with_suffix(".zip.tmp")
    destination.write_bytes(b"synthetic-previous-archive")
    temporary_output.write_bytes(b"synthetic-previous-archive-temporary")
    pause = _BackupPause(store, monkeypatch)
    backup = asyncio.create_task(create_backup_bundle(store, destination, config=config))
    try:
        await _wait(pause.entered)
        snapshot = pause.paths[0]
        assert snapshot.parent.is_dir() and snapshot.parent.parent == staging_root
        for _ in range(cancellations):
            backup.cancel()
            await asyncio.sleep(0.01)
        assert not backup.done(), "ZIP context must await the actual owned snapshot"
        assert snapshot.parent.is_dir(), "staging cannot clean up while old IO can recreate it"
        pause.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(backup, 3)
        assert pause.finished.is_set()
        assert not snapshot.parent.exists() and not list(staging_root.iterdir())
        await asyncio.sleep(0.02)
        assert not snapshot.parent.exists(), "joined work must not recreate staging later"
        assert _value(store.path) == source_before
        assert store.path.read_bytes() == source_bytes
        assert config.read_bytes() == config_before
        assert destination.read_bytes() == b"synthetic-previous-archive"
        assert temporary_output.read_bytes() == b"synthetic-previous-archive-temporary"
    finally:
        pause.release.set()
        await asyncio.gather(backup, return_exceptions=True)
        await _wait(pause.finished)


@pytest.mark.asyncio
async def test_backup_cancel_while_waiting_for_writer_never_starts_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _database(tmp_path)
    destination = tmp_path / "snapshot.db"
    calls: list[Path] = []
    original = store._backup_sync

    def backup(path: Path, cancelled: threading.Event | None = None) -> None:
        calls.append(path)
        if cancelled is None:
            original(path)
        else:
            original(path, cancelled)

    monkeypatch.setattr(store, "_backup_sync", backup)
    await store._writer_lock.acquire()
    task = asyncio.create_task(store.backup_to(destination))
    try:
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert calls == [] and not destination.exists()
        assert _value(store.path) == "source-snapshot"
    finally:
        store._writer_lock.release()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_raw_backup_cancel_after_commit_preserves_actual_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _database(tmp_path)
    destination = tmp_path / "snapshot.db"
    pause = _BackupPause(store, monkeypatch, after_copy=True)
    task = asyncio.create_task(store.backup_to(destination))
    try:
        await _wait(pause.entered)
        assert _value(destination) == "source-snapshot", "cancel must be after actual commit"
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done() and store._writer_lock.locked()
        pause.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert pause.finished.is_set()
        assert _value(destination) == "source-snapshot", "cancel does not undo committed output"
        assert not list(tmp_path.glob(".snapshot.db.*"))
    finally:
        pause.release.set()
        await asyncio.gather(task, return_exceptions=True)
        await _wait(pause.finished)


@pytest.mark.asyncio
async def test_backup_primary_error_survives_repeated_cancel_without_unobserved_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _database(tmp_path)
    destination = tmp_path / "snapshot.db"
    failure = sqlite3.OperationalError("synthetic copy failure")
    pause = _BackupPause(store, monkeypatch, failure=failure)
    task = asyncio.create_task(store.backup_to(destination))
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    unobserved: list[dict[str, Any]] = []
    loop.set_exception_handler(lambda _loop, context: unobserved.append(context))
    try:
        await _wait(pause.entered)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done()
        pause.release.set()
        with pytest.raises(sqlite3.OperationalError) as caught:
            await asyncio.wait_for(task, 3)
        assert caught.value is failure
        assert pause.finished.is_set() and not destination.exists()
        await asyncio.sleep(0.02)
        assert unobserved == [], "handled primary error cannot also become an orphan loop error"
    finally:
        pause.release.set()
        await asyncio.gather(task, return_exceptions=True)
        await _wait(pause.finished)
        loop.set_exception_handler(previous_handler)


class _Connections:
    """Real SQLite connections; failures of copy/open/close are explicit controlled seams."""

    def __init__(
        self,
        store: SQLiteStore,
        monkeypatch: pytest.MonkeyPatch,
        *,
        failure: BaseException | None = None,
        close_failure: str | None = None,
        target_open_failure: bool = False,
    ) -> None:
        self.opened: list[sqlite3.Connection] = []
        self.close_attempts: list[sqlite3.Connection] = []
        self.paths: list[Path] = []
        owner = self
        original = store._connect

        class Connection(sqlite3.Connection):
            def backup(
                self,
                target: sqlite3.Connection,
                *,
                pages: int = -1,
                progress: Callable[[int, int, int], object] | None = None,
                name: str = "main",
                sleep: float = 0.25,
            ) -> None:
                if failure is not None:
                    raise failure
                super().backup(target, pages=pages, progress=progress, name=name, sleep=sleep)

            def close(self) -> None:
                owner.close_attempts.append(self)
                index = owner.opened.index(self)
                role = "source" if index == 0 else "target"
                if close_failure == role:
                    raise OSError("synthetic-private-close-detail-must-not-enter-notes")
                super().close()

        def connect(path: Path | None = None) -> sqlite3.Connection:
            if path is not None and target_open_failure:
                assert failure is not None
                raise failure
            actual = path or store.path
            # Only the fixture disables affinity so its owner can force-close refused handles.
            # Production close attempts still execute in the actual backup worker thread.
            connection = sqlite3.connect(
                actual, factory=Connection, timeout=5, check_same_thread=False
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            if path is None:
                connection.execute("PRAGMA journal_mode=WAL")
            owner.opened.append(connection)
            owner.paths.append(actual)
            return connection

        self.original_connect = original
        monkeypatch.setattr(store, "_connect", connect)

    def force_close(self) -> None:
        for connection in self.opened:
            sqlite3.Connection.close(connection)


@pytest.mark.asyncio
@pytest.mark.parametrize("copy_fails", [False, True])
async def test_backup_explicitly_closes_both_actual_connections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, copy_fails: bool
) -> None:
    store = _database(tmp_path)
    destination = tmp_path / "snapshot.db"
    failure = sqlite3.OperationalError("synthetic copy failure") if copy_fails else None
    connections = _Connections(store, monkeypatch, failure=failure)
    try:
        if failure is None:
            await store.backup_to(destination)
            assert _value(destination) == "source-snapshot"
        else:
            with pytest.raises(sqlite3.OperationalError) as caught:
                await store.backup_to(destination)
            assert caught.value is failure and not destination.exists()
        assert len(connections.opened) == 2
        assert set(connections.close_attempts) == set(connections.opened)
        for connection in connections.opened:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                connection.execute("SELECT 1")
        assert not list(tmp_path.glob(".snapshot.db.*"))
    finally:
        connections.force_close()


@pytest.mark.asyncio
async def test_backup_target_open_failure_closes_already_open_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _database(tmp_path)
    destination = tmp_path / "snapshot.db"
    failure = sqlite3.OperationalError("synthetic target open failure")
    connections = _Connections(store, monkeypatch, failure=failure, target_open_failure=True)
    try:
        with pytest.raises(sqlite3.OperationalError) as caught:
            await store.backup_to(destination)
        assert caught.value is failure and len(connections.opened) == 1
        assert connections.close_attempts == connections.opened
        assert not destination.exists() and not list(tmp_path.glob(".snapshot.db.*"))
    finally:
        connections.force_close()


@pytest.mark.asyncio
@pytest.mark.parametrize("close_failure", ["source", "target"])
async def test_backup_primary_error_survives_connection_cleanup_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, close_failure: str
) -> None:
    store = _database(tmp_path)
    destination = tmp_path / "snapshot.db"
    failure = sqlite3.OperationalError("synthetic primary copy failure")
    connections = _Connections(store, monkeypatch, failure=failure, close_failure=close_failure)
    try:
        with pytest.raises(sqlite3.OperationalError) as caught:
            await store.backup_to(destination)
        assert caught.value is failure
        assert len(connections.opened) == 2
        assert set(connections.close_attempts) == set(connections.opened)
        notes = getattr(caught.value, "__notes__", [])
        assert any("close" in note.lower() or "cleanup" in note.lower() for note in notes)
        assert all("synthetic-private-close-detail" not in note for note in notes)
        assert not destination.exists()
    finally:
        connections.force_close()


@pytest.mark.asyncio
@pytest.mark.parametrize("close_failure", ["source", "target"])
async def test_backup_reports_connection_cleanup_refusal_after_successful_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, close_failure: str
) -> None:
    store = _database(tmp_path)
    destination = tmp_path / "snapshot.db"
    connections = _Connections(store, monkeypatch, close_failure=close_failure)
    try:
        with pytest.raises(OSError, match="synthetic-private-close-detail"):
            await store.backup_to(destination)
        assert len(connections.opened) == 2
        assert set(connections.close_attempts) == set(connections.opened)
        assert _value(store.path) == "source-snapshot"
    finally:
        connections.force_close()


@pytest.mark.asyncio
async def test_backup_primary_error_survives_temporary_cleanup_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _database(tmp_path)
    destination = tmp_path / "snapshot.db"
    failure = sqlite3.OperationalError("synthetic primary copy failure")
    connections = _Connections(store, monkeypatch, failure=failure)
    native_unlink = Path.unlink
    refused: list[Path] = []

    def unlink(path: Path, missing_ok: bool = False) -> None:
        if path.parent == tmp_path and path.name.startswith(".snapshot.db."):
            refused.append(path)
            raise OSError("synthetic-private-cleanup-detail-must-not-enter-notes")
        native_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    try:
        with pytest.raises(sqlite3.OperationalError) as caught:
            await store.backup_to(destination)
        assert caught.value is failure and not destination.exists()
        assert refused and all(path.exists() for path in refused)
        notes = getattr(caught.value, "__notes__", [])
        assert any("cleanup" in note.lower() for note in notes)
        assert all("synthetic-private-cleanup-detail" not in note for note in notes)
    finally:
        connections.force_close()
        for path in refused:
            native_unlink(path, missing_ok=True)


@pytest.mark.asyncio
async def test_backup_committed_output_remains_visible_when_final_cleanup_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _database(tmp_path)
    destination = tmp_path / "snapshot.db"
    native_unlink = Path.unlink

    def unlink(path: Path, missing_ok: bool = False) -> None:
        if path.parent == tmp_path and path.name.startswith(".snapshot.db."):
            raise OSError("synthetic cleanup refusal after commit")
        native_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(OSError, match="synthetic cleanup refusal after commit"):
        await store.backup_to(destination)
    assert _value(destination) == "source-snapshot", "visible cleanup error does not undo commit"
    assert _value(store.path) == "source-snapshot"


@pytest.mark.asyncio
async def test_backup_worker_preserves_each_callers_context_without_cross_call_leakage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _database(tmp_path)
    provenance = ContextVar("synthetic_backup_provenance", default="missing")
    observed: list[tuple[Path, str, int]] = []
    original = store._backup_sync

    def backup(destination: Path, cancelled: threading.Event | None = None) -> None:
        observed.append((destination, provenance.get(), threading.get_ident()))
        original(destination, cancelled)

    async def caller(value: str, destination: Path) -> None:
        token = provenance.set(value)
        try:
            await store.backup_to(destination)
        finally:
            provenance.reset(token)

    monkeypatch.setattr(store, "_backup_sync", backup)
    first, second = tmp_path / "first.db", tmp_path / "second.db"
    await asyncio.gather(caller("first-caller", first), caller("second-caller", second))
    assert {(path, value) for path, value, _ in observed} == {
        (first, "first-caller"),
        (second, "second-caller"),
    }
    assert len(observed) == 2 and all(thread != threading.get_ident() for _, _, thread in observed)
    assert provenance.get() == "missing"
    assert _value(first) == _value(second) == _value(store.path) == "source-snapshot"


@pytest.mark.asyncio
@pytest.mark.parametrize("pause_at", ["copying", "copy_done"])
async def test_real_copy_cancellation_before_final_publication_preserves_prior_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pause_at: str
) -> None:
    """DONE commits the owned temporary copy; publication remains a separate boundary."""

    store = _database(tmp_path)
    with closing(sqlite3.connect(store.path)) as connection, connection:
        connection.execute("CREATE TABLE backup_payload(value BLOB)")
        connection.executemany("INSERT INTO backup_payload VALUES (zeroblob(8192))", [()] * 128)
    source_before = store.path.read_bytes()
    destination = tmp_path / "snapshot.db"
    with closing(sqlite3.connect(destination)) as connection, connection:
        connection.execute("CREATE TABLE backup_fixture(value TEXT NOT NULL)")
        connection.execute("INSERT INTO backup_fixture VALUES ('prior-backup')")
    destination_before = destination.read_bytes()
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    statuses: list[int] = []
    opened: list[sqlite3.Connection] = []
    native_connect = sqlite3.connect
    original_backup = store._backup_sync

    class Connection(sqlite3.Connection):
        def backup(
            self,
            target: sqlite3.Connection,
            *,
            pages: int = -1,
            progress: Callable[[int, int, int], object] | None = None,
            name: str = "main",
            sleep: float = 0.25,
        ) -> None:
            def observe(status: int, remaining: int, total: int) -> None:
                statuses.append(status)
                at_boundary = (
                    status == sqlite3.SQLITE_DONE
                    if pause_at == "copy_done"
                    else status != sqlite3.SQLITE_DONE
                )
                if at_boundary and not entered.is_set():
                    entered.set()
                    assert release.wait(4), "synthetic real-copy progress release missing"
                if progress is not None:
                    progress(status, remaining, total)

            # Force several genuine copy steps; only the pause timing is controlled.
            super().backup(target, pages=1, progress=observe, name=name, sleep=sleep)

    def connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        kwargs["factory"] = Connection
        kwargs["check_same_thread"] = False  # Owner can clean refused/old-source fixture handles.
        connection = native_connect(*args, **kwargs)
        assert isinstance(connection, Connection)
        opened.append(connection)
        return connection

    def backup(path: Path, cancelled: threading.Event | None = None) -> None:
        try:
            if cancelled is None:
                original_backup(path)
            else:
                original_backup(path, cancelled)
        finally:
            finished.set()

    monkeypatch.setattr(sqlite3, "connect", connect)
    monkeypatch.setattr(store, "_backup_sync", backup)
    task = asyncio.create_task(store.backup_to(destination))
    try:
        await _wait(entered)
        assert destination.read_bytes() == destination_before
        assert _value(destination) == "prior-backup"
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0.01)
        assert not task.done() and store._writer_lock.locked()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert finished.is_set()
        assert any(status != sqlite3.SQLITE_DONE for status in statuses)
        if pause_at == "copy_done":
            assert sqlite3.SQLITE_DONE in statuses, "fixture must cancel after actual temp copy"
        assert destination.read_bytes() == destination_before
        assert _value(destination) == "prior-backup"
        assert store.path.read_bytes() == source_before
        assert _value(store.path) == "source-snapshot"
        assert not list(tmp_path.glob(".snapshot.db.*"))
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await _wait(finished)
        for connection in opened:
            sqlite3.Connection.close(connection)
