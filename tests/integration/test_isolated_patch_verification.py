from __future__ import annotations

import asyncio
import difflib
import importlib
import os
import platform
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import uuid4

import pytest

from siro.core.evolution import PatchProposal
from siro.services.tools.execution import (
    ExecutionCancelled,
    ExecutionCleanupError,
    ExecutionContext,
)

pytestmark = pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine() != "x86_64",
    reason="D43 explicitly supports Linux x86_64 only",
)


real_profile = pytest.mark.skipif(
    not (
        Path("/usr/bin/python3.14").is_file()
        and Path("/usr/lib/python3.14").is_dir()
        and Path("/usr/lib/x86_64-linux-gnu/libseccomp.so.2").is_file()
        and shutil.which("bwrap")
        and shutil.which("git")
    ),
    reason="real D43 profile requires system CPython3.14, libseccomp, bwrap and git",
)


def proposal(
    old: str = "VALUE = 1\n", new: str = "VALUE = 2\n", *, path: str = "src/value.py"
) -> PatchProposal:
    return PatchProposal(
        proposal_id=uuid4(),
        created_at=datetime.now(UTC),
        unified_diff="".join(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        ),
    )


def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src/value.py").write_text("VALUE = 1\n")
    (root / "tests/test_value.py").write_text(
        "import unittest\nfrom value import VALUE\n"
        "class ValueTest(unittest.TestCase):\n"
        "    def test_value(self): self.assertEqual(VALUE, 2)\n"
    )
    return root


def backend() -> ModuleType:
    return importlib.import_module("siro.services.tools.patch_verification")


@pytest.mark.parametrize(
    "path,status",
    [
        ("src/value.py", "ready"),
        ("src/siro/config.py", "rejected_policy_change"),
        ("src/siro/core/authorization.py", "rejected_policy_change"),
    ],
)
def test_shared_pure_preflight(path: str, status: str) -> None:
    core = importlib.import_module("siro.core.evolution")
    result = core.preflight_patch(proposal(path=path))
    assert result.status == status and result.workspace_removed is True
    assert result.changed_paths == (path,) and result.outputs == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("value,status", [(2, "passed"), (3, "failed_checks")])
@real_profile
async def test_actual_unittest_profile_and_unchanged_original(
    tmp_path: Path, value: int, status: str
) -> None:
    root = project(tmp_path)
    report = await backend().verify_isolated_patch(root, proposal(new=f"VALUE = {value}\n"))
    assert report.status == status, report.outputs
    assert report.workspace_removed is True
    assert (root / "src/value.py").read_text() == "VALUE = 1\n"
    assert not (root / ".git").exists()


@pytest.mark.asyncio
@real_profile
async def test_real_import_cannot_read_write_fork_exec_network_or_raise_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    secret = tmp_path / "host-secret"
    secret.write_text("SYNTHETIC-PRIVATE-CANARY")
    (root / ".env.local").write_text("SYNTHETIC-PRIVATE-CANARY")
    (root / ".siro-data").mkdir()
    (root / ".siro-data/private.db").write_text("SYNTHETIC-PRIVATE-CANARY")
    monkeypatch.setenv("RI003_SYNTHETIC_SECRET", "SYNTHETIC-PRIVATE-CANARY")
    forbidden = [
        str(secret),
        str(root / "src/value.py"),
        "/candidate/.env.local",
        "/candidate/.siro-data/private.db",
    ]
    attack = f"""import os, socket, resource
assert 'RI003_SYNTHETIC_SECRET' not in os.environ
for path in {forbidden!r}:
    try: open(path).read()
    except OSError: pass
    else: raise AssertionError('private read escaped')
for path in [{str(tmp_path / "host-write")!r}, '/candidate/src/value.py']:
    try: open(path,'w').write('escape')
    except OSError: pass
    else: raise AssertionError('write escaped')
for action in [os.fork, os.setsid, lambda: os.setpgid(0,0),
               lambda: os.execv('/usr/bin/python3.14',['python']),
               lambda: socket.socket(), lambda: resource.setrlimit(resource.RLIMIT_AS,(-1,-1))]:
    try: action()
    except (OSError, ValueError): pass
    else: raise AssertionError('restricted syscall escaped')
try:
    fd=os.open('/dev/tty',os.O_RDONLY|os.O_NONBLOCK)
except OSError: pass
else:
    os.close(fd)
    raise AssertionError('host terminal available')
VALUE = 2
"""
    report = await backend().verify_isolated_patch(root, proposal(new=attack))
    assert report.status == "passed", report.outputs
    assert "SYNTHETIC-PRIVATE-CANARY" not in "".join(report.outputs)
    assert secret.read_text() == "SYNTHETIC-PRIVATE-CANARY"
    assert not (tmp_path / "host-write").exists()
    assert (root / "src/value.py").read_text() == "VALUE = 1\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["file_symlink", "directory_symlink", "hardlink", "root_symlink"])
