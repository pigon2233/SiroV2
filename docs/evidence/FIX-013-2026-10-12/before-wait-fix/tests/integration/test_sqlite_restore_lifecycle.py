from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import threading
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest

from siro.persistence import sqlite as sqlite_module
from siro.persistence.sqlite import (
    Migration,
    MigrationError,
    SQLiteStore,
    apply_migrations,
    load_migrations,
)


async def _wait(event: threading.Event) -> None:
    async with asyncio.timeout(2):
        while not event.is_set():
            await asyncio.sleep(0.002)


async def _databases(tmp_path: Path) -> tuple[SQLiteStore, Path]:
    store = SQLiteStore(tmp_path / "live.sqlite3")
    await store.initialize()

    def create(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE restore_fixture(value TEXT NOT NULL)")
        connection.execute("INSERT INTO restore_fixture VALUES ('latest')")

    await store.run_transaction(create)
    source = tmp_path / "backup.sqlite3"
    with closing(sqlite3.connect(source)) as connection:
        apply_migrations(connection, load_migrations())
        create(connection)
        connection.execute("UPDATE restore_fixture SET value='backup'")
        connection.commit()
    return store, source


def _state(path: Path) -> str:
    with closing(sqlite3.connect(path)) as connection:
        return str(connection.execute("SELECT value FROM restore_fixture").fetchone()[0])


class _MigrationPause:
    """Controlled thread timing around real SQLite migration work, never a fake database."""

    def __init__(self, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.thread_ids: list[int] = []
        original_migrate = sqlite_module.apply_migrations
        original_restore = store._restore_sync

        def migrate(connection: sqlite3.Connection, migrations: Sequence[Migration]) -> None:
            self.thread_ids.append(threading.get_ident())
            self.entered.set()
            assert self.release.wait(3), "synthetic migration release missing"
            original_migrate(connection, migrations)

        def restore(source: Path, cancelled: threading.Event | None = None) -> None:
            try:
                if cancelled is None:
                    original_restore(source)
                else:
                    original_restore(source, cancelled)
            finally:
                self.finished.set()

        monkeypatch.setattr(sqlite_module, "apply_migrations", migrate)
        monkeypatch.setattr(store, "_restore_sync", restore)


@pytest.mark.asyncio
async def test_repeated_restore_cancel_keeps_writer_owner_until_thread_finishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, source = await _databases(tmp_path)
    pause = _MigrationPause(store, monkeypatch)
    restore = asyncio.create_task(store.restore_from(source))
    writes: list[str] = []

    def write(connection: sqlite3.Connection) -> None:
        writes.append("queued")
        connection.execute("UPDATE restore_fixture SET value='queued'")

    queued: asyncio.Task[None] | None = None
    try:
        await _wait(pause.entered)
        assert pause.thread_ids[0] != threading.get_ident(), "restore work must remain off-loop"
        queued = asyncio.create_task(store.run_transaction(write))
        await asyncio.sleep(0.01)
        assert not queued.done()
        restore.cancel()
        await asyncio.sleep(0.01)
        restore.cancel()
        await asyncio.sleep(0.01)
        assert not restore.done(), "caller cancellation must join the real restore owner"
        assert store._writer_lock.locked()
        assert not queued.done() and writes == [], "queued writes must not overtake restore cleanup"
        pause.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(restore, 2)
        await asyncio.wait_for(queued, 2)
        assert pause.finished.is_set()
        assert writes == ["queued"] and _state(store.path) == "queued"
        assert not store._writer_lock.locked()
    finally:
        if queued is not None and not queued.done():
            queued.cancel()
        pause.release.set()
        await asyncio.gather(restore, *([queued] if queued else []), return_exceptions=True)
        await _wait(pause.finished)


@pytest.mark.asyncio
async def test_cancel_during_candidate_migration_preserves_latest_live_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, source = await _databases(tmp_path)
    original_source = source.read_bytes()
    pause = _MigrationPause(store, monkeypatch)
    restore = asyncio.create_task(store.restore_from(source))
    try:
        await _wait(pause.entered)
        restore.cancel()
        pause.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(restore, 2)
        await _wait(pause.finished)
        assert _state(store.path) == "latest", "cancelled candidate must never be promoted"
        assert source.read_bytes() == original_source
        assert await store.integrity_check() == "ok"
    finally:
        pause.release.set()
        await asyncio.gather(restore, return_exceptions=True)
        await _wait(pause.finished)


@pytest.mark.asyncio
async def test_cancel_while_waiting_for_writer_lock_never_starts_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, source = await _databases(tmp_path)
    calls: list[Path] = []
    original = store._restore_sync

    def restore(source: Path, cancelled: threading.Event | None = None) -> None:
        calls.append(source)
        if cancelled is None:
            original(source)
        else:
            original(source, cancelled)

    monkeypatch.setattr(store, "_restore_sync", restore)
    await store._writer_lock.acquire()
    task = asyncio.create_task(store.restore_from(source))
    try:
        await asyncio.sleep(0.01)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert calls == [] and store._writer_lock.locked()
        assert _state(store.path) == "latest"
    finally:
        store._writer_lock.release()
        await asyncio.gather(task, return_exceptions=True)


class _Directory:
    def __init__(self, owner: _Directories, native: Any) -> None:
        self.owner = owner
        self.native = native
        self.name = str(native.name)

    def __enter__(self) -> str:
        return self.name

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        self.owner.thread_ids.append(threading.get_ident())
        self.owner.entered.set()
        try:
            if self.owner.block:
                assert self.owner.release.wait(3), "synthetic cleanup release missing"
            if self.owner.failure is not None:
                raise self.owner.failure
            self.native.cleanup()
        finally:
            self.owner.finished.set()


class _Directories:
    """Only candidate cleanup timing/refusal is controlled; SQLite commits remain real."""

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        block: bool = False,
        failure: OSError | None = None,
    ) -> None:
        self.block = block
        self.failure = failure
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.thread_ids: list[int] = []
        self.instances: list[_Directory] = []
        original = tempfile.TemporaryDirectory

        def create(*args: Any, **kwargs: Any) -> _Directory:
            kwargs["dir"] = tmp_path
            instance = _Directory(self, original(*args, **kwargs))
            self.instances.append(instance)
            return instance

        monkeypatch.setattr(tempfile, "TemporaryDirectory", create)

    def force_cleanup(self) -> None:
        self.release.set()
        for instance in self.instances:
            instance.native.cleanup()


@pytest.mark.asyncio
async def test_cancel_after_real_live_commit_joins_cleanup_without_claiming_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, source = await _databases(tmp_path)
    directories = _Directories(tmp_path, monkeypatch, block=True)
    task = asyncio.create_task(store.restore_from(source))
    try:
        await _wait(directories.entered)
        assert _state(store.path) == "backup", "fixture must cancel after the actual SQLite commit"
        assert directories.thread_ids[0] != threading.get_ident()
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done() and store._writer_lock.locked()
        directories.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert directories.finished.is_set()
        assert _state(store.path) == "backup", "committed restore is not silently reversed"
        assert directories.instances and all(
            not Path(instance.name).exists() for instance in directories.instances
        )
        assert not store._writer_lock.locked()
    finally:
        directories.release.set()
        await asyncio.gather(task, return_exceptions=True)
        directories.force_cleanup()


@pytest.mark.asyncio
async def test_successful_commit_reports_candidate_cleanup_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, source = await _databases(tmp_path)
    directories = _Directories(
        tmp_path, monkeypatch, failure=OSError("synthetic candidate cleanup denial")
    )
    try:
        with pytest.raises(OSError, match="synthetic candidate cleanup denial"):
            await store.restore_from(source)
        assert _state(store.path) == "backup"
        assert directories.instances and all(
            Path(instance.name).exists() for instance in directories.instances
        ), "refused cleanup cannot be reported as removed"
        assert not store._writer_lock.locked()
    finally:
        directories.force_cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("late_cancel", [False, True])
async def test_migration_error_survives_cleanup_refusal_and_late_repeated_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, late_cancel: bool
) -> None:
    store, source = await _databases(tmp_path)
    original_source = source.read_bytes()
    sensitive_detail = "synthetic-source-content-must-not-enter-cleanup-note"
    directories = _Directories(
        tmp_path, monkeypatch, block=late_cancel, failure=OSError(sensitive_detail)
    )

    def fail(_connection: sqlite3.Connection, _migrations: Sequence[Migration]) -> None:
        raise MigrationError("synthetic applied migration mismatch")

    monkeypatch.setattr(sqlite_module, "apply_migrations", fail)
    task = asyncio.create_task(store.restore_from(source))
    try:
        if late_cancel:
            await _wait(directories.entered)
            task.cancel()
            await asyncio.sleep(0.01)
            task.cancel()
            await asyncio.sleep(0.01)
            assert not task.done() and store._writer_lock.locked()
            directories.release.set()
        with pytest.raises(MigrationError, match="synthetic applied migration mismatch") as error:
            await asyncio.wait_for(task, 2)
        notes = getattr(error.value, "__notes__", [])
        assert any("cleanup" in note.lower() for note in notes)
        assert all(sensitive_detail not in note for note in notes)
        assert _state(store.path) == "latest"
        assert source.read_bytes() == original_source
        assert directories.instances and all(
            Path(instance.name).exists() for instance in directories.instances
        )
        assert not store._writer_lock.locked()
    finally:
        directories.release.set()
        await asyncio.gather(task, return_exceptions=True)
        directories.force_cleanup()


