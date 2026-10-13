from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import signal
import threading
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from siro.adapters import skill_worker
from siro.adapters.isolated_python import runtime_mounts
from siro.adapters.process_execution import execute_bounded_argv
from siro.adapters.skill_worker import SkillExecutionError, WorkerSupervisor
from siro.core.skills import InstalledSkill, load_skill
from siro.services.tools import skill_candidates
from siro.services.tools.execution import ExecutionCleanupError
from siro.services.tools.orchestrator import ToolCatalog

STRICT = "python-stdlib-single"
REAL = pytest.mark.skipif(
    platform.system() != "Linux"
    or platform.machine() != "x86_64"
    or not Path("/usr/bin/python3.14").exists()
    or not Path("/usr/lib/x86_64-linux-gnu/libseccomp.so.2").exists()
    or not shutil.which("bwrap"),
    reason="D46 actual profile requires Linux x86_64/system CPython3.14/seccomp/bwrap",
)


def package(root: Path, source: str | None = None, **overrides: object) -> InstalledSkill:
    path = root / f"package-{len(list(root.iterdir()))}"
    path.mkdir()
    files = skill_candidates._package_files()
    manifest = json.loads(files["manifest.json"])
    manifest.update(overrides)
    files["manifest.json"] = json.dumps(manifest)
    if source is not None:
        files["plugin.py"] = source
        schema = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        }
        files["input.json"] = files["output.json"] = json.dumps(schema)
    for name, content in files.items():
        (path / name).write_text(content, encoding="utf-8")
    return load_skill(path)


def alive(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1][0] != "Z"
    except (FileNotFoundError, ProcessLookupError):
        return False


def descendants(pid: int) -> set[int]:
    try:
        direct = {
            int(value) for value in Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
        }
    except (FileNotFoundError, ProcessLookupError):
        return set()
    return direct | {child for parent in direct for child in descendants(parent)}


class Owned:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.processes: list[asyncio.subprocess.Process] = []
        self.pids: set[int] = set()
        self.running = asyncio.Event()
        self.release: asyncio.Event | None = None
        self.publish_delay = 0.0
        self.target_probe = False
        original = asyncio.create_subprocess_exec

        async def spawn(*argv: str, **kwargs: Any) -> asyncio.subprocess.Process:
            process = await original(*argv, **kwargs)
            self.processes.append(process)
            self.pids.add(process.pid)
            if ("--probe" in argv) == self.target_probe:
                self.running.set()
                if self.publish_delay:
                    await asyncio.sleep(self.publish_delay)
                if self.release is not None:
                    await self.release.wait()
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    async def observe(self) -> None:
        await asyncio.wait_for(self.running.wait(), 3)
        for _ in range(10):
            for process in self.processes:
                self.pids |= descendants(process.pid)
            await asyncio.sleep(0.005)

    async def stop(self, task: asyncio.Task[Any]) -> None:
        if self.release is not None:
            self.release.set()
        if not task.done():
            task.cancel()
            with suppress(BaseException):
                await asyncio.wait_for(asyncio.shield(task), 1)
        for process in self.processes:
            self.pids |= descendants(process.pid)
        for pid in self.pids:
            with suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        for process in self.processes:

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
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_profiles_are_explicit_and_unknown_never_falls_back() -> None:
    assert WorkerSupervisor(profile=STRICT) is not None
    assert WorkerSupervisor() is not None
    with pytest.raises(ValueError):
        WorkerSupervisor(profile="automatic-untrusted")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "override",
    [
        {"entrypoint": "python:plugin:other"},
        {"permissions": [{"capability": "computer.read", "scope_required": "host"}]},
        {"risk": "normal"},
        {"idempotency": "idempotent"},
        {"concurrency": 2},
        {"cancellation": "cooperative"},
        {"compensation": "declared"},
        {"timeout_ms": 10001},
        {"resource_limits": {"memory_mb": 257, "output_bytes": 1024, "cpu_seconds": 1}},
        {"resource_limits": {"memory_mb": 64, "output_bytes": 131073, "cpu_seconds": 1}},
        {"resource_limits": {"memory_mb": 64, "output_bytes": 1024, "cpu_seconds": 6}},
    ],
)
async def test_unsupported_manifest_has_no_process_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, override: dict[str, object]
) -> None:
    skill = package(tmp_path, "def run(arguments): return arguments\n", **override)

    async def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("unsupported profile must not dispatch")

    monkeypatch.setattr(skill_worker, "execute_bounded_argv", forbidden)
    with pytest.raises(SkillExecutionError, match="unsupported strict skill profile"):
        await WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize("kind", ["extra_file", "changed_bytes", "forged_schema", "source_alias"])