@real_profile
async def test_source_aliases_are_rejected_without_following(tmp_path: Path, mode: str) -> None:
    root = project(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("SYNTHETIC-PRIVATE-CANARY")
    if mode == "file_symlink":
        (root / "src/alias.py").symlink_to(outside)
    elif mode == "directory_symlink":
        (root / "src/alias").symlink_to(tmp_path)
    elif mode == "hardlink":
        os.link(outside, root / "src/alias.py")
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    result = await backend().verify_isolated_patch(root, proposal())
    assert result.status == "rejected_source" and result.workspace_removed
    assert "SYNTHETIC-PRIVATE-CANARY" not in "".join(result.outputs)


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", ["files", "file_bytes", "total_bytes"])
@real_profile
async def test_real_source_capture_bounds(tmp_path: Path, limit: str) -> None:
    root = project(tmp_path)
    if limit == "files":
        for i in range(513):
            (root / f"src/file{i}.py").write_text("# synthetic\n")
    elif limit == "file_bytes":
        (root / "src/large.py").write_bytes(b"#" * (4 * 1024 * 1024 + 1))
    else:
        for i in range(4):
            (root / f"src/large{i}.py").write_bytes(b"#" * (4 * 1024 * 1024))
    result = await backend().verify_isolated_patch(root, proposal())
    assert result.status == "rejected_source" and result.workspace_removed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", ["profile", "path", "policy", "invalid", "missing_bwrap", "platform"]
)
async def test_rejected_ingress_has_no_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    root = project(tmp_path)
    module = backend()

    async def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("rejected ingress executed a process")

    monkeypatch.setattr(module, "execute_bounded_argv", forbidden)
    candidate = proposal()
    kwargs = {}
    expected = {
        "profile": "rejected_profile",
        "path": "rejected_source",
        "policy": "rejected_policy_change",
        "invalid": "rejected_invalid_diff",
        "missing_bwrap": "unsupported_sandbox",
        "platform": "unsupported_platform",
    }[kind]
    if kind == "profile":
        kwargs["profile"] = "model-selected-command"
    elif kind == "path":
        candidate = proposal(path="private.py")
    elif kind == "policy":
        candidate = proposal(path="src/siro/core/authorization.py")
    elif kind == "invalid":
        candidate = candidate.model_copy(update={"unified_diff": "unknown format\n"})
    elif kind == "missing_bwrap":
        monkeypatch.setattr(module.shutil, "which", lambda *args, **kwargs: None)
    else:
        monkeypatch.setattr(module.platform, "system", lambda: "UnsupportedOS")
    result = await module.verify_isolated_patch(root, candidate, **kwargs)
    assert result.status == expected and result.workspace_removed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attack",
    [
        "bytearray(512*1024*1024)\n",
        "while True: pass\n",
        "open('/tmp/large','wb').write(b'x'*(2*1024*1024))\n",
        "for i in range(20): open('/tmp/f'+str(i),'wb').write(b'x'*(1024*1024))\n",
        "import os\nfor i in range(100):\n os.write(1,b'x'*16384)\n os.write(2,b'y'*16384)\n",
    ],
)
@real_profile
async def test_real_resource_and_output_limits(tmp_path: Path, attack: str) -> None:
    root = project(tmp_path)
    report = await backend().verify_isolated_patch(root, proposal(new=attack + "VALUE = 2\n"))
    assert report.status == "failed_checks", report.outputs
    assert report.workspace_removed
    assert sum(len(s.encode()) for s in report.outputs) < 70 * 1024
    assert (root / "src/value.py").read_text() == "VALUE = 1\n"


