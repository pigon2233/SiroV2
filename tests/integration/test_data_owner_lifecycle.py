"""Actual Linux fd ownership with synthetic paths and explicitly joined child processes."""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import importlib
import os
import pwd
import select
import signal
import sqlite3
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import closing, contextmanager, suppress
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def ownership(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ModuleType, Path]:
    # A missing core capability is RED, never an importorskip.
    module = importlib.import_module("siro.adapters.data_ownership")
    domain = tmp_path / "owner-domain"
    monkeypatch.setattr(module, "_owner_directory", lambda: domain)
    return module, domain


def lock_path(domain: Path, database: Path) -> Path:
    digest = hashlib.sha256(str(database.resolve()).encode()).hexdigest()
    return domain / f"{digest}.lock"


def child_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SIRO_") and key not in {"GROQ_API_KEY", "OPENAI_API_KEY"}
    }


def line(process: subprocess.Popen[str]) -> str:
    assert process.stdout is not None
    poller = select.poll()
    poller.register(process.stdout, select.POLLIN | select.POLLHUP | select.POLLERR)
    readable = poller.poll(2000)
    assert readable, "synthetic child handshake timed out"
    value = str(process.stdout.readline()).strip()
    assert value, f"synthetic child exited before handshake: {process.poll()}"
    return value