async def test_captured_package_shape_and_identity_reject_before_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    skill = package(tmp_path, "def run(arguments): return arguments\n")
    error = "skill package verification failed"
    if kind == "extra_file":
        (skill.root / "extra.py").write_text("raise AssertionError('must not import')\n")
        skill = load_skill(skill.root)
        error = "unsupported strict skill profile"
    elif kind == "changed_bytes":
        (skill.root / "plugin.py").write_text("raise AssertionError('must not import')\n")
    elif kind == "forged_schema":
        skill = replace(skill, output_schema={"type": "object"})
    else:
        outside = tmp_path / "synthetic-outside.py"
        outside.write_text("raise AssertionError('must not import')\n")
        (skill.root / "plugin.py").unlink()
        (skill.root / "plugin.py").symlink_to(outside)

    async def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("package rejection must not dispatch")

    monkeypatch.setattr(skill_worker, "execute_bounded_argv", forbidden)
    with pytest.raises(SkillExecutionError, match=error):
        await WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})


@pytest.mark.asyncio
@REAL
async def test_actual_d44_preparation_to_fixed_parser_developer_execution(tmp_path: Path) -> None:
    preparer = skill_candidates.SkillCandidatePreparer(ToolCatalog(()))
    try:
        review = await preparer.prepare(skill_candidates.CAPABILITY)
    finally:
        await preparer.close()
    assert review["status"] == "awaiting_review"
    assert review["installed"] is False and review["enabled"] is False
    assert review["authorizes_execution"] is False
    files = review["files"]
    assert isinstance(files, dict)
    root = tmp_path / "review-package"
    root.mkdir()
    for name, content in files.items():
        assert isinstance(name, str) and isinstance(content, str)
        (root / name).write_text(content, encoding="utf-8")
    skill = load_skill(root)
    assert skill.manifest_hash == review["package_hash"]
    result = await WorkerSupervisor(profile=STRICT).execute(
        skill,
        {"text": "- [ ] 買牛奶\n* [x] 完成\n```\n- [ ] hidden\n```\n+ [X] \ufffd"},
    )
    assert result == {
        "pending": ["買牛奶"],
        "completed": ["完成", "\ufffd"],
        "pending_count": 1,
        "completed_count": 2,
    }
    assert load_skill(root) == skill


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize("text", ["a" * 16384, "\n".join("- [ ] a" for _ in range(128))])
async def test_actual_fixed_parser_supported_input_limits(tmp_path: Path, text: str) -> None:
    skill = package(tmp_path)
    result = await WorkerSupervisor(profile=STRICT).execute(skill, {"text": text})
    assert result["pending_count"] == (128 if "[ ]" in text else 0)
    assert result["completed_count"] == 0


