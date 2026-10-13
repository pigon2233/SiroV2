"""Explicit-owner Linux single-process checks; never a host execution fallback."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import stat
import sys
import tempfile
from contextlib import suppress
from dataclasses import replace
from pathlib import Path

from siro.core.evolution import PatchProposal, VerificationReport, preflight_patch
from siro.services.tools.execution import (
    ExecutionCleanupError,
    ExecutionContext,
    execute_bounded_argv,
)

PROFILE = "python-unittest-single"
_LIBRARY_ROOT = Path("/usr/lib/x86_64-linux-gnu")
_LIBRARIES = (
    "libc.so.6",
    "libm.so.6",
    "libz.so.1",
    "libexpat.so.1",
    "libffi.so.8",
    "libseccomp.so.2",
)


class _SourceRejected(ValueError):
    pass


def _supported_path(value: str) -> bool:
    parts = value.split("/")
    return (
        len(parts) > 1
        and parts[0] in {"src", "tests"}
        and parts[-1].endswith(".py")
        and all(not p.startswith(".") and p != "__pycache__" for p in parts)
    )


def _capture(root: Path) -> dict[str, bytes]:
    absolute = root.absolute()
    if absolute != absolute.resolve():
        raise _SourceRejected("noncanonical source root")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    root_fd = os.open(absolute, flags)
    entries = 0
    total = 0
    captured: dict[str, bytes] = {}

    def visit(directory: int, parts: tuple[str, ...]) -> None:
        nonlocal entries, total
        if len(parts) > 32:
            raise _SourceRejected("source depth limit")
        names = []
        with os.scandir(directory) as iterator:
            for entry in iterator:
                entries += 1
                if entries > 1024:
                    raise _SourceRejected("source entry limit")
                if not entry.name.startswith(".") and entry.name != "__pycache__":
                    names.append(entry.name)
        for name in sorted(names):
            metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode) or metadata.st_dev != os.fstat(root_fd).st_dev:
                raise _SourceRejected("source alias")
            if stat.S_ISDIR(metadata.st_mode):
                child = os.open(name, flags, dir_fd=directory)
                try:
                    opened = os.fstat(child)
                    if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                        raise _SourceRejected("source directory changed")
                    visit(child, (*parts, name))
                finally:
                    os.close(child)
            elif name.endswith(".py"):
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise _SourceRejected("nonregular source")
                if metadata.st_size > 4 * 1024 * 1024 or len(captured) >= 512:
                    raise _SourceRejected("source file limit")
                descriptor = os.open(
                    name,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                    dir_fd=directory,
                )
                try:
                    before = os.fstat(descriptor)
                    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                        raise _SourceRejected("source changed")
                    data = bytearray()
                    while chunk := os.read(descriptor, 64 * 1024):
                        data.extend(chunk)
                        if len(data) > 4 * 1024 * 1024:
                            raise _SourceRejected("source file limit")
                    after = os.fstat(descriptor)

                    def identity(s: os.stat_result) -> tuple[int, ...]:
                        return (
                            s.st_dev,
                            s.st_ino,
                            s.st_size,
                            s.st_mtime_ns,
                            s.st_ctime_ns,
                            s.st_nlink,
                        )

                    if (
                        identity(metadata) != identity(before)
                        or identity(before) != identity(after)
                        or len(data) != before.st_size
                    ):
                        raise _SourceRejected("source changed during capture")
                finally:
                    os.close(descriptor)
                total += len(data)
                if total > 16 * 1024 * 1024:
                    raise _SourceRejected("source total limit")
                captured["/".join((*parts, name))] = bytes(data)

    try:
        for name in ("src", "tests"):
            try:
                child = os.open(name, flags, dir_fd=root_fd)
            except FileNotFoundError:
                continue
            try:
                if os.fstat(child).st_dev != os.fstat(root_fd).st_dev:
                    raise _SourceRejected("source mount alias")
                visit(child, (name,))
            finally:
                os.close(child)
    finally:
        os.close(root_fd)
    if not captured:
        raise _SourceRejected("empty source projection")
    return captured


def _prepare(root: Path, proposal: PatchProposal) -> Path:
    workspace = Path(tempfile.mkdtemp(prefix="siro-isolated-patch-"))
    try:
        captured = _capture(root)
        for name, data in captured.items():
            target = workspace / "candidate" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (workspace / "candidate/tests").mkdir(parents=True, exist_ok=True)
        (workspace / "proposal.diff").write_bytes(proposal.unified_diff.encode("utf-8"))
        trusted = workspace / "trusted"
        trusted.mkdir()
        shutil.copyfile(
            Path(__file__).with_name("patch_verification_runner.py"), trusted / "runner.py"
        )
        return workspace
    except BaseException:
        _remove_workspace(workspace)
        raise


def _remove_workspace(workspace: Path) -> None:
    try:
        shutil.rmtree(workspace)
    except OSError as error:
        raise ExecutionCleanupError("candidate workspace cleanup failed") from error


async def _join_owned(task: asyncio.Task[object]) -> object:
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done():
                return task.result()


async def _workspace(root: Path, proposal: PatchProposal) -> Path:
    preparation = asyncio.create_task(asyncio.to_thread(_prepare, root, proposal))
    try:
        return await asyncio.shield(preparation)
    except asyncio.CancelledError:
        # Preparation owns the disk copy even after cancellation; join and remove it.
        try:
            workspace = await _join_owned(preparation)
        except ExecutionCleanupError:
            raise
        except Exception:
            raise asyncio.CancelledError from None
        assert isinstance(workspace, Path)
        await _join_owned(asyncio.create_task(asyncio.to_thread(_remove_workspace, workspace)))
        raise


async def _validate_candidate(root: Path) -> None:
    validation = asyncio.create_task(asyncio.to_thread(_capture, root))
    try:
        await asyncio.shield(validation)
    except asyncio.CancelledError:
        with suppress(Exception):
            await _join_owned(validation)
        raise


def _mounts() -> tuple[tuple[str, str], ...] | None:
    paths = [
        ("/usr/bin/python3.14", "/usr/bin/python3.14"),
        ("/usr/lib/python3.14", "/usr/lib/python3.14"),
        (str(_LIBRARY_ROOT / "ld-linux-x86-64.so.2"), "/lib64/ld-linux-x86-64.so.2"),
        *((str(_LIBRARY_ROOT / name), str(_LIBRARY_ROOT / name)) for name in _LIBRARIES),
    ]
    if any(not Path(source).exists() for source, _ in paths):
        return None
    return tuple((str(Path(source).resolve()), target) for source, target in paths)


def _sandbox_argv(
    bwrap: str, workspace: Path, mounts: tuple[tuple[str, str], ...]
) -> tuple[str, ...]:
    argv = [
        bwrap,
        "--unshare-all",
        "--unshare-user",
        "--disable-userns",
        "--assert-userns-disabled",
        "--die-with-parent",
        "--cap-drop",
        "ALL",
        "--clearenv",
    ]
    for source, target in mounts:
        argv.extend(("--ro-bind", source, target))
    argv.extend(
        (
            "--symlink",
            "usr/lib",
            "/lib",
            "--ro-bind",
            str(workspace / "candidate"),
            "/candidate",
            "--ro-bind",
            str(workspace / "trusted"),
            "/trusted",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--size",
            str(8 * 1024 * 1024),
            "--tmpfs",
            "/tmp",
            "--remount-ro",
            "/proc",
            "--remount-ro",
            "/dev",
            "--remount-ro",
            "/",
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--setenv",
            "TMPDIR",
            "/tmp",
            "--chdir",
            "/candidate",
            "--",
            "/usr/bin/python3.14",
            "-I",
            "-S",
            "-B",
            "/trusted/runner.py",
        )
    )
    return tuple(argv)


async def verify_isolated_patch(
    project_root: Path,
    proposal: PatchProposal,
    *,
    profile: str = PROFILE,
    context: ExecutionContext | None = None,
) -> VerificationReport:
    if context is not None:
        context.check()
    initial = preflight_patch(proposal)
    if initial.status != "ready":
        return initial

    def report(status: str, outputs: tuple[str, ...] = ()) -> VerificationReport:
        return VerificationReport(
            proposal.proposal_id, status, initial.changed_paths, outputs, True
        )

    if profile != PROFILE:
        return report("rejected_profile")
    if not all(_supported_path(path) for path in initial.changed_paths):
        return report("rejected_source")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        return report("unsupported_platform")
    bwrap = shutil.which("bwrap", path=os.defpath)
    git = shutil.which("git", path=os.defpath)
    mounts = _mounts()
    if not bwrap or not git or mounts is None:
        return report("unsupported_sandbox")
    deadline = asyncio.get_running_loop().time() + 10
    owned_context = replace(
        context or ExecutionContext("patch-check", "owner", "single"),
        deadline=min(deadline, context.deadline)
        if context and context.deadline is not None
        else deadline,
    )
    try:
        workspace = await _workspace(project_root, proposal)
    except (OSError, _SourceRejected):
        return report("rejected_source")
    environment = {
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    try:
        candidate = workspace / "candidate"
        for command in (
            (git, "init", "-q"),
            (git, "apply", "--check", str(workspace / "proposal.diff")),
            (git, "apply", str(workspace / "proposal.diff")),
        ):
            result = await execute_bounded_argv(
                command,
                cwd=candidate,
                environment=environment,
                timeout=10,
                output_limit=4096,
                context=owned_context,
            )
            if result["returncode"] != 0 or result["truncated"]:
                return report("rejected_unappliable")
        try:
            await _validate_candidate(candidate)
        except (OSError, _SourceRejected):
            return report("rejected_source")
        argv = _sandbox_argv(bwrap, workspace, mounts)
        probe = await execute_bounded_argv(
            (*argv, "--probe"),
            cwd=workspace,
            environment={},
            timeout=10,
            output_limit=4096,
            context=owned_context,
        )
        if (
            probe["returncode"] != 0
            or probe["stdout"] != "SIRO_PATCH_PROFILE_READY_V1\n"
            or probe["truncated"]
        ):
            return report("unsupported_sandbox")
        result = await execute_bounded_argv(
            argv, cwd=workspace, environment={}, timeout=10, context=owned_context
        )
        outputs = (str(result["stdout"]), str(result["stderr"]))
        if result["returncode"] == 78:
            return report("unsupported_sandbox")
        return report(
            "passed" if result["returncode"] == 0 and not result["truncated"] else "failed_checks",
            outputs,
        )
    except TimeoutError:
        if context is not None:
            context.check()
        return report("failed_checks", ("timeout",))
    finally:
        pending_error = sys.exception()
        cleanup = asyncio.create_task(asyncio.to_thread(_remove_workspace, workspace))
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            await _join_owned(cleanup)
            raise
        if pending_error is None and context is not None:
            context.check()
