from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from siro.adapters.computer import (
    ComputerActionError,
    ProcessDriver,
    ScopedFileDriver,
    ScopeViolation,
)


def test_a16_scoped_files_symlinks_atomic_write_move_and_replay(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    (allowed / "escape").symlink_to(outside, target_is_directory=True)
    driver = ScopedFileDriver((allowed,))

    with pytest.raises(ScopeViolation):
        driver.read_text(allowed / "escape" / "secret.txt")
    with pytest.raises(ScopeViolation):
        driver.write_text("escape-write", allowed / "escape" / "new.txt", "bad")

    target = allowed / "safe.txt"
    assert driver.write_text("write-1", target, "hello") == 5
    assert driver.write_text("write-1", target, "changed replay") == 5
    assert driver.read_text(target) == "hello"
    assert driver.move("move-1", target, allowed / "moved.txt").endswith("moved.txt")
    assert driver.move("move-1", target, allowed / "other.txt").endswith("moved.txt")
    assert driver.list(allowed) == ("escape", "moved.txt")


@pytest.mark.asyncio
async def test_a16_argv_execution_scope_timeout_output_and_cancel(tmp_path: Path) -> None:
    driver = ProcessDriver((tmp_path,), output_limit=100)
    result = await driver.run(
        "run-safe", (sys.executable, "-c", "print('safe')"), tmp_path, timeout=1
    )
    assert result.returncode == 0
    assert result.stdout == b"safe\n"
    replay = await driver.run(
        "run-safe", (sys.executable, "-c", "print('must not execute')"), tmp_path, timeout=1
    )
    assert replay == result
    with pytest.raises(ScopeViolation):
        await driver.run("outside", (sys.executable, "-c", "pass"), Path("/"), timeout=1)
    with pytest.raises(ComputerActionError, match="output"):
        await driver.run("flood", (sys.executable, "-c", "print('x'*200)"), tmp_path, timeout=1)
    with pytest.raises(ComputerActionError, match="timed out"):
        await driver.run(
            "timeout",
            (sys.executable, "-c", "import time; time.sleep(5)"),
            tmp_path,
            timeout=0.05,
        )

    pid = await driver.start(
        "start-1", (sys.executable, "-c", "import time; time.sleep(5)"), tmp_path
    )
    assert (
        await driver.start("start-1", (sys.executable, "-c", "raise SystemExit(1)"), tmp_path)
        == pid
    )
    assert driver.list_managed() == (pid,)
    await driver.stop(pid)
    assert driver.list_managed() == ()
    with pytest.raises(ScopeViolation):
        await driver.stop(pid)

    task = asyncio.create_task(
        driver.run(
            "cancel",
            (sys.executable, "-c", "import time; time.sleep(5)"),
            tmp_path,
            timeout=5,
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
