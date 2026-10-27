"""R10 drill: real gateway processes are killed mid-run; code rollback keeps all data."""

from __future__ import annotations

import asyncio
import json
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from test_release_source_process import (
    HEALTH,
    KEY,
    environment,
    port_at,
    prepared_project,
    retained,
    seed,
    signed,
    source_bundle,
)

from siro.core.releases import ReleaseManager, ReleaseManifest
from siro.persistence.sqlite import SQLiteStore, load_migrations


@contextmanager
def running_gateway(root: Path, launcher: Path, version: str) -> Iterator[subprocess.Popen[bytes]]:
    port = port_at()
    log_path = root / f"drill-{version}-{time.monotonic_ns()}.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-B", str(launcher)],
            env=environment(root, port),
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 20
            while True:
                assert process.poll() is None, log_path.read_text()
                try:
                    url = f"http://127.0.0.1:{port}/health/ready"
                    with urllib.request.urlopen(url, timeout=0.3) as response:
                        ready = json.load(response)
                    if ready.get("state") == "healthy":
                        assert ready["release"]["version"] == version
                        break
                except (urllib.error.URLError, TimeoutError):
                    pass
                assert time.monotonic() < deadline, log_path.read_text()
                time.sleep(0.02)
            yield process
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)


def crash(process: subprocess.Popen[bytes]) -> None:
    process.send_signal(signal.SIGKILL)
    assert process.wait(timeout=10) == -signal.SIGKILL


def test_sigkill_midrun_then_rollback_keeps_every_committed_row(tmp_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="crash-drill-", dir=tmp_path) as temporary:
        root = Path(temporary)
        launcher = prepared_project(root)
        database = root / "data/siro.db"
        asyncio.run(SQLiteStore(database).initialize())
        seed(database, "before-first")
        manager = ReleaseManager(
            root / "manager", KEY, current_schema=len(load_migrations()), database=database
        )
        manifests: dict[str, ReleaseManifest] = {}
        for version, phase in (("1.0.0", "during-first"), ("2.0.0", "during-second")):
            bundle = source_bundle(root, version)
            manifests[version] = signed(bundle, version)
            assert manager.stage_and_activate(bundle, manifests[version], HEALTH).status == (
                "activated"
            )
            with running_gateway(root, launcher, version) as process:
                seed(database, phase)  # committed while the real process is live
                crash(process)  # no drain: the process dies abruptly
            with closing(sqlite3.connect(database)) as connection:
                assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            # Restart the same version after the crash: it must come back healthy.
            with running_gateway(root, launcher, version) as process:
                process.terminate()
                assert process.wait(timeout=10) in (0, -signal.SIGTERM)
        expected = retained(database)
        assert all(len(values) == 3 for values in expected.values())
        assert manager.rollback().status == "rolled_back"
        assert manager.active_version() == "1.0.0"
        assert retained(database) == expected  # rollback never restores an old backup
        with running_gateway(root, launcher, "1.0.0") as process:
            process.terminate()
            assert process.wait(timeout=10) in (0, -signal.SIGTERM)
        assert retained(database) == expected


def test_incompatible_schema_release_is_refused_without_touching_data(tmp_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="schema-drill-", dir=tmp_path) as temporary:
        root = Path(temporary)
        prepared_project(root)
        database = root / "data/siro.db"
        asyncio.run(SQLiteStore(database).initialize())
        seed(database, "before")
        before = retained(database)
        manager = ReleaseManager(
            root / "manager", KEY, current_schema=len(load_migrations()), database=database
        )
        bundle = source_bundle(root, "9.0.0")
        good = signed(bundle, "9.0.0")
        wrong = good.model_copy(
            update={"min_schema": good.min_schema + 1, "max_schema": good.max_schema + 1}
        )
        assert manager.stage_and_activate(bundle, wrong, HEALTH).status in {
            "incompatible_schema",
            "invalid_manifest",
        }
        assert manager.active_version() is None
        assert retained(database) == before