@pytest.mark.asyncio
@real_profile
async def test_no_tests_cannot_pass(tmp_path: Path) -> None:
    root = project(tmp_path)
    (root / "tests/test_value.py").unlink()
    result = await backend().verify_isolated_patch(root, proposal())
    assert result.status == "failed_checks" and result.workspace_removed


@pytest.mark.asyncio
@real_profile
async def test_kernel_object_creation_is_denied(tmp_path: Path) -> None:
    root = project(tmp_path)
    attack = """import ctypes, errno, os
libc=ctypes.CDLL('/usr/lib/x86_64-linux-gnu/libc.so.6',use_errno=True)
fd=libc.memfd_create(b'synthetic',0)
if fd>=0:
    os.close(fd)
    raise AssertionError('memfd creation allowed')
assert ctypes.get_errno()==errno.EPERM
segment=libc.shmget(0,4096,0o1600)
if segment>=0:
    libc.shmctl(segment,0,None)
    raise AssertionError('shm creation allowed')
assert ctypes.get_errno()==errno.EPERM
assert libc.syscall(250,999999,0,0,0,0)==-1 # invalid keyctl, no key accessed
assert ctypes.get_errno()==errno.EPERM
assert libc.syscall(435,0,0)==-1 # clone3, including direct syscall path
assert ctypes.get_errno()==errno.EPERM
VALUE=2
"""
    result = await backend().verify_isolated_patch(root, proposal(new=attack))
    assert result.status == "passed", result.outputs


@pytest.mark.asyncio
@real_profile
async def test_ipc_kernel_allocations_are_denied(tmp_path: Path) -> None:
    root = project(tmp_path)
    attack = """import ctypes, errno, os
libc=ctypes.CDLL('/usr/lib/x86_64-linux-gnu/libc.so.6',use_errno=True)
violations=[]
semaphore=libc.semget(0,1,0o1600)
if semaphore>=0:
    assert libc.semctl(semaphore,0,0)==0 # immediately remove private synthetic object
    violations.append('semget allowed')
else:
    assert ctypes.get_errno()==errno.EPERM
queue=libc.msgget(0,0o1600)
if queue>=0:
    assert libc.msgctl(queue,0,None)==0 # IPC_RMID, no message data allocated
    violations.append('msgget allowed')
else:
    assert ctypes.get_errno()==errno.EPERM
name=b'/siro-synthetic-private'
descriptor=libc.mq_open(name,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600,None)
if descriptor>=0:
    assert libc.mq_close(descriptor)==0
    assert libc.mq_unlink(name)==0
    violations.append('mq_open allowed')
else:
    assert ctypes.get_errno()==errno.EPERM
assert not violations, violations
VALUE=2
"""
    result = await backend().verify_isolated_patch(root, proposal(new=attack))
    assert result.status == "passed", "".join(result.outputs)


@pytest.mark.asyncio
@real_profile
async def test_patch_cannot_expand_projected_source_byte_limit(tmp_path: Path) -> None:
    root = project(tmp_path)
    old = "#\n" * (2 * 1024 * 1024)
    (root / "src/large.py").write_text(old)
    result = await backend().verify_isolated_patch(
        root, proposal(old=old, new=old + "# added\n" * 100, path="src/large.py")
    )
    assert result.status == "rejected_source" and result.workspace_removed
    assert (root / "src/large.py").stat().st_size == 4 * 1024 * 1024