@contextmanager
def held_by_process(domain: Path, database: Path) -> Iterator[subprocess.Popen[str]]:
    code = (
        "import sys,sqlite3; from pathlib import Path; "
        "import siro.adapters.data_ownership as owner; "
        "owner._owner_directory=lambda:Path(sys.argv[1]); "
        "database=Path(sys.argv[2]); "
        "\nwith owner.exclusive_data_owner(database):\n"
        " database.parent.mkdir(parents=True,exist_ok=True)\n"
        " connection=sqlite3.connect(database)\n"
        " connection.execute('PRAGMA journal_mode=WAL')\n"
        " connection.execute('CREATE TABLE synthetic_owner(value TEXT)')\n"
        " connection.execute(\"INSERT INTO synthetic_owner VALUES ('committed')\")\n"
        " connection.commit()\n"
        " print('HELD',flush=True)\n"
        " sys.stdin.read(1)\n"
        " connection.close()\n"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(domain), str(database)],
        env=child_environment(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert line(process) == "HELD"
        yield process
    finally:
        if process.poll() is None:
            assert process.stdin is not None
            process.stdin.close()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


def test_owner_file_has_fixed_identity_modes_and_survives_normal_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "not-created" / "siro.db"
    leaf = lock_path(domain, database)
    with owner.exclusive_data_owner(database):
        assert domain.stat().st_mode & 0o777 == 0o700
        assert leaf.stat().st_mode & 0o777 == 0o600
        assert leaf.read_bytes() == b"" and leaf.stat().st_nlink == 1
        inode = leaf.stat().st_ino
        assert not database.parent.exists(), (
            "coordination must not create the target data directory"
        )
        with pytest.raises(owner.DataOwnerBusyError), owner.exclusive_data_owner(database):
            pytest.fail("same-process reentry must not acquire a second owner")
    assert leaf.exists() and leaf.stat().st_ino == inode and leaf.read_bytes() == b""
    with owner.exclusive_data_owner(database):
        assert leaf.stat().st_ino == inode


@pytest.mark.parametrize("stop", ["normal", "sigkill"])
def test_real_wal_writer_process_blocks_competition_until_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "data" / "siro.db"
    with held_by_process(domain, database) as process:
        leaf = lock_path(domain, database)
        inode = leaf.stat().st_ino
        with closing(sqlite3.connect(database)) as connection:
            before = tuple(connection.iterdump())
        with pytest.raises(owner.DataOwnerBusyError), owner.exclusive_data_owner(database):
            pytest.fail("a live managed SQLite writer must exclude the competing owner")
        with closing(sqlite3.connect(database)) as connection:
            assert tuple(connection.iterdump()) == before
        if stop == "sigkill":
            os.kill(process.pid, signal.SIGKILL)
        else:
            assert process.stdin is not None
            process.stdin.write("x")
            process.stdin.flush()
        process.wait(timeout=3)
        assert process.returncode == (0 if stop == "normal" else -signal.SIGKILL)
        with owner.exclusive_data_owner(database):
            assert leaf.stat().st_ino == inode


@contextmanager
def managed_child(
    code: str, domain: Path, database: Path, *, pass_fds: tuple[int, ...] = ()
) -> Iterator[subprocess.Popen[str]]:
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(domain), str(database)],
        env=child_environment(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        pass_fds=pass_fds,
    )
    try:
        yield process
    finally:
        if process.stdin is not None:
            with suppress(BrokenPipeError):
                process.stdin.close()
        if process.poll() is None:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        for pipe in (process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


def test_two_real_processes_compete_atomically_without_wait_or_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "never-created" / "siro.db"
    code = (
        "import sys; from pathlib import Path; "
        "import siro.adapters.data_ownership as owner; "
        "owner._owner_directory=lambda:Path(sys.argv[1]); "
        "print('READY',flush=True); sys.stdin.read(1)\n"
        "try:\n"
        " with owner.exclusive_data_owner(Path(sys.argv[2])):\n"
        "  print('HELD',flush=True)\n"
        "  sys.stdin.read(1)\n"
        "except owner.DataOwnerBusyError:\n"
        " print('BUSY',flush=True)\n"
        " raise SystemExit(7)\n"
    )
    with (
        managed_child(code, domain, database) as first,
        managed_child(code, domain, database) as second,
    ):
        assert line(first) == line(second) == "READY"
        for process in (first, second):
            assert process.stdin is not None
            process.stdin.write("x")
            process.stdin.flush()
        statuses = [line(first), line(second)]
        assert sorted(statuses) == ["BUSY", "HELD"]
        winner = (first, second)[statuses.index("HELD")]
        loser = (first, second)[statuses.index("BUSY")]
        assert loser.wait(timeout=2) == 7
        assert winner.poll() is None
        with pytest.raises(owner.DataOwnerBusyError), owner.exclusive_data_owner(database):
            pytest.fail("atomic winner must retain its owner")
        assert not database.parent.exists()


@pytest.mark.parametrize("alias", ["directory", "database"])
def test_canonical_symlink_alias_competes_for_exact_same_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alias: str
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    data = tmp_path / "data"
    data.mkdir()
    database = data / "siro.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE alias_fixture(value TEXT)")
        connection.commit()
    if alias == "directory":
        other = tmp_path / "directory-alias"
        other.symlink_to(data, target_is_directory=True)
        alternate = other / database.name
    else:
        alternate = tmp_path / "database-alias.db"
        alternate.symlink_to(database)
    with (
        owner.exclusive_data_owner(database),
        pytest.raises(owner.DataOwnerBusyError),
        owner.exclusive_data_owner(alternate),
    ):
        pytest.fail("canonical database aliases must not create parallel owners")
    assert len(list(domain.glob("*.lock"))) == 1
    assert lock_path(domain, database) == lock_path(domain, alternate)


def test_distinct_databases_can_hold_independent_owners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    first, second = tmp_path / "one" / "siro.db", tmp_path / "two" / "siro.db"
    with owner.exclusive_data_owner(first), owner.exclusive_data_owner(second):
        assert len(list(domain.glob("*.lock"))) == 2
        assert not first.parent.exists() and not second.parent.exists()


def test_thread_held_context_excludes_other_thread_until_complete_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "siro.db"
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    failures: list[BaseException] = []

    def hold() -> None:
        try:
            with owner.exclusive_data_owner(database):
                entered.set()
                assert release.wait(3), "synthetic thread release missing"
        except BaseException as error:
            failures.append(error)
        finally:
            finished.set()

    thread = threading.Thread(target=hold)
    thread.start()
    try:
        assert entered.wait(2), "synthetic thread owner did not start"
        with pytest.raises(owner.DataOwnerBusyError), owner.exclusive_data_owner(database):
            pytest.fail("a live thread-held context must exclude another owner")
        assert not finished.is_set()
        release.set()
        thread.join(timeout=2)
        assert finished.is_set() and not thread.is_alive() and failures == []
        with owner.exclusive_data_owner(database):
            pass
    finally:
        release.set()
        thread.join(timeout=3)
        assert not thread.is_alive()