@pytest.mark.asyncio
@REAL
async def test_actual_import_restrictions_precede_candidate_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = tmp_path / "synthetic-host-canary"
    canary.write_text("SYNTHETIC-RI004-NOT-MOUNTED")
    monkeypatch.setenv("RI004_WORKER_SYNTHETIC_SECRET", "SYNTHETIC-RI004-NOT-INHERITED")
    forbidden = [
        str(canary),
        "/etc/passwd",
        str(Path.home() / "synthetic-ri004-file"),
        f"/proc/{os.getpid()}/root{canary}",
        str(Path(skill_worker.__file__)),
    ]
    source = f"""import ctypes, errno, os, resource, socket
assert 'RI004_WORKER_SYNTHETIC_SECRET' not in os.environ
for path in {forbidden!r}:
    try: open(path).read()
    except OSError: pass
    else: raise AssertionError('host read escaped')
for path in [{str(tmp_path / "synthetic-host-write")!r}, '/candidate/plugin.py',
             '/trusted/request.json', '/top-level-write']:
    try: open(path,'w').write('synthetic')
    except OSError: pass
    else: raise AssertionError('readonly projection escaped')
for action in [os.fork, os.setsid, lambda: os.setpgid(0,0),
               lambda: os.execv('/usr/bin/python3.14',['python']),
               lambda: socket.socket(), lambda: socket.socketpair(),
               lambda: resource.setrlimit(resource.RLIMIT_AS,(-1,-1)),
               lambda: resource.setrlimit(resource.RLIMIT_CPU,(5,5))]:
    try: action()
    except (OSError, ValueError): pass
    else: raise AssertionError('restricted syscall escaped')
libc=ctypes.CDLL('/usr/lib/x86_64-linux-gnu/libc.so.6',use_errno=True)
assert libc.prctl(39,0,0,0,0)==1
assert libc.syscall(435,0,0)==-1 and ctypes.get_errno()==errno.EPERM
limits=open('/proc/self/limits').read()
for name,expected in [('Max address space',67108864),('Max cpu time',1),
                      ('Max file size',1048576),('Max open files',64),('Max core file size',0)]:
    row=next(line for line in limits.splitlines() if line.startswith(name))
    soft,hard,*_=row[len(name):].split()
    assert int(soft)==int(hard)==expected
try: fd=os.open('/dev/tty',os.O_RDONLY|os.O_NONBLOCK)
except OSError: pass
else:
    os.close(fd)
    raise AssertionError('host terminal accessible')
def run(arguments): return {{'text':'all boundaries denied before import'}}
"""
    skill = package(
        tmp_path,
        source,
        resource_limits={"memory_mb": 64, "output_bytes": 131072, "cpu_seconds": 1},
    )
    assert await WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"}) == {
        "text": "all boundaries denied before import"
    }
    assert canary.read_text() == "SYNTHETIC-RI004-NOT-MOUNTED"
    assert not (tmp_path / "synthetic-host-write").exists()
    assert load_skill(skill.root) == skill