@pytest.mark.asyncio
@real_profile
async def test_repeated_cancel_reaps_all_owned_processes_and_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    module = backend()
    original_spawn = asyncio.create_subprocess_exec
    processes = []
    started = asyncio.Event()

    async def spawn(*args: str, **kwargs: Any) -> asyncio.subprocess.Process:
        process = await original_spawn(*args, **kwargs)
        processes.append(process)
        if "bwrap" in Path(args[0]).name and "--probe" not in args:
            started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    original_temp = module.tempfile.mkdtemp
    workspaces = []

    def temporary(*args: Any, **kwargs: Any) -> str:
        path = str(original_temp(*args, **kwargs))
        workspaces.append(Path(path))
        return path

    monkeypatch.setattr(module.tempfile, "mkdtemp", temporary)
    task = asyncio.create_task(
        module.verify_isolated_patch(root, proposal(new="import time\ntime.sleep(30)\nVALUE = 2\n"))
    )
    await asyncio.wait_for(started.wait(), 5)
    task.cancel()
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 6)
    assert processes and all(p.returncode is not None for p in processes)
    assert workspaces and all(not p.exists() for p in workspaces)


@pytest.mark.asyncio
async def test_pre_fenced_context_never_executes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    module = backend()
    context = ExecutionContext("synthetic", "owner", "epoch")
    context.cancellation.cancel()

    async def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("cancelled verification spawned")

    monkeypatch.setattr(module, "execute_bounded_argv", forbidden)
    with pytest.raises(ExecutionCancelled):
        await module.verify_isolated_patch(root, proposal(), context=context)


@pytest.mark.asyncio
@real_profile
async def test_missing_seccomp_inside_real_namespace_never_runs_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    module = backend()
    original_mounts = module._mounts
    monkeypatch.setattr(
        module,
        "_mounts",
        lambda: tuple(pair for pair in original_mounts() if "libseccomp" not in pair[1]),
    )
    report = await module.verify_isolated_patch(
        root, proposal(new="print('CANDIDATE-MUST-NOT-RUN')\nVALUE=2\n")
    )
    assert report.status == "unsupported_sandbox" and report.workspace_removed
    assert "CANDIDATE-MUST-NOT-RUN" not in "".join(report.outputs)


@pytest.mark.asyncio
@real_profile
async def test_external_deadline_propagates_and_removes_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    module = backend()
    original_temp = module.tempfile.mkdtemp
    workspaces: list[Path] = []

    def temporary(*args: Any, **kwargs: Any) -> str:
        path = str(original_temp(*args, **kwargs))
        workspaces.append(Path(path))
        return path

    monkeypatch.setattr(module.tempfile, "mkdtemp", temporary)
    context = ExecutionContext(
        "synthetic", "owner", "epoch", deadline=asyncio.get_running_loop().time() + 0.5
    )
    with pytest.raises(TimeoutError):
        await module.verify_isolated_patch(
            root, proposal(new="import time\ntime.sleep(30)\nVALUE=2\n"), context=context
        )
    assert workspaces and all(not p.exists() for p in workspaces)


@pytest.mark.asyncio
@real_profile
async def test_cancel_during_source_preparation_joins_before_removing_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    module = backend()
    original_capture = module._capture
    original_temp = module.tempfile.mkdtemp
    started, release = threading.Event(), threading.Event()
    workspaces: list[Path] = []

    def capture(path: Path) -> dict[str, bytes]:
        started.set()
        assert release.wait(5)
        return dict(original_capture(path))

    def temporary(*args: Any, **kwargs: Any) -> str:
        path = str(original_temp(*args, **kwargs))
        workspaces.append(Path(path))
        return path

    monkeypatch.setattr(module, "_capture", capture)
    monkeypatch.setattr(module.tempfile, "mkdtemp", temporary)
    task = asyncio.create_task(module.verify_isolated_patch(root, proposal()))
    try:
        async with asyncio.timeout(3):
            while not started.is_set():
                await asyncio.sleep(0.005)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    assert workspaces and all(not p.exists() for p in workspaces)