def test_actual_exec_does_not_inherit_owner_descriptor_with_close_fds_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "siro.db"
    child = (
        "import sys,select; ready,_,_=select.select([sys.stdin],[],[],2); "
        "sys.stdin.read(1) if ready else None"
    )
    code = (
        "import sys,subprocess; from pathlib import Path; "
        "import siro.adapters.data_ownership as owner; "
        "owner._owner_directory=lambda:Path(sys.argv[1])\n"
        "with owner.exclusive_data_owner(Path(sys.argv[2])):\n"
        f" child=subprocess.Popen([sys.executable,'-c',{child!r}],close_fds=False)\n"
        "print('CLOSED '+str(child.pid),flush=True)\n"
        "raise SystemExit(child.wait(timeout=3))\n"
    )
    with managed_child(code, domain, database) as process:
        message = line(process)
        assert message.startswith("CLOSED ")
        child_pid = int(message.partition(" ")[2])
        os.kill(child_pid, 0)
        with owner.exclusive_data_owner(database):
            os.kill(child_pid, 0)
        assert process.stdin is not None
        process.stdin.write("x")
        process.stdin.flush()
        assert process.wait(timeout=3) == 0


@pytest.mark.parametrize("stop", ["normal", "sigkill"])
def test_raw_fork_child_conservatively_retains_owner_after_parent_context_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "siro.db"
    read_fd, write_fd = os.pipe()
    code = (
        "import os,sys,select; from pathlib import Path; "
        "import siro.adapters.data_ownership as owner; "
        "owner._owner_directory=lambda:Path(sys.argv[1])\n"
        "with owner.exclusive_data_owner(Path(sys.argv[2])):\n"
        " child=os.fork()\n"
        " if child==0:\n"
        "  os.close(0); os.close(1); os.close(2)\n"
        "  poller=select.poll()\n"
        f"  poller.register({read_fd},select.POLLIN|select.POLLHUP)\n"
        "  ready=poller.poll(2000)\n"
        f"  os.read({read_fd},1) if ready else None\n"
        "  os._exit(0)\n"
        "print('CLOSED '+str(child),flush=True)\n"
        "_,status=os.waitpid(child,0)\n"
        "print('REAPED',flush=True)\n"
    )
    try:
        with managed_child(code, domain, database, pass_fds=(read_fd,)) as process:
            message = line(process)
            assert message.startswith("CLOSED ")
            child_pid = int(message.partition(" ")[2])
            with pytest.raises(owner.DataOwnerBusyError), owner.exclusive_data_owner(database):
                pytest.fail("closing parent fd must not unlock a raw-fork child's fd")
            if stop == "normal":
                os.write(write_fd, b"x")
            else:
                os.kill(child_pid, signal.SIGKILL)
            assert line(process) == "REAPED"
            assert process.wait(timeout=3) == 0
            with owner.exclusive_data_owner(database):
                pass
    finally:
        os.close(write_fd)
        os.close(read_fd)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory", "fifo", "mode"])
def test_unsafe_lock_artifacts_fail_closed_without_touching_their_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "untouched" / "siro.db"
    domain.mkdir(mode=0o700)
    leaf = lock_path(domain, database)
    other = tmp_path / "synthetic-protected-file"
    other.write_bytes(b"synthetic preserved content")
    other.chmod(0o600)
    if kind == "symlink":
        leaf.symlink_to(other)
    elif kind == "hardlink":
        os.link(other, leaf)
    elif kind == "directory":
        leaf.mkdir(mode=0o700)
    elif kind == "fifo":
        os.mkfifo(leaf, mode=0o600)
    else:
        leaf.touch(mode=0o644)
        leaf.chmod(0o644)
    with pytest.raises(owner.DataOwnerUnavailableError), owner.exclusive_data_owner(database):
        pytest.fail("unsafe lock artifact must not grant ownership")
    assert other.read_bytes() == b"synthetic preserved content"
    assert not database.parent.exists()


