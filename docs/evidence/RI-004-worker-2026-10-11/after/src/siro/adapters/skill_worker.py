"""Bounded, cancellable subprocess supervisor for trusted local Python skills."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from siro.adapters.isolated_python import runtime_mounts, sandbox_argv
from siro.adapters.process_execution import (
    ExecutionCleanupError,
    ExecutionContext,
    execute_bounded_argv,
)
from siro.core.skills import InstalledSkill, capture_skill, load_skill, validate_object
from siro.persistence.skills import SQLiteSkillRegistry


class SkillExecutionError(RuntimeError):
    pass


class SkillDisabled(SkillExecutionError):
    pass


@dataclass(frozen=True, slots=True)
class _PreparedSkill:
    identity: InstalledSkill
    snapshot: InstalledSkill
    directory: tempfile.TemporaryDirectory[str]


def _prepare_skill(skill: InstalledSkill) -> _PreparedSkill:
    current, files = capture_skill(skill.root)
    if current != skill:
        raise ValueError("skill package differs from the supplied identity")
    directory = tempfile.TemporaryDirectory(prefix="siro-skill-verified-")
    try:
        root = Path(directory.name)
        for relative, (data, executable) in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o444 | executable)
        if load_skill(current.root) != current:
            raise ValueError("skill source changed during preparation")
        snapshot = load_skill(root)
        if snapshot.manifest_hash != current.manifest_hash:
            raise ValueError("skill snapshot differs from captured bytes")
        return _PreparedSkill(current, snapshot, directory)
    except BaseException:
        directory.cleanup()
        raise


async def _join_owned[T](task: asyncio.Task[T], *, propagate_cancellation: bool = True) -> T:
    """Finish owned preparation/cleanup even if the caller repeats cancellation."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
            continue
    result = task.result()
    if cancelled and propagate_cancellation:
        raise asyncio.CancelledError
    return result


_REQUEST_MAX_BYTES = 64 * 1024


