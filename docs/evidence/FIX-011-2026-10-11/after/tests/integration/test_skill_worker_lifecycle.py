from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from siro.adapters import skill_worker
from siro.adapters.skill_worker import SkillExecutionError, WorkerSupervisor
from siro.core.skills import InstalledSkill, load_skill
from siro.services.tools.execution import ExecutionCleanupError

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not shutil.which("bwrap"),
    reason="D45 trusted worker requires actual Linux bubblewrap",
)


def make_skill(root: Path, source: str, **overrides: object) -> InstalledSkill:
    package = root / f"skill-{len(list(root.iterdir()))}"
    package.mkdir()
    manifest: dict[str, object] = {
        "id": "test.lifecycle",
        "version": "1.0.0",
        "contract_version": 1,
        "description": "Synthetic trusted worker lifecycle fixture",
        "entrypoint": "python:plugin:run",
        "input_schema": "input.json",
        "output_schema": "output.json",
        "permissions": [],
        "risk": "observe",
        "timeout_ms": 1000,
        "concurrency": 1,
        "resource_limits": {"memory_mb": 64, "output_bytes": 1024, "cpu_seconds": 1},
        "network": "denied",
        "idempotency": "read_only",
        "cancellation": "process",
        "compensation": "none",
    }
    manifest.update(overrides)
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }
    (package / "manifest.json").write_text(json.dumps(manifest))
    for name in ("input.json", "output.json"):
        (package / name).write_text(json.dumps(schema))
    (package / "plugin.py").write_text(source)
    return load_skill(package)


def running(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1][0] != "Z"
    except (FileNotFoundError, ProcessLookupError):
        return False


def children(pid: int) -> set[int]:
    """Inspect only known fixture descendants; never scan host processes by name."""
    try:
        immediate = {
            int(value) for value in Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
        }
    except (FileNotFoundError, ProcessLookupError):
        return set()
    return immediate | {child for parent in immediate for child in children(parent)}


class OwnedProcesses:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.processes: list[asyncio.subprocess.Process] = []
        self.pids: set[int] = set()
        self.entered = asyncio.Event()
        self.release: asyncio.Event | None = None
        original = asyncio.create_subprocess_exec

        async def spawn(*argv: str, **kwargs: Any) -> asyncio.subprocess.Process:
            process = await original(*argv, **kwargs)
            self.processes.append(process)
            self.pids.add(process.pid)
            self.entered.set()
            if self.release is not None:
                await self.release.wait()
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    async def observe(self) -> None:
        await asyncio.wait_for(self.entered.wait(), 3)
        for _ in range(20):
            for process in self.processes:
                self.pids |= children(process.pid)
            await asyncio.sleep(0.005)

    async def stop(self) -> None:
        for process in self.processes:
            self.pids |= children(process.pid)
        for pid in self.pids:
            with suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        for process in self.processes:
            if process.stdin is not None:
                process.stdin.close()

            async def drain(stream: asyncio.StreamReader | None) -> None:
                if stream is not None:
                    while await stream.read(16384):
                        pass

            async with asyncio.timeout(3):
                await asyncio.gather(
                    drain(process.stdout),
                    drain(process.stderr),
                    process.wait(),
                    return_exceptions=True,
                )


async def finish(task: asyncio.Task[Any], owned: OwnedProcesses) -> None:
    if owned.release is not None:
        owned.release.set()
    if not task.done():
        task.cancel()
        with suppress(BaseException):
            await asyncio.wait_for(asyncio.shield(task), 1)
    await owned.stop()
    if not task.done():
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("descriptor", [1, 2])
async def test_real_worker_output_flood_rejects_without_timeout_deadlock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, descriptor: int
) -> None:
    owned = OwnedProcesses(monkeypatch)
    skill = make_skill(
        tmp_path,
        "import os\ndef run(arguments):\n"
        f"    for _ in range(256): os.write({descriptor}, b'x'*65536)\n"
        "    return arguments\n",
        timeout_ms=500,
    )
    task = asyncio.create_task(WorkerSupervisor().execute(skill, {"text": "synthetic"}))
    try:
        await owned.observe()
        with pytest.raises(SkillExecutionError, match=r"output exceeded|timed out"):
            await asyncio.wait_for(asyncio.shield(task), 2)
        assert all(process.returncode is not None for process in owned.processes)
        assert not any(running(pid) for pid in owned.pids)
    finally:
        await finish(task, owned)


@pytest.mark.asyncio
async def test_real_worker_complete_valid_large_json_under_manifest_limit(tmp_path: Path) -> None:
    skill = make_skill(
        tmp_path,
        "def run(arguments): return {'text': 'x'*100000}\n",
        resource_limits={"memory_mb": 64, "output_bytes": 131072, "cpu_seconds": 1},
    )
    result = await asyncio.wait_for(WorkerSupervisor().execute(skill, {"text": "synthetic"}), 3)
    assert result == {"text": "x" * 100000}


