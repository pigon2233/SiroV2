from __future__ import annotations

import asyncio
import os
import signal
import sqlite3
import threading
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest
from test_skill_activation import activation_module, installed
from test_strict_skill_worker import REAL, alive, descendants

from siro.adapters import skill_worker
from siro.core.skills import InstalledSkill, load_skill
from siro.services.tools.execution import ExecutionCleanupError, ExecutionContext

_MARKER = b"SIRO_ACTIVATION_CONTROLLED_STRICT_WAIT\n"


class _Processes:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.processes: list[asyncio.subprocess.Process] = []
        self.execution_processes: list[asyncio.subprocess.Process] = []
        self.pids: set[int] = set()
        self.restricted_wait = asyncio.Event()
        self.stderr = bytearray()
        original = asyncio.create_subprocess_exec

        async def spawn(*argv: str, **kwargs: Any) -> asyncio.subprocess.Process:
            process = await original(*argv, **kwargs)
            self.processes.append(process)
            self.pids.add(process.pid)
            if "--probe" not in argv:
                self.execution_processes.append(process)
                assert process.stderr is not None
                original_feed = process.stderr.feed_data
                observed = bytearray()

                def feed(data: bytes) -> None:
                    observed.extend(data)
                    self.stderr.extend(data)
                    if _MARKER in observed:
                        self.restricted_wait.set()
                    original_feed(data)

                monkeypatch.setattr(process.stderr, "feed_data", feed)
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    async def observe(self) -> None:
        await asyncio.wait_for(self.restricted_wait.wait(), 2)
        for _ in range(5):
            for process in self.processes:
                self.pids |= descendants(process.pid)
            await asyncio.sleep(0.002)

    async def cleanup(self, tasks: list[asyncio.Task[Any]]) -> None:
        for task in tasks:
            if not task.done():
                task.cancel()
        with suppress(TimeoutError):
            async with asyncio.timeout(3):
                await asyncio.gather(*tasks, return_exceptions=True)
        for process in self.processes:
            self.pids |= descendants(process.pid)
        # Failing probes clean only the exact synthetic processes captured by this fixture.
        for pid in self.pids:
            if alive(pid):
                with suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGKILL)
        async with asyncio.timeout(3):
            await asyncio.gather(*(process.wait() for process in self.processes))