def _prepare_request(arguments: dict[str, object]) -> Path:
    payload = json.dumps(arguments, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > _REQUEST_MAX_BYTES:
        raise ValueError("skill request exceeded its byte limit")
    workspace = Path(tempfile.mkdtemp(prefix="siro-skill-request-")).resolve()
    try:
        request = workspace / "request.json"
        request.write_bytes(payload)
        request.chmod(0o400)
        return workspace
    except BaseException:
        _remove_request(workspace)
        raise


def _remove_request(workspace: Path) -> None:
    try:
        shutil.rmtree(workspace)
    except OSError as error:
        raise ExecutionCleanupError("skill request cleanup failed") from error


async def _request(arguments: dict[str, object]) -> Path:
    preparation = asyncio.create_task(asyncio.to_thread(_prepare_request, arguments))
    try:
        return await asyncio.shield(preparation)
    except asyncio.CancelledError:
        try:
            workspace = await _join_owned(preparation, propagate_cancellation=False)
        except (OSError, ValueError):
            raise asyncio.CancelledError from None
        await _join_owned(
            asyncio.create_task(asyncio.to_thread(_remove_request, workspace)),
            propagate_cancellation=False,
        )
        raise


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON is unsupported")


_STRICT_PROFILE = "python-stdlib-single"


def _strict_manifest(skill: InstalledSkill) -> bool:
    manifest = skill.manifest
    limits = manifest.resource_limits
    return (
        manifest.entrypoint == "python:plugin:run"
        and manifest.input_schema == "input.json"
        and manifest.output_schema == "output.json"
        and not manifest.permissions
        and manifest.risk == "observe"
        and manifest.idempotency == "read_only"
        and manifest.network == "denied"
        and manifest.concurrency == 1
        and manifest.cancellation == "process"
        and manifest.compensation == "none"
        and 16 <= limits.memory_mb <= 256
        and 1 <= limits.cpu_seconds <= 5
        and 1 <= limits.output_bytes <= 131072
        and 10 <= manifest.timeout_ms <= 10000
    )


def _strict_runtime() -> tuple[str, tuple[tuple[str, str], ...]]:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SkillExecutionError("strict skill sandbox unavailable")
    bubblewrap = shutil.which("bwrap", path=os.defpath)
    mounts = runtime_mounts()
    if bubblewrap is None or mounts is None:
        raise SkillExecutionError("strict skill sandbox unavailable")
    return bubblewrap, mounts


def _strict_identity(current: InstalledSkill, supplied: InstalledSkill) -> bool:
    if current.root != supplied.root or current.manifest_hash != supplied.manifest_hash:
        return False

    def metadata(value: InstalledSkill) -> str:
        return json.dumps(
            [value.manifest.model_dump(mode="python"), value.input_schema, value.output_schema],
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )

    try:
        return metadata(current) == metadata(supplied)
    except (TypeError, ValueError, RecursionError):
        return False


def _prepare_strict(workspace: Path, skill: InstalledSkill) -> InstalledSkill:
    """Freeze verified package bytes; trusted control files stay outside its identity."""
    try:
        current, files = capture_skill(skill.root)
        if not _strict_identity(current, skill):
            raise ValueError("supplied identity differs from captured package")
    except (OSError, ValueError, KeyError) as error:
        raise SkillExecutionError("skill package verification failed") from error
    if not _strict_manifest(current) or set(files) != {
        "manifest.json",
        "input.json",
        "output.json",
        "plugin.py",
    }:
        raise SkillExecutionError("unsupported strict skill profile")
    candidate = workspace / "candidate"
    candidate.mkdir()
    for name, (data, executable) in files.items():
        path = candidate / name
        path.write_bytes(data)
        path.chmod(0o444 | executable)
    try:
        verified = load_skill(candidate)
        if (
            not _strict_identity(load_skill(skill.root), current)
            or verified.manifest_hash != current.manifest_hash
        ):
            raise ValueError("skill changed during preparation")
    except (OSError, ValueError, KeyError) as error:
        raise SkillExecutionError("skill package verification failed") from error
    trusted = workspace / "trusted"
    trusted.mkdir()
    adapter_root = Path(__file__).parent
    for source, target in (
        ("strict_skill_runner.py", "runner.py"),
        ("python_restrictions.py", "python_restrictions.py"),
    ):
        shutil.copyfile(adapter_root / source, trusted / target)
    (workspace / "request.json").rename(trusted / "request.json")
    limits = verified.manifest.resource_limits
    (trusted / "limits.json").write_text(
        json.dumps({"memory_mb": limits.memory_mb, "cpu_seconds": limits.cpu_seconds}),
        encoding="utf-8",
    )
    for path in trusted.iterdir():
        path.chmod(0o400)
    return verified


class WorkerSupervisor:
    def __init__(self, *, profile: str = "trusted-local") -> None:
        if profile not in {"trusted-local", _STRICT_PROFILE}:
            raise ValueError("unsupported skill worker profile")
        self._profile = profile
        self._concurrency: dict[tuple[str, str, str], asyncio.Semaphore] = {}

    async def execute(self, skill: InstalledSkill, arguments: object) -> dict[str, object]:
        if self._profile == _STRICT_PROFILE and not _strict_manifest(skill):
            raise SkillExecutionError("unsupported strict skill profile")
        key = (skill.manifest.id, skill.manifest.version, skill.manifest_hash)
        semaphore = self._concurrency.setdefault(key, asyncio.Semaphore(skill.manifest.concurrency))
        async with semaphore:
            return await self._execute_one(skill, arguments)

    async def _execute_one(self, skill: InstalledSkill, arguments: object) -> dict[str, object]:
        if self._profile == _STRICT_PROFILE:
            return await self._execute_strict(skill, arguments)
        validated = validate_object(skill.input_schema, arguments)
        limits = skill.manifest.resource_limits
        bubblewrap = shutil.which("bwrap")
        if bubblewrap is None or not sys.platform.startswith("linux"):
            raise SkillExecutionError("a supported bubblewrap sandbox is required")
        source_root = Path(__file__).parents[2]
        environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "PYTHONUNBUFFERED": "1",
            "SIRO_SKILL_ROOT": "/skill",
            "SIRO_SKILL_ENTRYPOINT": skill.manifest.entrypoint,
            "SIRO_SKILL_REQUEST": "/request.json",
            "SIRO_WORKER_MEMORY_MB": str(limits.memory_mb),
            "SIRO_WORKER_CPU_SECONDS": str(limits.cpu_seconds),
        }
        project_root = source_root.parent
        directories: list[str] = []
        current = Path("/")
        for part in project_root.parts[1:]:
            current /= part
            directories.extend(("--dir", str(current)))
        workspace = await _request(validated)
        try:
            command = (
                bubblewrap,
                "--unshare-net",
                "--unshare-pid",
                "--die-with-parent",
                "--ro-bind",
                "/usr",
                "/usr",
                "--ro-bind",
                "/lib",
                "/lib",
                "--ro-bind",
                "/lib64",
                "/lib64",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--tmpfs",
                "/tmp",
                *directories,
                "--ro-bind",
                str(project_root / ".venv"),
                str(project_root / ".venv"),
                "--ro-bind",
                str(source_root),
                str(source_root),
                "--ro-bind",
                str(skill.root),
                "/skill",
                "--ro-bind",
                str(workspace / "request.json"),
                "/request.json",
                "--chdir",
                "/skill",
                sys.executable,
                "-m",
                "siro.skill_worker",
            )
            try:
                result = await execute_bounded_argv(
                    command,
                    cwd=workspace,
                    environment=environment,
                    timeout=skill.manifest.timeout_ms / 1000,
                    output_limit=max(limits.output_bytes, 4096),
                    stdout_errors="strict",
                )
            except TimeoutError as error:
                raise SkillExecutionError("skill timed out") from error
            except UnicodeDecodeError as error:
                raise SkillExecutionError("skill returned invalid JSON") from error
            output = str(result["stdout"])
            if result["truncated"] or len(output.encode("utf-8")) > limits.output_bytes:
                raise SkillExecutionError("skill output exceeded its limit")
            if result["returncode"] != 0:
                raise SkillExecutionError("skill worker failed")
            try:
                response = json.loads(output, parse_constant=_reject_constant)
            except (UnicodeDecodeError, ValueError) as error:
                raise SkillExecutionError("skill returned invalid JSON") from error
            return validate_object(skill.output_schema, response)
        finally:
            pending = sys.exception()
            await _join_owned(
                asyncio.create_task(asyncio.to_thread(_remove_request, workspace)),
                propagate_cancellation=not isinstance(pending, ExecutionCleanupError),
            )

    async def _execute_strict(self, skill: InstalledSkill, arguments: object) -> dict[str, object]:
        if not _strict_manifest(skill):
            raise SkillExecutionError("unsupported strict skill profile")
        validated = validate_object(skill.input_schema, arguments)
        bubblewrap, mounts = await _join_owned(
            asyncio.create_task(asyncio.to_thread(_strict_runtime))
        )
        workspace = await _request(validated)
        try:
            verified = await _join_owned(
                asyncio.create_task(asyncio.to_thread(_prepare_strict, workspace, skill))
            )
            validate_object(verified.input_schema, validated)
            argv = sandbox_argv(bubblewrap, workspace, mounts)
            deadline = asyncio.get_running_loop().time() + verified.manifest.timeout_ms / 1000
            limits = verified.manifest.resource_limits
            context = ExecutionContext(
                "skill-worker", verified.manifest.id, verified.manifest_hash, deadline=deadline
            )

            async def execute(command: tuple[str, ...]) -> dict[str, object]:
                return await execute_bounded_argv(
                    command,
                    cwd=workspace,
                    environment={},
                    timeout=max(0, deadline - asyncio.get_running_loop().time()),
                    output_limit=max(limits.output_bytes, 4096),
                    stdout_errors="strict",
                    context=context,
                )

            try:
                probe = await execute((*argv, "--probe"))
            except UnicodeDecodeError as error:
                raise SkillExecutionError("strict skill sandbox unavailable") from error
            if (
                probe["returncode"] != 0
                or probe["truncated"]
                or probe["stdout"] != "SIRO_SKILL_PROFILE_READY_V1\n"
            ):
                raise SkillExecutionError("strict skill sandbox unavailable")
            try:
                result = await execute(argv)
            except UnicodeDecodeError as error:
                raise SkillExecutionError("skill returned invalid JSON") from error
            output = str(result["stdout"])
            if result["truncated"] or len(output.encode("utf-8")) > limits.output_bytes:
                raise SkillExecutionError("skill output exceeded its limit")
            if result["returncode"] == 78:
                raise SkillExecutionError("strict skill sandbox unavailable")
            if result["returncode"] != 0:
                raise SkillExecutionError("skill worker failed")
            try:
                response = json.loads(output, parse_constant=_reject_constant)
            except ValueError as error:
                raise SkillExecutionError("skill returned invalid JSON") from error
            return validate_object(verified.output_schema, response)
        except TimeoutError as error:
            raise SkillExecutionError("skill timed out") from error
        finally:
            pending = sys.exception()
            await _join_owned(
                asyncio.create_task(asyncio.to_thread(_remove_request, workspace)),
                propagate_cancellation=not isinstance(pending, ExecutionCleanupError),
            )