@pytest.mark.asyncio
@pytest.mark.parametrize("repeat", [False, True])
async def test_real_worker_cancel_during_spawn_joins_and_reaps_owned_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repeat: bool
) -> None:
    owned = OwnedProcesses(monkeypatch)
    owned.release = asyncio.Event()
    skill = make_skill(
        tmp_path, "import time\ndef run(arguments): time.sleep(30); return arguments\n"
    )
    task = asyncio.create_task(WorkerSupervisor().execute(skill, {"text": "synthetic"}))
    try:
        await owned.observe()
        task.cancel()
        await asyncio.sleep(0.01)
        if repeat:
            task.cancel()
        owned.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 2)
        assert owned.processes and all(p.returncode is not None for p in owned.processes)
        assert not any(running(pid) for pid in owned.pids)
    finally:
        await finish(task, owned)


@pytest.mark.asyncio
async def test_real_worker_import_delay_obeys_fractional_manifest_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = OwnedProcesses(monkeypatch)
    skill = make_skill(
        tmp_path,
        "import time\ntime.sleep(5)\ndef run(arguments): return arguments\n",
        timeout_ms=100,
        resource_limits={"memory_mb": 64, "output_bytes": 65536, "cpu_seconds": 1},
    )
    start = time.monotonic()
    task = asyncio.create_task(WorkerSupervisor().execute(skill, {"text": "x" * 60000}))
    try:
        await owned.observe()
        with pytest.raises(SkillExecutionError, match="timed out"):
            await asyncio.wait_for(asyncio.shield(task), 1.2)
        assert time.monotonic() - start < 1.2
        assert not any(running(pid) for pid in owned.pids)
    finally:
        await finish(task, owned)


@pytest.mark.asyncio
@pytest.mark.parametrize("cause", ["timeout", "cancel"])
async def test_real_worker_namespace_stops_setsid_descendant_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cause: str
) -> None:
    owned = OwnedProcesses(monkeypatch)
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    skill = make_skill(
        tmp_path,
        "import os,signal,time\ndef run(arguments):\n"
        "    if os.fork()==0:\n"
        "        os.setsid()\n"
        "        signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
        "        while True: time.sleep(.01)\n"
        "    while True: time.sleep(.01)\n",
        timeout_ms=500 if cause == "timeout" else 5000,
    )
    task = asyncio.create_task(WorkerSupervisor().execute(skill, {"text": "synthetic"}))
    try:
        await owned.observe()
        assert len(owned.pids) >= 3, "fixture must include actual worker and fork descendant"
        if cause == "cancel":
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cause == "cancel" else SkillExecutionError):
            await asyncio.wait_for(asyncio.shield(task), 2)
        assert not any(running(pid) for pid in owned.pids)
        assert unrelated.poll() is None
    finally:
        await finish(task, owned)
        unrelated.terminate()
        unrelated.wait(timeout=3)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["large", "nonfinite"])
async def test_request_limits_and_finite_json_reject_before_process_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    skill = make_skill(tmp_path, "def run(arguments): return {'text':'synthetic'}\n")
    arguments: object = {"text": "x" * 65536}
    if kind == "nonfinite":
        schema = {
            "type": "object",
            "properties": {"value": {"type": "number"}},
            "required": ["value"],
            "additionalProperties": False,
        }
        (skill.root / "input.json").write_text(json.dumps(schema))
        skill = load_skill(skill.root)
        arguments = {"value": float("nan")}

    async def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("invalid bounded request must never spawn")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises((ValueError, SkillExecutionError)):
        await WorkerSupervisor().execute(skill, arguments)


