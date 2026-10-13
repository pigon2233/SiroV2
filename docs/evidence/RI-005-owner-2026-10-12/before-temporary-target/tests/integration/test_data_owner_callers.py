from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from siro.cli import main
from siro.config import SiroSettings
from siro.core.releases import ReleaseManager, ReleaseManifest
from siro.persistence.sqlite import SQLiteStore, apply_migrations, load_migrations

KEY = b"synthetic-d50-owner-key"


def seed(path: Path, value: str) -> None:
    with closing(sqlite3.connect(path)) as connection, connection:
        apply_migrations(connection, load_migrations())
        connection.execute("CREATE TABLE owner_fixture(value TEXT)")
        connection.execute("INSERT INTO owner_fixture VALUES (?)", (value,))
        connection.execute(
            "INSERT INTO inbox(consumer_id,event_id,processed_at) "
            "VALUES ('completed',?,'synthetic')",
            (value,),
        )


def dump(path: Path) -> tuple[str, ...]:
    with closing(sqlite3.connect(path)) as connection:
        return tuple(connection.iterdump())


def tree(path: Path) -> dict[str, bytes]:
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}


@contextmanager
def kernel_owner(database: Path, home: Path) -> Iterator[Path]:
    """Independent OS holder of the documented coordination key; no adapter fallback."""
    domain = home / ".local/state/siro/data-owners"
    domain.mkdir(parents=True, mode=0o700, exist_ok=True)
    name = hashlib.sha256(str(database.resolve()).encode()).hexdigest() + ".lock"
    path = domain / name
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield path
    finally:
        os.close(descriptor)


@pytest.fixture
def account(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import pwd

    home = tmp_path / "synthetic-home"
    monkeypatch.setattr(pwd, "getpwuid", lambda _uid: SimpleNamespace(pw_dir=str(home)))
    monkeypatch.setenv("SIRO_RELEASE_SIGNING_KEY", KEY.decode())
    return home


def signed(bundle: Path, version: str) -> ReleaseManifest:
    values: dict[str, Any] = {
        "version": version,
        "source_sha256": ReleaseManager._digest(bundle),
        "min_schema": 1,
        "max_schema": len(load_migrations()),
        "signing_format": "siro-release-manifest-v1",
    }
    wire = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    values["signature"] = hmac.new(KEY, wire, hashlib.sha256).hexdigest()
    return ReleaseManifest.model_validate(values)


@pytest.mark.parametrize(
    "command", ["demo", "backup", "raw-restore", "zip-restore", "stage", "rollback"]
)
def test_managed_cli_busy_has_no_database_config_release_or_health_effects(
    tmp_path: Path, account: Path, command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database, source = data / "siro.db", tmp_path / "backup.db"
    seed(database, "latest-completed")
    seed(source, "old-snapshot")
    config = tmp_path / "config.json"
    config.write_text(SiroSettings().model_dump_json())
    release_root = tmp_path / "releases"
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "app.txt").write_text("synthetic approved application")
    manager = ReleaseManager(
        release_root, KEY, current_schema=len(load_migrations()), database=database
    )
    for version in ("1.0.0", "2.0.0"):
        assert (
            manager.stage_and_activate(
                bundle, signed(bundle, version), (sys.executable, "-c", "pass")
            ).status
            == "activated"
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(signed(bundle, "3.0.0").model_dump_json())
    health_marker = tmp_path / "health-called"
    health = json.dumps(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; Path(" + repr(str(health_marker)) + ").touch()",
        ]
    )
    if command == "demo":
        arguments = ["demo", "--data", str(data), "--once", "synthetic conversation"]
    elif command == "backup":
        arguments = ["backup", "--data", str(data), str(tmp_path / "new-backup.db")]
    elif command == "raw-restore":
        arguments = ["restore", "--data", str(data), str(source)]
    elif command == "zip-restore":
        archive_path = tmp_path / "backup.zip"
        content = {"siro.db": source.read_bytes(), "config.json": config.read_bytes()}
        with zipfile.ZipFile(archive_path, "w") as archive:
            for name, raw in content.items():
                archive.writestr(name, raw)
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "format": 1,
                        "files": {
                            name: hashlib.sha256(raw).hexdigest() for name, raw in content.items()
                        },
                    }
                ),
            )
        arguments = ["restore", "--data", str(data), "--config", str(config), str(archive_path)]
    else:
        arguments = [
            "release",
            "--release-root",
            str(release_root),
            "--database",
            str(database),
            "stage" if command == "stage" else "rollback",
        ]
        if command == "stage":
            arguments.extend(
                ["--bundle", str(bundle), "--manifest", str(manifest), "--healthcheck", health]
            )
    before, source_before, config_before, release_before = (
        dump(database),
        source.read_bytes(),
        config.read_bytes(),
        tree(release_root),
    )

    with kernel_owner(database, account):
        assert main(arguments) == 1

    assert json.loads(capsys.readouterr().out) == {"status": "data_in_use"}
    assert dump(database) == before and source.read_bytes() == source_before
    assert config.read_bytes() == config_before and tree(release_root) == release_before
    assert not health_marker.exists() and not (tmp_path / "new-backup.db").exists()


