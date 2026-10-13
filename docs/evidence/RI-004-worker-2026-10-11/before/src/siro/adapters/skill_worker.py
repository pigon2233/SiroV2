"""Bounded, cancellable subprocess supervisor for trusted local Python skills."""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from siro.adapters.process_execution import ExecutionCleanupError, execute_bounded_argv
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


class WorkerSupervisor:
    def __init__(self) -> None:
        self._concurrency: dict[tuple[str, str, str], asyncio.Semaphore] = {}

    async def execute(self, skill: InstalledSkill, arguments: object) -> dict[str, object]:
        key = (skill.manifest.id, skill.manifest.version, skill.manifest_hash)
        semaphore = self._concurrency.setdefault(key, asyncio.Semaphore(skill.manifest.concurrency))
        async with semaphore:
            return await self._execute_one(skill, arguments)

    async def _execute_one(self, skill: InstalledSkill, arguments: object) -> dict[str, object]:
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