@pytest.mark.asyncio
async def test_source_is_readonly_and_all_owned_sqlite_connections_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, source = await _databases(tmp_path)
    original_source = source.read_bytes()
    opened: list[TrackedConnection] = []
    closed: list[TrackedConnection] = []
    source_copies: list[bool] = []
    original_connect = sqlite3.connect

    class TrackedConnection(sqlite3.Connection):
        def close(self) -> None:
            closed.append(self)
            super().close()

        def backup(
            self,
            target: sqlite3.Connection,
            *,
            pages: int = -1,
            progress: Callable[[int, int, int], object] | None = None,
            name: str = "main",
            sleep: float = 0.25,
        ) -> None:
            database = str(self.execute("PRAGMA database_list").fetchone()[2])
            if Path(database) == source:
                assert self.execute("PRAGMA query_only").fetchone()[0] == 1
                # Removing query_only still cannot write: the source must be opened mode=ro.
                self.execute("PRAGMA query_only=OFF")
                try:
                    with pytest.raises(sqlite3.OperationalError, match="readonly"):
                        self.execute("UPDATE restore_fixture SET value='unexpected'")
                finally:
                    self.rollback()
                    self.execute("PRAGMA query_only=ON")
                source_copies.append(True)
            super().backup(target, pages=pages, progress=progress, name=name, sleep=sleep)

    def connect(*args: Any, **kwargs: Any) -> TrackedConnection:
        kwargs["factory"] = TrackedConnection
        connection = original_connect(*args, **kwargs)
        assert isinstance(connection, TrackedConnection)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    try:
        await store.restore_from(source)
        assert source_copies == [True]
        assert len(opened) >= 3 and all(connection in closed for connection in opened)
        assert source.read_bytes() == original_source
        assert _state(store.path) == "backup"
    finally:
        for connection in opened:
            if connection not in closed:
                connection.close()