@pytest.mark.parametrize("profile", ["legacy", "candidate"])
def test_gateway_refuses_owner_before_sqlite_initialization_or_server(
    tmp_path: Path, account: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    import uvicorn

    from siro.services.presentation import gateway

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    data = tmp_path / "must-remain-absent"
    monkeypatch.setenv("SIRO_DATA_DIR", str(data))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", profile)
    called: list[str] = []

    async def initialize(_store: SQLiteStore) -> None:
        called.append("initialize")
        raise AssertionError("busy owner must precede initialization")

    monkeypatch.setattr(SQLiteStore, "initialize", initialize)
    monkeypatch.setattr(uvicorn, "run", lambda *_args, **_kwargs: called.append("server"))
    with kernel_owner(data / "siro.db", account), pytest.raises(SystemExit, match="already in use"):
        gateway.main()
    assert called == [] and not data.exists()


@pytest.mark.parametrize("error", [RuntimeError("synthetic startup failure"), KeyboardInterrupt()])
def test_gateway_owner_is_held_through_server_and_released_on_failure(
    tmp_path: Path, account: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    import uvicorn

    from siro.services.presentation import gateway

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path / "data"))
    checks: list[str] = []

    def run(*_args: Any, **_kwargs: Any) -> None:
        with pytest.raises(BlockingIOError), kernel_owner(tmp_path / "data/siro.db", account):
            checks.append("incorrectly acquired")
        checks.append("busy while server owns")
        raise error

    monkeypatch.setattr(uvicorn, "run", run)
    with pytest.raises(type(error)):
        gateway.main()
    assert checks == ["busy while server owns"]
    with kernel_owner(tmp_path / "data/siro.db", account):
        pass


def test_unreadable_existing_database_is_not_treated_as_a_new_target(
    tmp_path: Path,
    account: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if os.geteuid() == 0:
        pytest.skip("actual permission denial requires an unprivileged Linux account")
    data = tmp_path / "data"
    data.mkdir()
    database = data / "siro.db"
    seed(database, "latest-completed")
    called: list[str] = []

    async def initialize(_store: SQLiteStore) -> None:
        called.append("initialize")
        raise AssertionError("unknown target access must refuse before any database work")

    monkeypatch.setattr(SQLiteStore, "initialize", initialize)
    data.chmod(0)
    try:
        assert main(["backup", "--data", str(data), str(tmp_path / "backup.db")]) == 1
    finally:
        data.chmod(0o700)
    assert called == [] and not (tmp_path / "backup.db").exists()
    assert json.loads(capsys.readouterr().out) == {"status": "data_owner_unavailable"}


def test_owner_key_uses_actual_posix_path_bytes(tmp_path: Path, account: Path) -> None:
    from siro.adapters.data_ownership import exclusive_data_owner

    database = tmp_path / os.fsdecode(b"synthetic-\xff.db")
    expected = hashlib.sha256(os.fsencode(database.resolve())).hexdigest() + ".lock"
    with exclusive_data_owner(database):
        assert (account / ".local/state/siro/data-owners" / expected).is_file()
        assert not database.exists()


def child_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SIRO_") and key != "GROQ_API_KEY"
    }


def wait_marker(path: Path, process: subprocess.Popen[str], timeout: float = 5) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        assert process.poll() is None, f"owned fixture exited before {path.name}"
        assert time.monotonic() < deadline, f"owned fixture never reached {path.name}"
        time.sleep(0.005)