@pytest.mark.asyncio
@REAL
async def test_actual_kernel_object_creation_is_denied_before_import(tmp_path: Path) -> None:
    source = """import ctypes,errno,os
libc=ctypes.CDLL('/usr/lib/x86_64-linux-gnu/libc.so.6',use_errno=True)
violations=[]
fd=libc.memfd_create(b'siro-synthetic',0)
if fd>=0:
    os.close(fd)
    violations.append('memfd')
else: assert ctypes.get_errno()==errno.EPERM
segment=libc.shmget(0,4096,0o1600)
if segment>=0:
    libc.shmctl(segment,0,None)
    violations.append('shmget')
else: assert ctypes.get_errno()==errno.EPERM
semaphore=libc.semget(0,1,0o1600)
if semaphore>=0:
    assert libc.semctl(semaphore,0,0)==0
    violations.append('semget')
else: assert ctypes.get_errno()==errno.EPERM
queue=libc.msgget(0,0o1600)
if queue>=0:
    assert libc.msgctl(queue,0,None)==0
    violations.append('msgget')
else: assert ctypes.get_errno()==errno.EPERM
name=b'/siro-synthetic-worker-private'
descriptor=libc.mq_open(name,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600,None)
if descriptor>=0:
    assert libc.mq_close(descriptor)==0
    assert libc.mq_unlink(name)==0
    violations.append('mq_open')
else: assert ctypes.get_errno()==errno.EPERM
assert libc.syscall(250,999999,0,0,0,0)==-1 and ctypes.get_errno()==errno.EPERM
assert not violations, violations
def run(arguments): return {'text':'all kernel creation denied'}
"""
    skill = package(tmp_path, source)
    assert await WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"}) == {
        "text": "all kernel creation denied"
    }


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize(
    "attack",
    [
        "bytearray(128*1024*1024)",
        "while True: pass",
        "open('/tmp/big','wb').write(b'x'*(2*1024*1024))",
        "for i in range(20):\n"
        "    with open('/tmp/f'+str(i),'wb') as stream:\n"
        "        stream.write(b'x'*(1024*1024))",
    ],
)
async def test_actual_memory_cpu_file_and_scratch_caps(tmp_path: Path, attack: str) -> None:
    skill = package(
        tmp_path,
        attack + "\ndef run(arguments): return arguments\n",
        timeout_ms=10000,
        resource_limits={"memory_mb": 64, "output_bytes": 131072, "cpu_seconds": 1},
    )
    with pytest.raises(SkillExecutionError, match="skill worker failed"):
        await asyncio.wait_for(
            WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"}), 4
        )
    assert load_skill(skill.root) == skill


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize("descriptor", [1, 2])
async def test_actual_output_flood_has_shared_bound_and_no_deadlock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, descriptor: int
) -> None:
    owned = Owned(monkeypatch)
    skill = package(
        tmp_path,
        "import os\n" + f"for _ in range(256): os.write({descriptor},b'x'*65536)\n"
        "def run(arguments): return arguments\n",
        resource_limits={"memory_mb": 64, "output_bytes": 1024, "cpu_seconds": 1},
    )
    task = asyncio.create_task(
        WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    )
    try:
        with pytest.raises(SkillExecutionError, match=r"output exceeded|timed out"):
            await asyncio.wait_for(asyncio.shield(task), 2)
        assert owned.processes and all(p.returncode is not None for p in owned.processes)
        assert not any(alive(pid) for pid in owned.pids)
    finally:
        await owned.stop(task)


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize("malformed", [False, True])
async def test_actual_strict_json_utf8_distinguishes_valid_replacement_text(
    tmp_path: Path, malformed: bool
) -> None:
    source = (
        'import os\ndef run(arguments):\n    os.write(1,b\'{"text":"\\xff"}\')\n    os._exit(0)\n'
        if malformed
        else "def run(arguments): return {'text':'\ufffd'}\n"
    )
    skill = package(tmp_path, source)
    if malformed:
        with pytest.raises(SkillExecutionError, match="invalid JSON"):
            await WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    else:
        assert await WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"}) == {
            "text": "\ufffd"
        }


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize("kind", ["platform", "runtime", "missing_seccomp_mount"])
async def test_unavailable_sandbox_never_imports_candidate_or_uses_trusted_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    skill = package(
        tmp_path,
        "print('CANDIDATE-MUST-NOT-IMPORT',flush=True)\ndef run(arguments): return arguments\n",
    )
    observations: list[dict[str, object]] = []
    original = execute_bounded_argv

    async def spy(*args: Any, **kwargs: Any) -> dict[str, object]:
        result = await original(*args, **kwargs)
        observations.append(result)
        return result

    monkeypatch.setattr(skill_worker, "execute_bounded_argv", spy)
    if kind == "platform":
        monkeypatch.setattr(platform, "machine", lambda: "unsupported")
    elif kind == "runtime":
        monkeypatch.setattr(skill_worker, "runtime_mounts", lambda: None)
    else:
        mounts = runtime_mounts()
        assert mounts is not None
        monkeypatch.setattr(
            skill_worker,
            "runtime_mounts",
            lambda: tuple(pair for pair in mounts if "libseccomp" not in pair[1]),
        )
    with pytest.raises(SkillExecutionError, match="strict skill sandbox unavailable"):
        await WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    assert not any("CANDIDATE-MUST-NOT-IMPORT" in str(row["stdout"]) for row in observations)
    assert len(observations) == (1 if kind == "missing_seccomp_mount" else 0)


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize(
    "bad", ["nonzero", "truncated", "extra_marker", "forged_json", "invalid_utf8"]
)
async def test_probe_must_match_fixed_marker_before_candidate_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    calls: list[tuple[str, ...]] = []

    async def fake(command: tuple[str, ...], **kwargs: object) -> dict[str, object]:
        calls.append(command)
        assert command[-1] == "--probe", "failed probe must never dispatch candidate"
        if bad == "invalid_utf8":
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "synthetic invalid probe")
        return {
            "returncode": 1 if bad == "nonzero" else 0,
            "truncated": bad == "truncated",
            "stdout": "SIRO_SKILL_PROFILE_READY_V1\n" + ("extra" if bad == "extra_marker" else "")
            if bad != "forged_json"
            else '{"passed":true}',
            "stderr": "",
        }

    monkeypatch.setattr(skill_worker, "execute_bounded_argv", fake)
    skill = package(tmp_path, "raise AssertionError('must not import')\n")
    with pytest.raises(SkillExecutionError, match="strict skill sandbox unavailable"):
        await WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    assert len(calls) == 1


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize("field", ["input", "output", "manifest"])
async def test_type_sensitive_identity_rejects_boolean_numeric_metadata_forgery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    skill = package(tmp_path, "def run(arguments): return arguments\n")
    arguments: dict[str, object] = {"text": "synthetic"}
    if field == "input":
        forged = replace(skill, input_schema={**skill.input_schema, "additionalProperties": 0})
        arguments["extra"] = "must not pass forged schema"
    elif field == "output":
        forged = replace(skill, output_schema={**skill.output_schema, "additionalProperties": 0})
    else:
        forged = replace(skill, manifest=skill.manifest.model_copy(update={"concurrency": True}))
    assert skill == forged, "control demonstrates why Python equality cannot bind typed identity"

    async def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("forged typed identity must never dispatch")

    monkeypatch.setattr(skill_worker, "execute_bounded_argv", forbidden)
    with pytest.raises(SkillExecutionError, match="skill package verification failed"):
        await WorkerSupervisor(profile=STRICT).execute(forged, arguments)