class SkillDispatcher:
    def __init__(self, registry: SQLiteSkillRegistry, supervisor: WorkerSupervisor) -> None:
        self._registry = registry
        self._supervisor = supervisor
        self._snapshot_slots = asyncio.Semaphore(8)

    async def execute(self, skill: InstalledSkill, arguments: object) -> dict[str, object]:
        async with self._snapshot_slots:
            return await self._execute_verified(skill, arguments)

    async def _execute_verified(
        self, skill: InstalledSkill, arguments: object
    ) -> dict[str, object]:
        if not await self._registry.is_enabled(
            skill.manifest.id, skill.manifest.version, identity=skill
        ):
            raise SkillDisabled("skill is disabled or requires package approval")
        preparation = asyncio.create_task(asyncio.to_thread(_prepare_skill, skill))
        try:
            prepared = await asyncio.shield(preparation)
        except asyncio.CancelledError:
            try:
                prepared = await _join_owned(preparation, propagate_cancellation=False)
            except (OSError, ValueError):
                pass
            else:
                await _join_owned(
                    asyncio.create_task(asyncio.to_thread(prepared.directory.cleanup))
                )
            raise
        except (OSError, ValueError) as error:
            raise SkillDisabled("skill requires package verification and approval") from error
        try:
            if not await self._registry.is_enabled(
                skill.manifest.id, skill.manifest.version, identity=prepared.identity
            ):
                raise SkillDisabled("skill is disabled or requires package approval")
            return await self._supervisor.execute(prepared.snapshot, arguments)
        finally:
            pending = sys.exception()
            await _join_owned(
                asyncio.create_task(asyncio.to_thread(prepared.directory.cleanup)),
                propagate_cancellation=not isinstance(pending, ExecutionCleanupError),
            )