@pytest.mark.parametrize("command", ["backup", "demo"])
def test_actual_cli_repeated_sigint_joins_old_sqlite_work_before_next_owner(
    tmp_path: Path, account: Path, command: str
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database = data / "siro.db"
    seed(database, "latest-completed")
    entered, shutdown, finishing, release, finished = [
        tmp_path / name for name in ("entered", "shutdown", "finishing", "release", "finished")
    ]
    destination = tmp_path / "backup.db"
    program = tmp_path / "owned_cli.py"
    program.write_text(
        """import asyncio, json, pwd, sqlite3, sys, time
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from siro import cli
from siro.adapters import data_ownership as ownership
from siro.persistence.sqlite import SQLiteStore
home, data, entered, shutdown, finishing, release, finished, destination = map(Path, sys.argv[1:9])
command = sys.argv[9]
pwd.getpwuid = lambda uid: SimpleNamespace(pw_dir=str(home))
original_initialize = SQLiteStore._initialize_sync
def initialize(store):
    entered.touch()
    deadline = time.monotonic() + 8
    while not release.exists():
        if time.monotonic() >= deadline:
            raise AssertionError('synthetic SQLite release missing')
        time.sleep(.005)
    try:
        with closing(sqlite3.connect(store.path)) as connection, connection:
            connection.execute("UPDATE owner_fixture SET value='old-owned-IO-finished'")
        original_initialize(store)
    finally:
        finished.touch()
SQLiteStore._initialize_sync = initialize
original_shutdown = asyncio.BaseEventLoop.shutdown_default_executor
async def stop_executor(loop, *args, **kwargs):
    shutdown.touch()
    return await original_shutdown(loop, *args, **kwargs)
asyncio.BaseEventLoop.shutdown_default_executor = stop_executor
original_finish = ownership._DataOwner._finish
def finish(owner):
    finishing.touch()
    return original_finish(owner)
ownership._DataOwner._finish = finish
arguments = (['backup', '--data', str(data), str(destination)] if command == 'backup'
             else ['demo', '--data', str(data), '--once', 'synthetic'])
try:
    result = cli.main(arguments)
except KeyboardInterrupt:
    print(json.dumps({'status': 'cancelled'}), flush=True)
    raise SystemExit(130)
else:
    print(json.dumps({'unexpected_success': result}), flush=True)
"""
    )
    process = subprocess.Popen(
        [
            sys.executable,
            str(program),
            *map(
                str, (account, data, entered, shutdown, finishing, release, finished, destination)
            ),
            command,
        ],
        env=child_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_marker(entered, process)
        process.send_signal(signal.SIGINT)
        wait_marker(shutdown, process)
        process.send_signal(signal.SIGINT)
        wait_marker(finishing, process)
        process.send_signal(signal.SIGINT)
        time.sleep(0.02)
        assert process.poll() is None and not finished.exists()
        with pytest.raises(BlockingIOError), kernel_owner(database, account):
            pytest.fail("next owner must wait for the actual old IO thread")
        if command == "backup":
            with pytest.raises(BlockingIOError), kernel_owner(destination, account):
                pytest.fail("write target must remain owned until the actual old IO joins")
        release.touch()
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 130 and json.loads(stdout) == {"status": "cancelled"}
        assert not stderr and finished.exists() and not destination.exists()
        if command == "backup":
            with kernel_owner(destination, account):
                pass
        with (
            kernel_owner(database, account),
            closing(sqlite3.connect(database)) as connection,
            connection,
        ):
            connection.execute("UPDATE owner_fixture SET value='next-owner-write'")
        assert any("next-owner-write" in line for line in dump(database))
    finally:
        release.touch()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        for pipe in (process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


def test_actual_gateway_process_blocks_competitors_until_shutdown(
    tmp_path: Path, account: Path
) -> None:
    data = tmp_path / "data"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = int(listener.getsockname()[1])
    assert port != 8026
    code = (
        "import pwd,sys; from types import SimpleNamespace; "
        "pwd.getpwuid=lambda uid:SimpleNamespace(pw_dir=sys.argv[1]); "
        "from siro.services.presentation.gateway import main; main()"
    )
    environment = child_environment()
    environment.update(SIRO_DATA_DIR=str(data), SIRO_GATEWAY_PORT=str(port))
    with (tmp_path / "gateway.log").open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-c", code, str(account)],
            env=environment,
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 15
            while True:
                assert process.poll() is None, (tmp_path / "gateway.log").read_text()
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/health/live", timeout=0.3
                    ) as response:
                        assert json.load(response) == {"state": "alive"}
                    break
                except (urllib.error.URLError, TimeoutError):
                    assert time.monotonic() < deadline, "synthetic gateway startup timed out"
                    time.sleep(0.02)
            before = dump(data / "siro.db")
            with pytest.raises(BlockingIOError), kernel_owner(data / "siro.db", account):
                pytest.fail("running gateway must hold its data key")
            blocked = subprocess.run(
                [sys.executable, "-c", code, str(account)],
                env=environment,
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert (
                blocked.returncode == 1 and blocked.stderr.strip() == "SIRO data is already in use"
            )
            assert main(["restore", "--data", str(data), str(tmp_path / "not-opened.db")]) == 1
            assert dump(data / "siro.db") == before
            process.terminate()
            assert process.wait(timeout=10) in (0, -signal.SIGTERM)
            assert "Application shutdown complete." in (tmp_path / "gateway.log").read_text()
            with kernel_owner(data / "siro.db", account):
                pass
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)


@pytest.mark.parametrize("bundle", [False, True])
def test_backup_refuses_busy_foreign_write_target_before_any_database_work(
    tmp_path: Path, account: Path, capsys: pytest.CaptureFixture[str], bundle: bool
) -> None:
    data, other = tmp_path / "source", tmp_path / "other"
    data.mkdir()
    other.mkdir()
    source, destination = data / "siro.db", other / "siro.db"
    seed(source, "source-snapshot")
    seed(destination, "foreign-managed-latest")
    source_before, target_before = dump(source), dump(destination)
    source_bytes, target_bytes = source.read_bytes(), destination.read_bytes()
    target_inode = destination.stat().st_ino
    arguments = ["backup", "--data", str(data)]
    if bundle:
        config = tmp_path / "config.json"
        config.write_text(SiroSettings().model_dump_json())
        arguments.extend(["--config", str(config)])
    arguments.append(str(destination))

    with kernel_owner(destination, account):
        assert main(arguments) == 1

    assert json.loads(capsys.readouterr().out) == {"status": "data_in_use"}
    assert dump(source) == source_before and dump(destination) == target_before
    assert source.read_bytes() == source_bytes and destination.read_bytes() == target_bytes
    assert destination.stat().st_ino == target_inode


@pytest.mark.parametrize("alias", [False, True])
@pytest.mark.parametrize("bundle", [False, True])
def test_backup_cannot_replace_its_own_source_database(
    tmp_path: Path, account: Path, capsys: pytest.CaptureFixture[str], alias: bool, bundle: bool
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database = data / "siro.db"
    seed(database, "latest-completed")
    before, inode = database.read_bytes(), database.stat().st_ino
    destination = database
    if alias:
        destination = tmp_path / "alias.db"
        destination.symlink_to(database)

    arguments = ["backup", "--data", str(data)]
    if bundle:
        config = tmp_path / "config.json"
        config.write_text(SiroSettings().model_dump_json())
        arguments.extend(["--config", str(config)])
    arguments.append(str(destination))
    assert main(arguments) == 1

    assert json.loads(capsys.readouterr().out) == {"status": "invalid_backup_destination"}
    assert database.read_bytes() == before and database.stat().st_ino == inode


def make_bundle(path: Path, database: Path) -> None:
    content = {
        "siro.db": database.read_bytes(),
        "config.json": SiroSettings().model_dump_json().encode(),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in content.items():
            archive.writestr(name, raw)
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": 1,
                    "files": {
                        name: hashlib.sha256(raw).hexdigest() for name, raw in content.items()
                    },
                }
            ),
        )


def test_backup_cannot_replace_its_input_configuration(
    tmp_path: Path, account: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database = data / "siro.db"
    seed(database, "latest-completed")
    config = tmp_path / "config.json"
    config.write_text(SiroSettings().model_dump_json())
    before, config_before = database.read_bytes(), config.read_bytes()

    assert main(["backup", "--data", str(data), "--config", str(config), str(config)]) == 1

    assert json.loads(capsys.readouterr().out) == {"status": "invalid_backup_destination"}
    assert database.read_bytes() == before and config.read_bytes() == config_before


def test_restore_refuses_busy_foreign_configuration_write_target(
    tmp_path: Path, account: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data, other = tmp_path / "data", tmp_path / "other"
    data.mkdir()
    other.mkdir()
    database, foreign, backup = data / "siro.db", other / "siro.db", tmp_path / "backup.db"
    seed(database, "latest-completed")
    seed(foreign, "foreign-managed-latest")
    seed(backup, "old-snapshot")
    source = tmp_path / "backup.zip"
    make_bundle(source, backup)
    before, foreign_before, source_before = dump(database), dump(foreign), source.read_bytes()
    with kernel_owner(foreign, account):
        assert main(["restore", "--data", str(data), "--config", str(foreign), str(source)]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "data_in_use"}
    assert dump(database) == before and dump(foreign) == foreign_before
    assert source.read_bytes() == source_before


@pytest.mark.parametrize("config_target", ["database", "archive"])
def test_restore_configuration_cannot_replace_its_database_or_source_backup(
    tmp_path: Path, account: Path, capsys: pytest.CaptureFixture[str], config_target: str
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database, backup = data / "siro.db", tmp_path / "backup.db"
    seed(database, "latest-completed")
    seed(backup, "old-snapshot")
    source = tmp_path / "backup.zip"
    make_bundle(source, backup)
    before, source_before = dump(database), source.read_bytes()
    target = database if config_target == "database" else source
    assert main(["restore", "--data", str(data), "--config", str(target), str(source)]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "invalid_restore_configuration"}
    assert dump(database) == before and source.read_bytes() == source_before
