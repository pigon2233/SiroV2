"""Actual bounded SIGINT/flock/SQLite probe of a naive outer-context prototype.

This intentionally demonstrates the rejected lifetime assumption, not production D50.
Every process, database and marker is synthetic and owned by this probe.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import platform
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path


CHILD = r"""
import asyncio,fcntl,os,sqlite3,sys,time
from pathlib import Path
root=Path(sys.argv[1]); original=asyncio.BaseEventLoop.shutdown_default_executor
async def marked(self,*args,**kwargs):
    (root/'shutdown-entered').touch()
    return await original(self,*args,**kwargs)
asyncio.BaseEventLoop.shutdown_default_executor=marked
def work():
    (root/'thread-entered').touch()
    until=time.monotonic()+4
    while not (root/'release-thread').exists() and time.monotonic()<until:
        time.sleep(.005)
    with sqlite3.connect(root/'synthetic.db') as connection:
        connection.execute("UPDATE state SET value='late-old-owner-write'")
    (root/'thread-finished').touch()
async def handler():
    await asyncio.to_thread(work)
fd=os.open(root/'owner.lock',os.O_CREAT|os.O_RDWR|os.O_CLOEXEC,0o600)
fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
try:
    asyncio.run(handler())
except KeyboardInterrupt:
    pass
finally:
    os.close(fd)
    (root/'lease-released').touch()
"""


def run() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="siro-d50-signal-contract-") as name:
        root = Path(name)
        with closing(sqlite3.connect(root / "synthetic.db")) as connection, connection:
            connection.execute("CREATE TABLE state(value TEXT)")
            connection.execute("INSERT INTO state VALUES ('latest')")
        child = subprocess.Popen(
            [sys.executable, "-c", CHILD, str(root)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        def wait(path: Path) -> None:
            deadline = time.monotonic() + 2
            while not path.exists():
                if child.poll() is not None:
                    raise AssertionError("owned child exited before its phase marker")
                if time.monotonic() > deadline:
                    raise TimeoutError(path.name)
                time.sleep(0.005)

        descriptor: int | None = None
        try:
            wait(root / "thread-entered")
            child.send_signal(signal.SIGINT)
            wait(root / "shutdown-entered")
            child.send_signal(signal.SIGINT)
            wait(root / "lease-released")
            thread_pending = not (root / "thread-finished").exists()
            descriptor = os.open(root / "owner.lock", os.O_RDWR | os.O_CLOEXEC)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                acquired = False
            if acquired:
                with closing(sqlite3.connect(root / "synthetic.db")) as connection, connection:
                    connection.execute("UPDATE state SET value='new-maintenance-owner'")
            (root / "release-thread").touch()
            _stdout, stderr = child.communicate(timeout=3)
            with closing(sqlite3.connect(root / "synthetic.db")) as connection:
                final = connection.execute("SELECT value FROM state").fetchone()[0]
            report = {
                "python": platform.python_version(),
                "kernel": platform.release(),
                "profile": "actual naive outer-context prototype; not production D50",
                "second_sigint_during_actual_executor_shutdown": True,
                "lease_released_while_thread_pending": thread_pending,
                "new_owner_acquired_before_old_thread_join": acquired,
                "latest_db_value_after_both": final,
                "child_exit": child.returncode,
                "child_stderr_present": bool(stderr),
                "synthetic_only": True,
                "private_data_read": False,
                "production_source_changed": False,
            }
        finally:
            (root / "release-thread").touch()
            if descriptor is not None:
                os.close(descriptor)
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=3)
    report["owned_child_joined"] = True
    report["temporary_workspace_removed"] = not root.exists()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    rendered = json.dumps(run(), indent=2) + "\n"
    if arguments.output is not None:
        arguments.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