@pytest.mark.asyncio
@real_profile
async def test_preparation_cleanup_failure_cannot_claim_removed_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    (root / "src/alias.py").symlink_to(root / "src/value.py")
    module = backend()
    original_remove = module.shutil.rmtree
    original_temp = module.tempfile.mkdtemp
    workspaces: list[Path] = []

    def temporary(*args: Any, **kwargs: Any) -> str:
        path = str(original_temp(*args, **kwargs))
        workspaces.append(Path(path))
        return path

    def failed_remove(*args: object, **kwargs: object) -> None:
        raise OSError("synthetic cleanup failure")

    monkeypatch.setattr(module.tempfile, "mkdtemp", temporary)
    monkeypatch.setattr(module.shutil, "rmtree", failed_remove)
    try:
        with pytest.raises(ExecutionCleanupError):
            await module.verify_isolated_patch(root, proposal())
    finally:
        for path in workspaces:
            if path.exists():
                original_remove(path)


@pytest.mark.asyncio
@real_profile
async def test_source_projection_never_opens_ignored_private_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    for path in (root / ".env.local", root / "src/.hidden.py", root / "tests/private.json"):
        path.write_text("SYNTHETIC-PRIVATE-CANARY")
    module = backend()
    original_open = os.open
    opened: list[str] = []

    def observed_open(path: Any, *args: Any, **kwargs: Any) -> int:
        opened.append(str(path))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", observed_open)
    report = await module.verify_isolated_patch(root, proposal())
    assert report.status == "passed", report.outputs
    assert all(
        Path(name).name not in {".env.local", ".hidden.py", "private.json"} for name in opened
    )
    assert "SYNTHETIC-PRIVATE-CANARY" not in "".join(report.outputs)


@pytest.mark.asyncio
@real_profile
@pytest.mark.parametrize("kind", ["task", "context"])
async def test_cancel_during_success_cleanup_cannot_return_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    root = project(tmp_path)
    module = backend()
    original_remove = module._remove_workspace
    started, release = threading.Event(), threading.Event()
    removed: list[Path] = []

    def remove(path: Path) -> None:
        started.set()
        assert release.wait(5)
        original_remove(path)
        removed.append(path)

    monkeypatch.setattr(module, "_remove_workspace", remove)
    context = ExecutionContext("synthetic", "owner", "epoch")
    task = asyncio.create_task(module.verify_isolated_patch(root, proposal(), context=context))
    try:
        async with asyncio.timeout(4):
            while not started.is_set():
                await asyncio.sleep(0.005)
        if kind == "task":
            task.cancel()
        else:
            context.cancellation.cancel()
    finally:
        release.set()
    expected = asyncio.CancelledError if kind == "task" else ExecutionCancelled
    with pytest.raises(expected):
        await asyncio.wait_for(task, 5)
    assert removed and all(not path.exists() for path in removed)


@pytest.mark.asyncio
@real_profile
async def test_context_cancellation_does_not_hide_process_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    module = backend()
    context = ExecutionContext("synthetic", "owner", "epoch")

    async def execute(argv: tuple[str, ...], **kwargs: Any) -> dict[str, object]:
        if "bwrap" in Path(argv[0]).name and "--probe" not in argv:
            context.cancellation.cancel()
            raise ExecutionCleanupError("synthetic owned cleanup failure")
        return {
            "returncode": 0,
            "truncated": False,
            "stdout": "SIRO_PATCH_PROFILE_READY_V1\n" if "--probe" in argv else "",
            "stderr": "",
        }

    monkeypatch.setattr(module, "execute_bounded_argv", execute)
    with pytest.raises(ExecutionCleanupError):
        await module.verify_isolated_patch(root, proposal(), context=context)
