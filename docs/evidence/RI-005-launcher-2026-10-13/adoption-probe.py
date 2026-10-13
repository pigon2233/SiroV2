"""Synthetic first-adoption evidence; never inspects or signals unrelated processes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import select
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True), flush=True)


def legacy_writer(database: Path) -> None:
    # Intentionally models a previous binary: SQLite only, no D50 advisory lease.
    connection = sqlite3.connect(database, timeout=2)
    try:
        mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        connection.execute("CREATE TABLE adoption_events (id INTEGER PRIMARY KEY, marker TEXT)")
        connection.execute("INSERT INTO adoption_events(marker) VALUES ('legacy-before-lease')")
        connection.commit()
        emit({"status": "ready", "journal_mode": mode, "connection_open": True})
        for line in sys.stdin:
            command = json.loads(line)
            if command == "write-after-lease":
                connection.execute(
                    "INSERT INTO adoption_events(marker) VALUES ('legacy-after-lease')"
                )
                connection.commit()
                emit({"status": "legacy-committed", "connection_open": True})
            elif command == "stop":
                connection.close()
                connection = None
                emit({"status": "stopped", "connection_closed": True})
                return
            else:
                raise ValueError("unsupported synthetic command")
    finally:
        if connection is not None:
            connection.close()


def managed_probe(database: Path, coordination: Path) -> None:
    import siro.adapters.data_ownership as ownership

    # Only the coordination-directory locator is redirected to this probe's own
    # temporary directory. Canonical-key calculation, fd validation and flock
    # remain the unmodified production adapter. Never touch the account directory.
    ownership._owner_directory = lambda: coordination
    try:
        with ownership.exclusive_data_owner(database):
            emit({"status": "managed-acquired"})
    except ownership.DataOwnerBusyError:
        emit({"status": "managed-busy"})


def read_message(child: subprocess.Popen[str], timeout: float = 8) -> dict[str, Any]:
    assert child.stdout is not None
    ready, _, _ = select.select([child.stdout], [], [], timeout)
    if not ready:
        raise TimeoutError("owned synthetic child did not respond")
    line = child.stdout.readline()
    if not line:
        raise RuntimeError("owned synthetic child exited before response")
    return json.loads(line)


def request(child: subprocess.Popen[str], command: str) -> dict[str, Any]:
    assert child.stdin is not None
    child.stdin.write(json.dumps(command) + "\n")
    child.stdin.flush()
    return read_message(child)


def spawn(script: Path, mode: str, database: Path, coordination: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            str(script),
            "--child",
            mode,
            "--database",
            str(database),
            "--coordination",
            str(coordination),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ.copy(),
    )


def finish(child: subprocess.Popen[str]) -> dict[str, Any]:
    if child.stdin is not None:
        child.stdin.close()
    returncode = child.wait(timeout=8)
    assert child.stdout is not None and child.stderr is not None
    tail = child.stdout.read()
    stderr = child.stderr.read()
    child.stdout.close()
    child.stderr.close()
    assert returncode == 0 and not tail and not stderr
    return {"exit_code": returncode, "joined": True, "stderr_empty": not stderr}


def run() -> dict[str, Any]:
    import siro.adapters.data_ownership as ownership

    script = Path(__file__).resolve()
    repository = script.parents[3]
    reviewed = [
        "src/siro/adapters/data_ownership.py",
        "src/siro/cli.py",
        "src/siro/services/presentation/gateway.py",
        "src/siro/core/releases.py",
        "scripts/start",
        "scripts/stop",
    ]
    source_hashes = {
        path: hashlib.sha256((repository / path).read_bytes()).hexdigest() for path in reviewed
    }
    events: list[dict[str, Any]] = []
    children: list[subprocess.Popen[str]] = []
    original_locator = ownership._owner_directory
    temporary = tempfile.TemporaryDirectory(prefix="siro-adoption-owned-")
    temporary_path = Path(temporary.name)

    def record(event: str, **fields: Any) -> None:
        events.append({"event": event, "monotonic_ns": time.monotonic_ns(), **fields})

    try:
        database = temporary_path / "synthetic.sqlite3"
        coordination = temporary_path / "owned-coordination"
        ownership._owner_directory = lambda: coordination
        legacy = spawn(script, "legacy", database, coordination)
        children.append(legacy)
        ready = read_message(legacy)
        assert ready == {"status": "ready", "journal_mode": "wal", "connection_open": True}
        record("legacy-running", **ready)
        with ownership.exclusive_data_owner(database):
            record("new-lease-acquired-while-legacy-alive", legacy_alive=legacy.poll() is None)
            connection = sqlite3.connect(database, timeout=2)
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO adoption_events(marker) VALUES ('sqlite-preflight')"
                )
                connection.commit()
            finally:
                connection.close()
            assert legacy.poll() is None
            record("sqlite-write-preflight-succeeded-while-legacy-alive")
            late = request(legacy, "write-after-lease")
            assert late["status"] == "legacy-committed" and legacy.poll() is None
            record("legacy-write-committed-after-new-lease", **late)
            contender = spawn(script, "managed", database, coordination)
            children.append(contender)
            contention = read_message(contender)
            assert contention == {"status": "managed-busy"}
            record("managed-contender-refused", **contention, **finish(contender))
            stop = request(legacy, "stop")
            assert stop == {"status": "stopped", "connection_closed": True}
            record("known-legacy-explicit-close", **stop)
            record("known-legacy-joined", **finish(legacy))
            connection = sqlite3.connect(database, timeout=2)
            try:
                before = [
                    row[0]
                    for row in connection.execute("SELECT marker FROM adoption_events ORDER BY id")
                ]
                assert before == ["legacy-before-lease", "sqlite-preflight", "legacy-after-lease"]
                connection.execute(
                    "INSERT INTO adoption_events(marker) VALUES ('managed-after-stop')"
                )
                connection.commit()
                after = [
                    row[0]
                    for row in connection.execute("SELECT marker FROM adoption_events ORDER BY id")
                ]
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                connection.close()
            assert after == [*before, "managed-after-stop"] and integrity == "ok"
            record(
                "managed-adoption-after-joined-stop",
                source_before=before,
                source_after=after,
                integrity=integrity,
                lease_continuously_held=True,
            )
        successor = spawn(script, "managed", database, coordination)
        children.append(successor)
        acquired = read_message(successor)
        assert acquired == {"status": "managed-acquired"}
        record("next-managed-owner-after-release", **acquired, **finish(successor))
    finally:
        ownership._owner_directory = original_locator
        for child in children:
            if child.poll() is None:
                # Failure cleanup can signal ONLY children created by this script.
                child.terminate()
                child.wait(timeout=8)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
        temporary.cleanup()
    assert not temporary_path.exists() and all(child.poll() is not None for child in children)
    source_hashes_after = {
        path: hashlib.sha256((repository / path).read_bytes()).hexdigest() for path in reviewed
    }
    assert (
        source_hashes["src/siro/adapters/data_ownership.py"]
        == source_hashes_after["src/siro/adapters/data_ownership.py"]
    )
    return {
        "status": "PASS",
        "profile": "Linux/same-UID/local-FS/synthetic-WAL",
        "controlled_boundary": "only _owner_directory redirected to owned temporary directory",
        "real_operations": [
            "SQLite WAL commits",
            "production canonical keys and kernel flock",
            "child wait/connection close",
            "SQLite integrity check",
        ],
        "checks": {
            "new_lease_does_not_prove_legacy_stopped": True,
            "sqlite_preflight_does_not_prove_legacy_stopped": True,
            "same_protocol_managed_contender_refused": True,
            "explicit_owned_legacy_close_and_join_before_adoption": True,
            "latest_legacy_commit_preserved": True,
            "continuously_held_lease_through_adoption": True,
            "next_managed_owner_acquired_after_release": True,
            "all_owned_children_joined": True,
            "temporary_root_removed": True,
        },
        "children_created": len(children),
        "source_hashes": source_hashes,
        "events": events,
        "source_hashes_after": source_hashes_after,
        "probe_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "not_verified": [
            "unknown/external writer absence",
            "live SIRO first adoption",
            "production launcher handoff",
            "power loss",
            "other OS or network FS",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=("legacy", "managed"))
    parser.add_argument("--database", type=Path)
    parser.add_argument("--coordination", type=Path)
    arguments = parser.parse_args()
    if arguments.child == "legacy":
        legacy_writer(arguments.database)
    elif arguments.child == "managed":
        managed_probe(arguments.database, arguments.coordination)
    else:
        emit(run())


if __name__ == "__main__":
    main()