@pytest.mark.asyncio
async def test_cancel_during_real_source_copy_joins_and_never_opens_live_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, source = await _databases(tmp_path)
    with closing(sqlite3.connect(source)) as connection, connection:
        connection.execute("CREATE TABLE copy_pages(value BLOB)")
        connection.execute("INSERT INTO copy_pages VALUES (zeroblob(1048576))")
    original_source = source.read_bytes()
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original_connect = sqlite3.connect
    original_store_connect = store._connect
    live_opens: list[bool] = []

    class SourceCopyConnection(sqlite3.Connection):
        def backup(
            self,
            target: sqlite3.Connection,
            *,
            pages: int = -1,
            progress: Callable[[int, int, int], object] | None = None,
            name: str = "main",
            sleep: float = 0.25,
        ) -> None:
            is_source = Path(str(self.execute("PRAGMA database_list").fetchone()[2])) == source

            def on_progress(status: int, remaining: int, total: int) -> None:
                if (
                    is_source
                    and status == sqlite3.SQLITE_OK
                    and remaining > 0
                    and not entered.is_set()
                ):
                    entered.set()
                    assert release.wait(3), "synthetic source-copy release missing"
                if progress is not None:
                    progress(status, remaining, total)

            try:
                super().backup(target, pages=64, progress=on_progress, name=name, sleep=sleep)
            finally:
                if is_source:
                    finished.set()

    def connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        kwargs["factory"] = SourceCopyConnection
        connection = original_connect(*args, **kwargs)
        assert isinstance(connection, SourceCopyConnection)
        return connection

    def store_connect(path: Path | None = None) -> sqlite3.Connection:
        if path is None:
            live_opens.append(True)
        return original_store_connect(path)

    monkeypatch.setattr(sqlite3, "connect", connect)
    monkeypatch.setattr(store, "_connect", store_connect)
    task = asyncio.create_task(store.restore_from(source))
    try:
        await _wait(entered)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done() and store._writer_lock.locked()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        await _wait(finished)
        assert live_opens == []
        assert _state(store.path) == "latest" and source.read_bytes() == original_source
        assert not store._writer_lock.locked()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await _wait(finished)