@pytest.mark.asyncio
@REAL
async def test_actual_revoke_joins_restricted_worker_and_admitted_queue_without_second_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _store, registry, _catalog, package_hash = await installed(tmp_path)
    await owner.enable(package_hash)
    original = skill_worker._prepare_strict
    workspaces: list[Path] = []

    def controlled(workspace: Path, skill: InstalledSkill) -> InstalledSkill:
        verified = original(workspace, skill)
        workspaces.append(workspace)
        runner = workspace / "trusted" / "runner.py"
        source = runner.read_text()
        source = source.replace("import sys\n", "import sys\nimport time\n", 1)
        before_request = '    request = _read_object(Path("/trusted/request.json"), 65536)'
        assert source.count(before_request) == 1
        # Fixed template bytes remain unchanged. Only this fixture's trusted runner delays
        # after irreversible restrictions and after the normal --probe early return.
        runner.chmod(0o600)
        runner.write_text(
            source.replace(
                before_request,
                "    time.sleep(0.05)\n"
                '    sys.stderr.write("SIRO_ACTIVATION_CONTROLLED_STRICT_WAIT\\n")\n'
                "    sys.stderr.flush()\n"
                "    time.sleep(30)\n" + before_request,
                1,
            )
        )
        runner.chmod(0o400)
        return verified

    monkeypatch.setattr(skill_worker, "_prepare_strict", controlled)
    tracked = _Processes(monkeypatch)
    first = asyncio.create_task(
        owner.execute(
            {"text": "- [ ] first"}, ExecutionContext("first", "synthetic", "e", authorized=True)
        )
    )
    tasks: list[asyncio.Task[Any]] = [first]
    try:
        try:
            await tracked.observe()
        except TimeoutError as error:
            raise AssertionError(
                f"controlled runner marker missing: {tracked.stderr!r}; "
                f"job error={first.exception() if first.done() else 'pending'}"
            ) from error
        second = asyncio.create_task(
            owner.execute(
                {"text": "- [ ] queued"},
                ExecutionContext("second", "synthetic", "e", authorized=True),
            )
        )
        tasks.append(second)
        async with asyncio.timeout(1):
            while len(owner._jobs) != 2:
                await asyncio.sleep(0)
        assert not first.done() and not second.done()
        assert len(tracked.execution_processes) == 1
        result = await asyncio.wait_for(owner.revoke(package_hash), 2)
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        assert result["enabled"] is False
        assert all(isinstance(outcome, BaseException) for outcome in outcomes)
        assert not owner._jobs
        assert len(tracked.processes) == 2, "one actual probe and one actual execution only"
        assert len(tracked.execution_processes) == 1, "admitted queued job must never spawn"
        assert all(process.returncode is not None for process in tracked.processes)
        assert not any(alive(pid) for pid in tracked.pids)
        assert workspaces and all(not path.exists() for path in workspaces)
        managed_package = next((tmp_path / "managed").glob("*/manifest.json")).parent
        assert load_skill(managed_package).manifest_hash == package_hash
        assert not await registry.is_enabled("siro.text.checklist", "1.0.0")
    finally:
        await tracked.cleanup(tasks)
        await owner.close()


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize("action", ["caller", "revoke", "suspend", "close"])
async def test_real_sqlite_uncommitted_enable_is_joined_and_compensated_after_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    owner, store, registry, _catalog, package_hash = await installed(tmp_path)
    original = store._run_transaction_sync
    entered, release = threading.Event(), threading.Event()
    thread_ids: list[int] = []
    observed_states: list[str] = []

    def blocked_transaction[T](work: Callable[[sqlite3.Connection], T]) -> T:
        def inside(connection: sqlite3.Connection) -> T:
            result = work(connection)
            row = connection.execute(
                "SELECT state FROM skills WHERE skill_id='siro.text.checklist' AND version='1.0.0'"
            ).fetchone()
            if row is not None:
                observed_states.append(str(row["state"]))
                if row["state"] == "enabled" and not entered.is_set():
                    assert connection.in_transaction
                    thread_ids.append(threading.get_ident())
                    entered.set()
                    assert release.wait(3), "synthetic pre-commit release missing"
            return result

        return original(inside)

    monkeypatch.setattr(store, "_run_transaction_sync", blocked_transaction)
    enable = asyncio.create_task(owner.enable(package_hash))
    stopper: asyncio.Task[Any] | None = None
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.002)
        assert thread_ids == [thread_ids[0]] and thread_ids[0] != threading.get_ident()
        assert store._writer_lock.locked(), "live transaction must retain its writer owner"
        with sqlite3.connect(store.path, timeout=0) as reader:
            assert reader.execute("SELECT state FROM skills").fetchone()[0] == "disabled"
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                reader.execute("BEGIN IMMEDIATE")
        if action == "caller":
            enable.cancel()
            await asyncio.sleep(0.01)
            enable.cancel()
        else:
            stopper = asyncio.create_task(
                owner.revoke(package_hash)
                if action == "revoke"
                else (owner.suspend() if action == "suspend" else owner.close())
            )
        await asyncio.sleep(0.01)
        assert not enable.done(), "cancellation must wait for the real COMMIT owner"
        assert store._writer_lock.locked()
        assert owner.snapshot()["enabled"] is False
        if stopper is not None:
            assert not stopper.done()
        release.set()
        with pytest.raises(
            asyncio.CancelledError
            if action == "caller"
            else activation_module().SkillActivationError
        ):
            await asyncio.wait_for(enable, 2)
        if stopper is not None:
            await asyncio.wait_for(stopper, 2)
        assert "enabled" in observed_states and observed_states[-1] == "disabled"
        assert not await registry.is_enabled("siro.text.checklist", "1.0.0")
        assert owner.snapshot()["enabled"] is False
        assert not owner._operations
    finally:
        release.set()
        await asyncio.gather(enable, *([stopper] if stopper else []), return_exceptions=True)
        await owner.close()


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize("primary_failure", [False, True])
async def test_owned_worker_cleanup_join_preserves_primary_error_or_late_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primary_failure: bool
) -> None:
    owner, _store, _registry, _catalog, package_hash = await installed(tmp_path)
    await owner.enable(package_hash)
    original = skill_worker._remove_request
    entered, release = threading.Event(), threading.Event()
    workspaces: list[Path] = []
    thread_ids: list[int] = []

    def blocked(workspace: Path) -> None:
        workspaces.append(workspace)
        thread_ids.append(threading.get_ident())
        entered.set()
        assert release.wait(3), "synthetic cleanup release missing"
        original(workspace)

    async def failure(*args: object, **kwargs: object) -> object:
        raise ExecutionCleanupError("synthetic activation worker primary cleanup failure")

    monkeypatch.setattr(skill_worker, "_remove_request", blocked)
    if primary_failure:
        monkeypatch.setattr(skill_worker, "execute_bounded_argv", failure)
    task = asyncio.create_task(
        owner.execute(
            {"text": "- [ ] synthetic"},
            ExecutionContext("cleanup", "synthetic", "e", authorized=True),
        )
    )
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.002)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        assert not task.done(), "cleanup must remain owned after repeated caller cancellation"
        release.set()
        with pytest.raises(ExecutionCleanupError if primary_failure else asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert thread_ids[0] != threading.get_ident()
        assert workspaces and all(not path.exists() for path in workspaces)
        assert not owner._jobs
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await owner.close()