@pytest.mark.asyncio
async def test_strict_admission_rejects_forged_zero_concurrency_before_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill = package(tmp_path, "def run(arguments): return arguments\n")
    forged = replace(skill, manifest=skill.manifest.model_copy(update={"concurrency": 0}))

    async def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("unsupported admission must never dispatch")

    monkeypatch.setattr(skill_worker, "execute_bounded_argv", forbidden)
    with pytest.raises(SkillExecutionError, match="unsupported strict skill profile"):
        await asyncio.wait_for(
            WorkerSupervisor(profile=STRICT).execute(forged, {"text": "synthetic"}), 0.2
        )


@pytest.mark.asyncio
@REAL
async def test_absolute_collect_deadline_fences_success_after_delayed_spawn_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = Owned(monkeypatch)
    owned.publish_delay = 0.35
    skill = package(tmp_path, "def run(arguments): return arguments\n", timeout_ms=200)
    task = asyncio.create_task(
        WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    )
    try:
        with pytest.raises(SkillExecutionError, match="timed out"):
            await asyncio.wait_for(asyncio.shield(task), 2)
        assert len(owned.processes) == 2, "probe and execution must reach actual OS"
        assert all(p.returncode is not None for p in owned.processes)
        assert not any(alive(pid) for pid in owned.pids)
    finally:
        await owned.stop(task)


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize("during_spawn", [False, True])
async def test_actual_repeated_cancel_reaps_probe_and_execution_before_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, during_spawn: bool
) -> None:
    owned = Owned(monkeypatch)
    if during_spawn:
        owned.release = asyncio.Event()
    workspaces: list[Path] = []
    original = skill_worker._prepare_request

    def prepare(arguments: dict[str, object]) -> Path:
        workspace = original(arguments)
        workspaces.append(workspace)
        return workspace

    monkeypatch.setattr(skill_worker, "_prepare_request", prepare)
    skill = package(
        tmp_path,
        "import time\ntime.sleep(30)\ndef run(arguments): return arguments\n",
        timeout_ms=5000,
    )
    task = asyncio.create_task(
        WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    )
    try:
        await owned.observe()
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        if owned.release is not None:
            owned.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 2)
        assert len(owned.processes) == 2, "actual probe and execution must both run"
        assert all(p.returncode is not None for p in owned.processes)
        assert not any(alive(pid) for pid in owned.pids)
        assert workspaces and all(not path.exists() for path in workspaces)
        assert load_skill(skill.root) == skill
    finally:
        await owned.stop(task)


@pytest.mark.asyncio
@REAL
async def test_actual_fractional_timeout_reaps_worker_and_readonly_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = Owned(monkeypatch)
    workspaces: list[Path] = []
    original = skill_worker._prepare_request

    def prepare(arguments: dict[str, object]) -> Path:
        workspace = original(arguments)
        workspaces.append(workspace)
        return workspace

    monkeypatch.setattr(skill_worker, "_prepare_request", prepare)
    skill = package(
        tmp_path,
        "import time\ntime.sleep(30)\ndef run(arguments): return arguments\n",
        timeout_ms=100,
    )
    task = asyncio.create_task(
        WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    )
    try:
        with pytest.raises(SkillExecutionError, match="timed out"):
            await asyncio.wait_for(asyncio.shield(task), 1.5)
        assert owned.processes and all(p.returncode is not None for p in owned.processes)
        assert not any(alive(pid) for pid in owned.pids)
        assert workspaces and all(not path.exists() for path in workspaces)
    finally:
        await owned.stop(task)