@pytest.mark.parametrize("kind", ["symlink", "file", "mode"])
def test_unsafe_owner_namespace_is_not_followed_or_repaired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "untouched" / "siro.db"
    other = tmp_path / "other-domain"
    other.mkdir(mode=0o700)
    if kind == "symlink":
        domain.symlink_to(other, target_is_directory=True)
    elif kind == "file":
        domain.write_bytes(b"synthetic file preserved")
    else:
        domain.mkdir(mode=0o755)
        domain.chmod(0o755)
    with pytest.raises(owner.DataOwnerUnavailableError), owner.exclusive_data_owner(database):
        pytest.fail("unsafe coordination namespace must not grant ownership")
    assert list(other.iterdir()) == [] and not database.parent.exists()
    if kind == "file":
        assert domain.read_bytes() == b"synthetic file preserved"
    elif kind == "mode":
        assert domain.stat().st_mode & 0o777 == 0o755


@pytest.mark.parametrize("kind", ["directory", "hardlink"])
def test_existing_database_must_be_regular_and_have_no_hardlink_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    owner, _domain = ownership(tmp_path, monkeypatch)
    database, other = tmp_path / "siro.db", tmp_path / "alias.db"
    if kind == "directory":
        database.mkdir()
    else:
        database.write_bytes(b"synthetic database bytes")
        os.link(database, other)
    with pytest.raises(owner.DataOwnerUnavailableError), owner.exclusive_data_owner(database):
        pytest.fail("nonregular or multiply-linked database must not grant ownership")
    if kind == "hardlink":
        assert database.read_bytes() == other.read_bytes() == b"synthetic database bytes"


def test_account_home_namespace_ignores_environment_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("siro.adapters.data_ownership")
    account_home = tmp_path / "account-home"
    monkeypatch.setattr(
        pwd,
        "getpwuid",
        lambda uid: SimpleNamespace(pw_dir=str(account_home), pw_uid=uid),
    )
    for name in ("HOME", "TMPDIR", "XDG_STATE_HOME"):
        monkeypatch.setenv(name, str(tmp_path / f"untrusted-{name}"))
    assert module._owner_directory() == account_home / ".local/state/siro/data-owners"
    assert not account_home.exists(), "namespace resolution itself must not create state"


@pytest.mark.parametrize("primary", [False, True])
def test_descriptor_close_failure_is_visible_and_preserves_primary_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primary: bool
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "siro.db"
    leaf = lock_path(domain, database)
    original_open, original_close = os.open, os.close
    captured: list[int] = []
    sensitive_detail = "synthetic-private-detail-not-for-error-text"

    def tracked_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        fd = original_open(path, flags, mode, dir_fd=dir_fd)
        if os.fsdecode(path).endswith(leaf.name):
            captured.append(fd)
        return fd

    def denied_close(fd: int) -> None:
        if fd in captured:
            raise OSError(sensitive_detail)
        original_close(fd)

    monkeypatch.setattr(os, "open", tracked_open)
    monkeypatch.setattr(os, "close", denied_close)
    try:
        if primary:
            with (
                pytest.raises(RuntimeError, match="synthetic primary") as error,
                owner.exclusive_data_owner(database),
            ):
                raise RuntimeError("synthetic primary")
            notes = getattr(error.value, "__notes__", [])
            assert notes and all(sensitive_detail not in note for note in notes)
        else:
            with (
                pytest.raises(owner.DataOwnerUnavailableError) as unavailable,
                owner.exclusive_data_owner(database),
            ):
                pass
            assert sensitive_detail not in str(unavailable.value)
        assert captured and all(os.fstat(fd).st_ino == leaf.stat().st_ino for fd in captured)
    finally:
        for fd in captured:
            with suppress(OSError):
                original_close(fd)