@pytest.mark.asyncio
async def test_request_preparation_cancel_joins_offloop_then_removes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = skill_worker._prepare_request
    entered, release = threading.Event(), threading.Event()
    workspaces: list[Path] = []
    thread_ids: list[int] = []

    def blocked(arguments: dict[str, object]) -> Path:
        thread_ids.append(threading.get_ident())
        workspace = original(arguments)
        workspaces.append(workspace)
        entered.set()
        assert release.wait(3)
        return workspace

    async def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("cancelled preparation must never spawn")

    monkeypatch.setattr(skill_worker, "_prepare_request", blocked)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    skill = make_skill(tmp_path, "def run(arguments): return arguments\n")
    task = asyncio.create_task(WorkerSupervisor().execute(skill, {"text": "synthetic"}))
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.005)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        assert not task.done(), "cancel must retain owned preparation until joined"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert len(thread_ids) == 1 and thread_ids[0] != threading.get_ident()
        assert workspaces and all(not path.exists() for path in workspaces)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancel_during_request_cleanup_joins_and_prevents_late_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = skill_worker._remove_request
    entered, release = threading.Event(), threading.Event()
    workspaces: list[Path] = []
    thread_ids: list[int] = []

    def blocked(workspace: Path) -> None:
        thread_ids.append(threading.get_ident())
        workspaces.append(workspace)
        entered.set()
        assert release.wait(3)
        original(workspace)

    monkeypatch.setattr(skill_worker, "_remove_request", blocked)
    skill = make_skill(tmp_path, "def run(arguments): return arguments\n")
    task = asyncio.create_task(WorkerSupervisor().execute(skill, {"text": "synthetic"}))
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.005)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        assert not task.done(), "cancel must retain cleanup ownership"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert thread_ids[0] != threading.get_ident()
        assert workspaces and all(not path.exists() for path in workspaces)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_request_cleanup_failure_is_explicit_and_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = skill_worker._remove_request
    workspaces: list[Path] = []

    def fail(workspace: Path) -> None:
        workspaces.append(workspace)
        raise ExecutionCleanupError("synthetic request cleanup refusal")

    monkeypatch.setattr(skill_worker, "_remove_request", fail)
    skill = make_skill(tmp_path, "def run(arguments): return arguments\n")
    try:
        with pytest.raises(ExecutionCleanupError, match="synthetic request cleanup refusal"):
            await asyncio.wait_for(WorkerSupervisor().execute(skill, {"text": "synthetic"}), 2)
    finally:
        for workspace in workspaces:
            original(workspace)


@pytest.mark.asyncio
async def test_readonly_request_file_does_not_change_package_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = skill_worker._prepare_request
    workspaces: list[Path] = []

    def observe(arguments: dict[str, object]) -> Path:
        workspace = original(arguments)
        workspaces.append(workspace)
        request = workspace / "request.json"
        assert request.stat().st_mode & 0o777 == 0o400
        assert json.loads(request.read_bytes()) == arguments
        return workspace

    monkeypatch.setattr(skill_worker, "_prepare_request", observe)
    skill = make_skill(
        tmp_path,
        "import os\ndef run(arguments):\n"
        "    assert os.environ['SIRO_SKILL_REQUEST']=='/request.json'\n"
        "    try: open('/request.json','w').write('bad')\n"
        "    except OSError: pass\n"
        "    else: raise AssertionError('request mount writable')\n"
        "    return arguments\n",
    )
    assert await WorkerSupervisor().execute(skill, {"text": "synthetic"}) == {"text": "synthetic"}
    assert load_skill(skill.root) == skill
    assert workspaces and all(not workspace.exists() for workspace in workspaces)


@pytest.mark.asyncio
@pytest.mark.parametrize("oversized", [False, True])
async def test_legacy_direct_worker_stdin_remains_bounded(tmp_path: Path, oversized: bool) -> None:
    skill = make_skill(tmp_path, "def run(arguments): return {'text':'synthetic'}\n")
    request = json.dumps({"text": "x" * 65536 if oversized else "synthetic"}).encode()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "siro.skill_worker",
        env={
            "PATH": os.defpath,
            "LANG": "C.UTF-8",
            "SIRO_SKILL_ROOT": str(skill.root),
            "SIRO_SKILL_ENTRYPOINT": skill.manifest.entrypoint,
            "SIRO_WORKER_MEMORY_MB": "64",
            "SIRO_WORKER_CPU_SECONDS": "1",
        },
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(3):
            output, _ = await process.communicate(request)
        if oversized:
            assert process.returncode != 0
            assert output == b"", "oversized legacy input must reject before function call"
        else:
            assert process.returncode == 0
            assert json.loads(output) == {"text": "synthetic"}
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


@pytest.mark.asyncio
async def test_process_cleanup_failure_survives_late_request_cleanup_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = skill_worker._remove_request
    entered, release = threading.Event(), threading.Event()
    workspaces: list[Path] = []

    async def process_failure(*args: object, **kwargs: object) -> object:
        raise ExecutionCleanupError("synthetic owned process cleanup refusal")

    def blocked(workspace: Path) -> None:
        workspaces.append(workspace)
        entered.set()
        assert release.wait(3)
        original(workspace)

    monkeypatch.setattr(skill_worker, "execute_bounded_argv", process_failure)
    monkeypatch.setattr(skill_worker, "_remove_request", blocked)
    skill = make_skill(tmp_path, "def run(arguments): return arguments\n")
    task = asyncio.create_task(WorkerSupervisor().execute(skill, {"text": "synthetic"}))
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.005)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        release.set()
        with pytest.raises(ExecutionCleanupError, match="synthetic owned process cleanup refusal"):
            await asyncio.wait_for(task, 2)
        assert workspaces and all(not workspace.exists() for workspace in workspaces)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


