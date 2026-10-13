"""Independent synthetic actual CLI/SQLite/process-signal lifecycle probe.

Controlled timing only: all SQL copies, CLI parsing, owner leases, temporary
workspace creation and cleanup execute the selected public production source.
No private configuration, database, provider or live service is opened.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from siro.adapters import data_ownership as owner
from siro.config import SiroSettings
from siro.persistence.sqlite import SQLiteStore, apply_migrations, load_migrations

SELF = Path(__file__).resolve()
REPOSITORY = SELF.parents[3]
PATHS = (
    "src/siro/persistence/sqlite.py",
    "src/siro/operations.py",
    "src/siro/adapters/data_ownership.py",
    "src/siro/cli.py",
    "src/siro/services/presentation/gateway.py",
)


def wait_file(path: Path, timeout: float = 8) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() > deadline:
            raise RuntimeError(f"bounded synthetic handshake timed out: {path.name}")
        time.sleep(0.002)


def worker(root: Path, bundle: bool, after_commit: bool, in_progress: bool) -> int:
    from siro import cli

    owner._owner_directory = lambda: root / "domain"
    tempfile.tempdir = str(root / "staging")
    original_backup = SQLiteStore._backup_sync
    original_wait = asyncio.wait
    original_shutdown = asyncio.BaseEventLoop.shutdown_default_executor
    original_finish = owner._DataOwner._finish
    original_cancel_all = asyncio.runners._cancel_all_tasks
    original_connect = sqlite3.connect
    cancelled_waits = 0
    entered_waits = 0

    class Connection(sqlite3.Connection):
        def backup(self, target: sqlite3.Connection, **kwargs: object) -> None:
            original_progress = kwargs.get("progress")
            paused = False

            def progress(status: int, remaining: int, total: int) -> None:
                nonlocal paused
                if in_progress and status != sqlite3.SQLITE_DONE and not paused:
                    paused = True
                    (root / "actual-copy-progress.json").write_text(
                        json.dumps({"status": status, "remaining": remaining, "total": total})
                    )
                    (root / "backup-entered").touch()
                    wait_file(root / "release", 15)
                if original_progress is not None:
                    original_progress(status, remaining, total)

            kwargs["progress"] = progress
            super().backup(target, **kwargs)

        def close(self) -> None:
            with (root / "explicit-connections-closed.txt").open("a") as output:
                output.write("closed\n")
            super().close()

    def connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        kwargs["factory"] = Connection
        return original_connect(*args, **kwargs)

    def backup(self: SQLiteStore, destination: Path, *args: object, **kwargs: object) -> None:
        (root / "snapshot-path.json").write_text(json.dumps(str(destination)))
        if after_commit:
            original_backup(self, destination, *args, **kwargs)
            (root / "copy-committed-before-cancellation").touch()
        if not in_progress:
            (root / "backup-entered").touch()
            wait_file(root / "release", 15)
        try:
            if not after_commit:
                original_backup(self, destination, *args, **kwargs)
        finally:
            (root / "backup-finished").touch()

    async def wait(*args: object, **kwargs: object) -> object:
        nonlocal cancelled_waits, entered_waits
        entered_waits += 1
        (root / f"wait-entered-{entered_waits}").touch()
        try:
            return await original_wait(*args, **kwargs)
        except asyncio.CancelledError:
            cancelled_waits += 1
            (root / f"wait-cancelled-{cancelled_waits}").touch()
            raise

    async def shutdown(loop: object, *args: object, **kwargs: object) -> None:
        (root / "shutdown-entered").touch()
        return await original_shutdown(loop, *args, **kwargs)

    def cancel_all(loop: object) -> None:
        (root / "runner-cancel-all-entered").touch()
        return original_cancel_all(loop)

    def finish(resource: object) -> bool:
        (root / "owner-finishing").touch()
        return original_finish(resource)

    SQLiteStore._backup_sync = backup
    asyncio.wait = wait
    asyncio.BaseEventLoop.shutdown_default_executor = shutdown
    asyncio.runners._cancel_all_tasks = cancel_all
    owner._DataOwner._finish = finish
    sqlite3.connect = connect
    arguments = ["backup", "--data", str(root / "data")]
    if bundle:
        arguments.extend(["--config", str(root / "settings.json")])
    arguments.append(str(root / ("archive.zip" if bundle else "snapshot.db")))
    previous_sigint_handler = signal.getsignal(signal.SIGINT)
    try:
        return cli.main(arguments)
    except (KeyboardInterrupt, asyncio.CancelledError) as error:
        print(json.dumps({"interrupted": type(error).__name__}), flush=True)
        return 130
    finally:
        (root / "sigint-handler-restored.json").write_text(
            json.dumps(signal.getsignal(signal.SIGINT) == previous_sigint_handler)
        )


def key_busy(root: Path, path: Path) -> bool:
    with patch.object(owner, "_owner_directory", return_value=root / "domain"):
        try:
            with owner.exclusive_data_owner(path):
                return False
        except owner.DataOwnerBusyError:
            return True


def run_case(
    bundle: bool,
    signals: int,
    owned: bool,
    after_commit: bool = False,
    in_progress: bool = False,
    managed_signals: bool = False,
) -> dict[str, object]:
    temporary = tempfile.TemporaryDirectory(prefix="siro-fix015-signal-")
    root = Path(temporary.name)
    (root / "data").mkdir()
    (root / "staging").mkdir()
    source = root / "data" / "siro.db"
    destination = root / ("archive.zip" if bundle else "snapshot.db")
    fixed_temporary = destination.with_suffix(destination.suffix + ".tmp")
    destination.write_bytes(b"synthetic-original-output")
    fixed_temporary.write_bytes(b"synthetic-original-fixed-temporary")
    previous_output = destination.read_bytes()
    previous_fixed = fixed_temporary.read_bytes()
    with closing(sqlite3.connect(source)) as connection:
        apply_migrations(connection, load_migrations())
        connection.execute("CREATE TABLE signal_fixture(value TEXT)")
        connection.execute("INSERT INTO signal_fixture VALUES ('source-snapshot')")
        connection.commit()
    (root / "settings.json").write_text(SiroSettings().model_dump_json())
    previous_settings = (root / "settings.json").read_bytes()
    process = None
    facts: dict[str, object] = {
        "bundle": bundle,
        "signals": signals,
        "retained_job_expected": owned,
        "cancel_after_actual_raw_commit": after_commit,
        "cancel_during_actual_sqlite_progress": in_progress,
        "backup_handler_manages_repeated_sigint": managed_signals,
    }
    try:
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SIRO_") and key not in {"GROQ_API_KEY", "OPENAI_API_KEY"}
        }
        process = subprocess.Popen(
            [
                sys.executable,
                str(SELF),
                "worker",
                str(root),
                str(int(bundle)),
                str(int(after_commit)),
                str(int(in_progress)),
            ],
            cwd=REPOSITORY,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        wait_file(root / "backup-entered")
        snapshot = Path(json.loads((root / "snapshot-path.json").read_text()))
        facts["actual_copy_committed_before_cancellation"] = (
            root / "copy-committed-before-cancellation"
        ).exists()
        if in_progress:
            facts["actual_non_done_progress"] = json.loads(
                (root / "actual-copy-progress.json").read_text()
            )
            facts["owned_scratch_present_before_cancellation"] = any(
                snapshot.parent.glob(f".{snapshot.name}.*.tmp")
            )
        facts["snapshot_parent_mode_before_cancel"] = oct(
            stat.S_IMODE(snapshot.parent.stat().st_mode)
        )
        process.send_signal(signal.SIGINT)
        wait_file(root / ("wait-cancelled-1" if owned else "shutdown-entered"))
        if managed_signals:
            # The actual backup coroutine has consumed cancellation and resumed
            # waiting on its one retained job before another signal is delivered.
            wait_file(root / "wait-entered-2")
        if signals == 3:
            if managed_signals:
                # Each real signal is consumed inside the actual retained job.
                # Runner.close must not begin until that work has resolved.
                for count in (2, 3):
                    process.send_signal(signal.SIGINT)
                    wait_file(root / f"wait-cancelled-{count}")
                    wait_file(root / f"wait-entered-{count + 1}")
            else:
                process.send_signal(signal.SIGINT)
                if owned:
                    wait_file(root / "wait-cancelled-2")
                else:
                    wait_file(root / "owner-finishing")
                process.send_signal(signal.SIGINT)
                wait_file(root / "owner-finishing")
        time.sleep(0.04)
        facts["child_alive_while_io_pending"] = process.poll() is None
        facts["owned_sync_backup_call_pending"] = not (root / "backup-finished").exists()
        facts["runner_close_started_while_backup_pending"] = (
            root / "runner-cancel-all-entered"
        ).exists()
        facts["consumed_async_wait_cancellations_while_backup_pending"] = len(
            list(root.glob("wait-cancelled-*"))
        )
        facts["actual_sql_copy_pending"] = not after_commit
        facts["snapshot_parent_exists_while_io_pending"] = snapshot.parent.exists()
        facts["source_busy_while_io_pending"] = key_busy(root, source)
        facts["destination_busy_while_io_pending"] = key_busy(root, destination)
        if bundle:
            facts["fixed_temporary_busy_while_io_pending"] = key_busy(root, fixed_temporary)
        facts["destination_retained_while_io_pending"] = destination.read_bytes() == previous_output
        (root / "release").touch()
        stdout, stderr = process.communicate(timeout=8)
        facts["child_exit"] = process.returncode
        facts["child_stdout"] = stdout.strip()
        facts["child_stderr_present"] = bool(stderr)
        facts["child_stderr"] = stderr.strip()
        facts["child_joined"] = process.poll() is not None
        facts["original_sigint_handler_restored_after_command"] = json.loads(
            (root / "sigint-handler-restored.json").read_text()
        )
        facts["actual_snapshot_io_finished"] = (root / "backup-finished").exists()
        closed = root / "explicit-connections-closed.txt"
        facts["explicit_connection_close_calls"] = (
            len(closed.read_text().splitlines()) if closed.exists() else 0
        )
        facts["settings_retained"] = (root / "settings.json").read_bytes() == previous_settings
        facts["fixed_temporary_retained"] = fixed_temporary.read_bytes() == previous_fixed
        facts["snapshot_exists_after_join"] = snapshot.exists()
        facts["staging_entries_after_join"] = sorted(
            str(path.relative_to(root / "staging")) for path in (root / "staging").rglob("*")
        )
        if bundle:
            facts["previous_final_archive_retained"] = destination.read_bytes() == previous_output
        else:
            facts["raw_output_replaced"] = destination.read_bytes() != previous_output
            if facts["raw_output_replaced"]:
                with closing(sqlite3.connect(destination)) as connection:
                    facts["raw_committed_value"] = connection.execute(
                        "SELECT value FROM signal_fixture"
                    ).fetchone()[0]
        with closing(sqlite3.connect(source)) as connection:
            facts["source_value_retained"] = (
                connection.execute("SELECT value FROM signal_fixture").fetchone()[0]
                == "source-snapshot"
            )
        kwargs = {"write_target": destination}
        if bundle:
            kwargs["temporary_write_target"] = fixed_temporary
        with (
            patch.object(owner, "_owner_directory", return_value=root / "domain"),
            owner.exclusive_data_owner(source, **kwargs),
        ):
            facts["all_keys_available_after_join"] = True
            destination.write_bytes(b"next-owner-output")
        time.sleep(0.04)
        facts["next_owner_output_retained"] = destination.read_bytes() == b"next-owner-output"
    except BaseException as error:
        facts["probe_error"] = f"{type(error).__name__}: {error}"
    finally:
        (root / "release").touch()
        if process is not None and process.poll() is None:
            try:
                process.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=3)
                facts["forced_fixture_cleanup"] = True
        facts["owned_child_joined_in_finally"] = process is None or process.poll() is not None
        temporary.cleanup()
        facts["synthetic_root_removed"] = not root.exists()
    return facts


def run(output: Path, owned: bool, managed_signals: bool = False) -> None:
    before = {path: hashlib.sha256((REPOSITORY / path).read_bytes()).hexdigest() for path in PATHS}
    cases = [
        run_case(bundle, signals, owned, managed_signals=managed_signals)
        for bundle in (True, False)
        for signals in (1, 3)
    ]
    cases.extend(
        run_case(False, signals, owned, after_commit=True, managed_signals=managed_signals)
        for signals in (1, 3)
    )
    cases.extend(
        run_case(True, signals, owned, in_progress=True, managed_signals=managed_signals)
        for signals in (1, 3)
    )
    after = {path: hashlib.sha256((REPOSITORY / path).read_bytes()).hexdigest() for path in PATHS}
    result = {
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "timing": "controlled pause before actual production SQLite copy; real process SIGINT",
        "source_sha256_at_start": before,
        "source_sha256_at_finish": after,
        "source_unchanged_during_probe": before == after,
        "cases": cases,
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if sys.argv[1] == "worker":
        raise SystemExit(
            worker(
                Path(sys.argv[2]),
                bool(int(sys.argv[3])),
                bool(int(sys.argv[4])),
                bool(int(sys.argv[5])),
            )
        )
    run(
        Path(sys.argv[1]),
        bool(int(sys.argv[2])),
        bool(int(sys.argv[3])) if len(sys.argv) > 3 else False,
    )