def test_open_failure_returns_safe_unavailable_error_without_data_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "untouched" / "siro.db"
    original = os.open
    sensitive_detail = "synthetic-private-open-error"

    def denied_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if os.fsdecode(path).endswith(".lock"):
            raise OSError(sensitive_detail)
        return original(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", denied_open)
    with (
        pytest.raises(owner.DataOwnerUnavailableError) as error,
        owner.exclusive_data_owner(database),
    ):
        pytest.fail("unknown OS open failure must not fall back to PID ownership")
    assert sensitive_detail not in str(error.value) and str(database) not in str(error.value)
    assert not database.parent.exists()


@pytest.mark.parametrize("primary", [False, True])
def test_owned_default_pool_sqlite_work_is_joined_before_context_releases_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primary: bool
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "siro.db"
    entered, release = threading.Event(), threading.Event()
    exiting, finished = threading.Event(), threading.Event()
    failures: list[BaseException] = []
    busy: list[str] = []
    code = (
        "import sys; from pathlib import Path; "
        "import siro.adapters.data_ownership as owner; "
        "owner._owner_directory=lambda:Path(sys.argv[1])\n"
        "try:\n"
        " with owner.exclusive_data_owner(Path(sys.argv[2])):\n"
        "  print('UNEXPECTED',flush=True)\n"
        "except owner.DataOwnerBusyError:\n"
        " print('BUSY',flush=True)\n"
    )

    def work() -> None:
        try:
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("CREATE TABLE pool_fixture(value TEXT)")
                connection.execute("INSERT INTO pool_fixture VALUES ('joined-commit')")
                entered.set()
                assert release.wait(3), "synthetic pool COMMIT release missing"
        finally:
            finished.set()

    def probe_and_release() -> None:
        try:
            assert entered.wait(2) and exiting.wait(2)
            assert not finished.is_set()
            with managed_child(code, domain, database) as process:
                busy.append(line(process))
                assert process.wait(timeout=2) == 0
        except BaseException as error:
            failures.append(error)
        finally:
            release.set()

    controller = threading.Thread(target=probe_and_release)
    controller.start()
    try:
        if primary:
            with (
                pytest.raises(KeyboardInterrupt, match="synthetic primary interrupt"),
                owner.exclusive_data_owner(database) as held,
            ):
                loop = held.loop_factory()
                loop.run_in_executor(None, work)
                assert entered.wait(2)
                loop.close()  # real loop close leaves actual pool work unfinished
                exiting.set()
                raise KeyboardInterrupt("synthetic primary interrupt")
        else:
            with owner.exclusive_data_owner(database) as held:
                loop = held.loop_factory()
                loop.run_in_executor(None, work)
                assert entered.wait(2)
                loop.close()
                exiting.set()
        controller.join(timeout=2)
        assert not controller.is_alive() and failures == []
        assert busy == ["BUSY"] and finished.is_set()
        with owner.exclusive_data_owner(database), closing(sqlite3.connect(database)) as connection:
            assert connection.execute("SELECT value FROM pool_fixture").fetchone() == (
                "joined-commit",
            )
    finally:
        exiting.set()
        release.set()
        controller.join(timeout=3)
        assert not controller.is_alive()


def test_missing_pwd_account_returns_safe_unavailable_before_any_directory_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = importlib.import_module("siro.adapters.data_ownership")
    database = tmp_path / "untouched" / "siro.db"
    sensitive_detail = "synthetic-missing-account-detail"

    def unknown_account(_uid: int) -> object:
        raise KeyError(sensitive_detail)

    monkeypatch.setattr(pwd, "getpwuid", unknown_account)
    with (
        pytest.raises(owner.DataOwnerUnavailableError) as error,
        owner.exclusive_data_owner(database),
    ):
        pytest.fail("unknown account namespace must not create a fallback owner")
    assert sensitive_detail not in str(error.value) and not database.parent.exists()


def test_busy_error_survives_contender_descriptor_cleanup_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "siro.db"
    leaf = lock_path(domain, database)
    original_open, original_close = os.open, os.close
    contender_fds: list[int] = []
    sensitive_detail = "synthetic-contender-cleanup-detail"

    def tracked_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
        if os.fsdecode(path).endswith(leaf.name):
            contender_fds.append(descriptor)
        return descriptor

    def denied_close(descriptor: int) -> None:
        if descriptor in contender_fds:
            raise OSError(sensitive_detail)
        original_close(descriptor)

    with owner.exclusive_data_owner(database):
        monkeypatch.setattr(os, "open", tracked_open)
        monkeypatch.setattr(os, "close", denied_close)
        try:
            with (
                pytest.raises(owner.DataOwnerBusyError) as error,
                owner.exclusive_data_owner(database),
            ):
                pytest.fail("cleanup refusal must not replace primary busy rejection")
            notes = getattr(error.value, "__notes__", [])
            assert notes and all(sensitive_detail not in note for note in notes)
            assert contender_fds and all(
                os.fstat(descriptor).st_ino == leaf.stat().st_ino for descriptor in contender_fds
            )
        finally:
            for descriptor in contender_fds:
                with suppress(OSError):
                    original_close(descriptor)


@pytest.mark.parametrize("primary", [False, True])
def test_owned_pool_join_refusal_retains_descriptor_and_primary_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primary: bool
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    owner, domain = ownership(tmp_path, monkeypatch)
    database = tmp_path / "siro.db"
    leaf = lock_path(domain, database)
    original_open, original_close = os.open, os.close
    descriptor: list[int] = []
    sensitive_detail = "synthetic-pool-join-detail"

    def tracked_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        result = original_open(path, flags, mode, dir_fd=dir_fd)
        if os.fsdecode(path).endswith(leaf.name):
            descriptor.append(result)
        return result

    def refuse_join(
        _executor: ThreadPoolExecutor, wait: bool = True, *, cancel_futures: bool = False
    ) -> None:
        raise RuntimeError(sensitive_detail)

    monkeypatch.setattr(os, "open", tracked_open)
    try:
        if primary:
            with (
                pytest.raises(ValueError, match="synthetic primary") as error,
                owner.exclusive_data_owner(database) as held,
            ):
                loop = held.loop_factory()
                loop.close()  # no executor task is submitted in this refusal-only fixture
                monkeypatch.setattr(ThreadPoolExecutor, "shutdown", refuse_join)
                raise ValueError("synthetic primary")
            notes = getattr(error.value, "__notes__", [])
            assert notes and all(sensitive_detail not in note for note in notes)
        else:
            with (
                pytest.raises(owner.DataOwnerUnavailableError) as unavailable,
                owner.exclusive_data_owner(database) as held,
            ):
                loop = held.loop_factory()
                loop.close()
                monkeypatch.setattr(ThreadPoolExecutor, "shutdown", refuse_join)
            assert sensitive_detail not in str(unavailable.value)
        assert descriptor and os.fstat(descriptor[0]).st_ino == leaf.stat().st_ino
        with pytest.raises(owner.DataOwnerBusyError), owner.exclusive_data_owner(database):
            pytest.fail("unknown owned-IO completion must not release ownership")
    finally:
        asyncio.set_event_loop(None)
        for fd in descriptor[:1]:
            with suppress(OSError):
                original_close(fd)


def test_joint_owner_partial_busy_acquisition_releases_the_other_actual_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    source, target = tmp_path / "a-source.db", tmp_path / "z-target.db"
    source_leaf = lock_path(domain, source)
    source_acquisitions: list[int] = []
    original_flock = fcntl.flock

    def observe(descriptor: int, operation: int) -> None:
        original_flock(descriptor, operation)
        if source_leaf.exists() and os.fstat(descriptor).st_ino == source_leaf.stat().st_ino:
            source_acquisitions.append(descriptor)

    with owner.exclusive_data_owner(target):
        monkeypatch.setattr(fcntl, "flock", observe)
        with (
            pytest.raises(owner.DataOwnerBusyError),
            owner.exclusive_data_owner(source, write_target=target),
        ):
            pytest.fail("busy second key must reject before entering the operation body")
        assert len(source_acquisitions) == 1, "fixture must acquire first key before second is busy"
        with owner.exclusive_data_owner(source):
            assert len(source_acquisitions) == 2
        with pytest.raises(owner.DataOwnerBusyError), owner.exclusive_data_owner(target):
            pytest.fail("the independent target holder must remain untouched")
    assert not source.exists() and not target.exists()


def test_joint_owner_deduplicates_canonical_write_target_alias_without_reentry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    data = tmp_path / "data"
    data.mkdir()
    source = data / "siro.db"
    alias = tmp_path / "canonical-alias"
    alias.symlink_to(data, target_is_directory=True)
    target = alias / source.name
    with owner.exclusive_data_owner(source, write_target=target):
        assert list(domain.glob("*.lock")) == [lock_path(domain, source)]
        with pytest.raises(owner.DataOwnerBusyError), owner.exclusive_data_owner(target):
            pytest.fail("deduplicated resource must still retain its sole owner")
    with owner.exclusive_data_owner(target):
        pass
    assert not source.exists()


def test_three_resource_owner_busy_last_key_releases_both_acquired_prefix_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, domain = ownership(tmp_path, monkeypatch)
    source, target, temporary = [tmp_path / name for name in ("a.db", "b.db", "z.tmp")]
    prefixes = {lock_path(domain, path) for path in (source, target)}
    observed: set[int] = set()
    original_flock = fcntl.flock

    def observe(descriptor: int, operation: int) -> None:
        original_flock(descriptor, operation)
        if any(
            leaf.exists() and os.fstat(descriptor).st_ino == leaf.stat().st_ino for leaf in prefixes
        ):
            observed.add(os.fstat(descriptor).st_ino)

    with owner.exclusive_data_owner(temporary):
        monkeypatch.setattr(fcntl, "flock", observe)
        with (
            pytest.raises(owner.DataOwnerBusyError),
            owner.exclusive_data_owner(
                source, write_target=target, temporary_write_target=temporary
            ),
        ):
            pytest.fail("busy final temporary key must reject before any body effects")
        assert observed == {leaf.stat().st_ino for leaf in prefixes}
        with owner.exclusive_data_owner(source, write_target=target):
            pass
        with pytest.raises(owner.DataOwnerBusyError), owner.exclusive_data_owner(temporary):
            pytest.fail("the original temporary writer must remain untouched")
    assert not any(path.exists() for path in (source, target, temporary))


@pytest.mark.parametrize("include_temporary", [False, True])
def test_joint_owner_io_join_refusal_retains_all_descriptors_and_primary_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, include_temporary: bool
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    owner, domain = ownership(tmp_path, monkeypatch)
    source, target = tmp_path / "source.db", tmp_path / "target.db"
    temporary = target.with_suffix(target.suffix + ".tmp") if include_temporary else None
    resources = (source, target, temporary) if temporary is not None else (source, target)
    leaves = {lock_path(domain, resource) for resource in resources}
    original_open, original_close = os.open, os.close
    captured: list[int] = []
    owner_fds: list[int] = []
    sensitive_detail = "synthetic-joint-owner-pool-detail"

    def tracked_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
        if Path(os.fsdecode(path)) in leaves:
            captured.append(descriptor)
        return descriptor

    def refuse_join(
        _executor: ThreadPoolExecutor, wait: bool = True, *, cancel_futures: bool = False
    ) -> None:
        raise RuntimeError(sensitive_detail)

    monkeypatch.setattr(os, "open", tracked_open)
    try:
        with (
            pytest.raises(ValueError, match="synthetic joint primary") as error,
            owner.exclusive_data_owner(
                source, write_target=target, temporary_write_target=temporary
            ) as held,
        ):
            owner_fds.extend(captured)
            assert len(owner_fds) == len(set(owner_fds)) == len(resources)
            loop = held.loop_factory()
            loop.close()  # refusal-only fixture submits no executor tasks
            monkeypatch.setattr(ThreadPoolExecutor, "shutdown", refuse_join)
            raise ValueError("synthetic joint primary")
        notes = getattr(error.value, "__notes__", [])
        assert notes and all(sensitive_detail not in note for note in notes)
        assert {os.fstat(descriptor).st_ino for descriptor in owner_fds} == {
            leaf.stat().st_ino for leaf in leaves
        }
        for resource in resources:
            with pytest.raises(owner.DataOwnerBusyError), owner.exclusive_data_owner(resource):
                pytest.fail("unknown shared IO completion must retain every kernel owner")
    finally:
        asyncio.set_event_loop(None)
        for descriptor in owner_fds:
            with suppress(OSError):
                original_close(descriptor)