def test_request_removal_os_error_is_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(path: Path) -> None:
        raise OSError("synthetic request removal denied")

    monkeypatch.setattr(shutil, "rmtree", denied)
    with pytest.raises(ExecutionCleanupError):
        skill_worker._remove_request(tmp_path)


def test_service_and_adapter_execution_types_are_identical() -> None:
    from siro.adapters import process_execution
    from siro.services.tools import execution

    assert execution.ExecutionContext is process_execution.ExecutionContext
    assert execution.ExecutionCancelled is process_execution.ExecutionCancelled
    assert execution.ExecutionCleanupError is process_execution.ExecutionCleanupError


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed", [False, True])
async def test_real_worker_strict_utf8_preserves_legitimate_replacement_character(
    tmp_path: Path, malformed: bool
) -> None:
    source = (
        'import os\ndef run(arguments):\n    os.write(1,b\'{"text":"\\xff"}\')\n    os._exit(0)\n'
        if malformed
        else "def run(arguments): return {'text':'\ufffd'}\n"
    )
    skill = make_skill(tmp_path, source)
    if malformed:
        with pytest.raises(SkillExecutionError, match="invalid JSON"):
            await asyncio.wait_for(WorkerSupervisor().execute(skill, {"text": "synthetic"}), 2)
    else:
        assert await WorkerSupervisor().execute(skill, {"text": "synthetic"}) == {"text": "\ufffd"}


@pytest.mark.asyncio
async def test_neutral_process_owner_rejects_invalid_utf8_after_reaping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from siro.adapters import process_execution

    owned = OwnedProcesses(monkeypatch)
    try:
        with pytest.raises(UnicodeDecodeError):
            await process_execution.execute_bounded_argv(
                (sys.executable, "-c", "import os; os.write(1,b'\\xff')"),
                cwd=tmp_path,
                environment={"PATH": os.defpath},
                timeout=1,
                stdout_errors="strict",
            )
        assert owned.processes and all(
            process.returncode is not None for process in owned.processes
        )
        assert not any(running(pid) for pid in owned.pids)
    finally:
        await owned.stop()


@pytest.mark.asyncio
async def test_existing_service_private_cleanup_delegate_is_importable_and_owned(
    tmp_path: Path,
) -> None:
    from siro.services.tools.execution import _protected_cleanup

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import time; time.sleep(30)",
        cwd=tmp_path,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        await asyncio.wait_for(_protected_cleanup(process, []), 2)
        assert process.returncode is not None and not running(process.pid)
    finally:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        await process.wait()


@pytest.mark.asyncio
async def test_dispatcher_primary_cleanup_error_survives_repeated_snapshot_cleanup_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from siro.adapters.skill_worker import SkillDispatcher
    from siro.persistence.skills import SQLiteSkillRegistry
    from siro.persistence.sqlite import SQLiteStore

    original = skill_worker._prepare_skill
    entered, release = threading.Event(), threading.Event()
    snapshots: list[Path] = []

    def prepare(skill: InstalledSkill) -> skill_worker._PreparedSkill:
        prepared = original(skill)
        snapshot = prepared.snapshot.root
        snapshots.append(snapshot)
        original_cleanup = prepared.directory.cleanup

        def blocked_cleanup() -> None:
            entered.set()
            assert release.wait(3)
            original_cleanup()

        monkeypatch.setattr(prepared.directory, "cleanup", blocked_cleanup)
        return prepared

    class FailingSupervisor(WorkerSupervisor):
        async def execute(self, skill: InstalledSkill, arguments: object) -> dict[str, object]:
            raise ExecutionCleanupError("synthetic owned worker cleanup refusal")

    monkeypatch.setattr(skill_worker, "_prepare_skill", prepare)
    skill = make_skill(tmp_path, "def run(arguments): return arguments\n")
    store = SQLiteStore(tmp_path / "synthetic-registry.db")
    await store.initialize()
    registry = SQLiteSkillRegistry(store)
    await registry.install(skill)
    assert await registry.set_enabled(skill.manifest.id, skill.manifest.version, enabled=True)
    dispatcher = SkillDispatcher(registry, FailingSupervisor())
    task = asyncio.create_task(dispatcher.execute(skill, {"text": "synthetic"}))
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.005)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        assert not task.done(), "cancel must retain frozen snapshot cleanup ownership"
        release.set()
        with pytest.raises(ExecutionCleanupError, match="synthetic owned worker cleanup refusal"):
            await asyncio.wait_for(task, 2)
        assert snapshots and all(not snapshot.exists() for snapshot in snapshots)
        assert await registry.is_enabled(skill.manifest.id, skill.manifest.version, identity=skill)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