@pytest.mark.asyncio
@REAL
async def test_strict_preparation_cancel_joins_offloop_capture_before_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = skill_worker._prepare_strict
    entered, release = threading.Event(), threading.Event()
    workspaces: list[Path] = []
    threads: list[int] = []

    def blocked(workspace: Path, skill: InstalledSkill) -> InstalledSkill:
        result = original(workspace, skill)
        workspaces.append(workspace)
        threads.append(threading.get_ident())
        entered.set()
        assert release.wait(3)
        return result

    async def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("cancelled preparation must not probe or execute")

    monkeypatch.setattr(skill_worker, "_prepare_strict", blocked)
    monkeypatch.setattr(skill_worker, "execute_bounded_argv", forbidden)
    skill = package(tmp_path, "def run(arguments): return arguments\n")
    task = asyncio.create_task(
        WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    )
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.005)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        assert not task.done(), "capture thread must remain owned until joined"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert threads and threads[0] != threading.get_ident()
        assert workspaces and all(not workspace.exists() for workspace in workspaces)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@REAL
@pytest.mark.parametrize("primary_failure", [False, True])
async def test_strict_cleanup_late_cancel_joins_and_preserves_primary_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primary_failure: bool
) -> None:
    original = skill_worker._remove_request
    entered, release = threading.Event(), threading.Event()
    workspaces: list[Path] = []
    threads: list[int] = []

    def blocked(workspace: Path) -> None:
        threads.append(threading.get_ident())
        workspaces.append(workspace)
        entered.set()
        assert release.wait(3)
        original(workspace)

    async def failure(*args: object, **kwargs: object) -> object:
        raise ExecutionCleanupError("synthetic strict process cleanup failure")

    monkeypatch.setattr(skill_worker, "_remove_request", blocked)
    if primary_failure:
        monkeypatch.setattr(skill_worker, "execute_bounded_argv", failure)
    skill = package(tmp_path, "def run(arguments): return arguments\n")
    task = asyncio.create_task(
        WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    )
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.005)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        assert not task.done(), "cleanup thread must remain owned"
        release.set()
        with pytest.raises(ExecutionCleanupError if primary_failure else asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert threads[0] != threading.get_ident()
        assert workspaces and all(not path.exists() for path in workspaces)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@REAL
async def test_strict_workspace_cleanup_failure_is_typed_not_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = skill_worker._remove_request
    workspaces: list[Path] = []

    def fail(workspace: Path) -> None:
        workspaces.append(workspace)
        raise ExecutionCleanupError("synthetic strict workspace removal failure")

    monkeypatch.setattr(skill_worker, "_remove_request", fail)
    skill = package(tmp_path, "def run(arguments): return arguments\n")
    try:
        with pytest.raises(
            ExecutionCleanupError, match="synthetic strict workspace removal failure"
        ):
            await WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    finally:
        for workspace in workspaces:
            original(workspace)


@pytest.mark.asyncio
@REAL
async def test_strict_projection_executes_frozen_capture_bytes_not_changed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = skill_worker._prepare_strict
    skill = package(tmp_path, "def run(arguments): return {'text':'captured source'}\n")

    def prepare(workspace: Path, supplied: InstalledSkill) -> InstalledSkill:
        captured = original(workspace, supplied)
        (supplied.root / "plugin.py").write_text(
            "def run(arguments): return {'text':'changed source'}\n"
        )
        return captured

    monkeypatch.setattr(skill_worker, "_prepare_strict", prepare)
    assert await WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"}) == {
        "text": "captured source"
    }
    assert load_skill(skill.root).manifest_hash != skill.manifest_hash


@pytest.mark.asyncio
@REAL
async def test_actual_probe_spawn_cancel_reaps_without_candidate_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = Owned(monkeypatch)
    owned.target_probe = True
    owned.release = asyncio.Event()
    skill = package(
        tmp_path, "raise AssertionError('candidate must not import')\n", timeout_ms=5000
    )
    task = asyncio.create_task(
        WorkerSupervisor(profile=STRICT).execute(skill, {"text": "synthetic"})
    )
    try:
        await owned.observe()
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        owned.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 2)
        assert len(owned.processes) == 1, "cancelled actual probe must not launch candidate"
        assert all(p.returncode is not None for p in owned.processes)
        assert not any(alive(pid) for pid in owned.pids)
    finally:
        await owned.stop(task)
