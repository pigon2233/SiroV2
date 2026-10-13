from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytest

from siro.adapters.computer import (
    AsyncScopedFileDriver,
    ComputerActionError,
    ProcessDriver,
    ScopedFileDriver,
    ScopeViolation,
)
from siro.core.outcomes import ActionOutcome


class CapturingOutcomes:
    def __init__(self) -> None:
        self.values: list[tuple[str, ActionOutcome, object | None]] = []

    async def report_action(
        self,
        action_id: str,
        outcome: ActionOutcome,
        *,
        occurred_at: datetime,
        importance: float,
        controllability: float,
        expected: object | None = None,
        observed: object | None = None,
    ) -> None:
        del occurred_at, importance, controllability, expected
        self.values.append((action_id, outcome, observed))


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
async def test_async_file_readback_reports_once_and_rejects_action_reuse(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outcomes = CapturingOutcomes()
    driver = AsyncScopedFileDriver(ScopedFileDriver((allowed,)), outcome_reporter=outcomes)
    source = allowed / "source.txt"
    assert await driver.write_text("write-async", source, "verified") == 8
    assert await driver.write_text("write-async", source, "verified") == 8
    destination = allowed / "destination.txt"
    assert (await driver.move("move-async", source, destination)).endswith("destination.txt")
    assert (await driver.move("move-async", source, destination)).endswith("destination.txt")
    with pytest.raises(ComputerActionError, match="reused"):
        await driver.write_text("write-async", source, "different")
    assert destination.read_text(encoding="utf-8") == "verified"
    assert [value[:2] for value in outcomes.values] == [
        ("write-async", "confirmed"),
        ("move-async", "confirmed"),
    ]


@pytest.mark.asyncio
async def test_a16_argv_execution_scope_timeout_output_and_cancel(tmp_path: Path) -> None:
    outcomes = CapturingOutcomes()
    driver = ProcessDriver((tmp_path,), output_limit=100, outcome_reporter=outcomes)
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
    await driver.stop(pid, action_id="stop-1")
    await driver.stop(pid, action_id="stop-1")
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
    assert ("run-safe", "confirmed", 0) in outcomes.values
    assert any(value[:2] == ("stop-1", "confirmed") for value in outcomes.values)
    assert any(value[:2] == ("flood", "error") for value in outcomes.values)
    assert ("timeout", "error", "timeout") in outcomes.values
    assert sum(value[0] == "run-safe" for value in outcomes.values) == 1
