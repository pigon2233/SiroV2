"""Bounded, cancellable subprocess supervisor for trusted local Python skills."""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path

from siro.core.skills import InstalledSkill, validate_object
from siro.persistence.skills import SQLiteSkillRegistry


class SkillExecutionError(RuntimeError):
    pass


class SkillDisabled(SkillExecutionError):
    pass


class WorkerSupervisor:
    def __init__(self) -> None:
        self._concurrency: dict[tuple[str, str], asyncio.Semaphore] = {}

    async def execute(self, skill: InstalledSkill, arguments: object) -> dict[str, object]:
        key = (skill.manifest.id, skill.manifest.version)
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
            "SIRO_WORKER_MEMORY_MB": str(limits.memory_mb),
            "SIRO_WORKER_CPU_SECONDS": str(limits.cpu_seconds),
        }
        project_root = source_root.parent
        home_parts = project_root.parts[1:]
        directories: list[str] = []
        current = Path("/")
        for part in home_parts:
            current /= part
            directories.extend(("--dir", str(current)))
        command = (
            bubblewrap,
            "--unshare-net",
            "--die-with-parent",
            "--new-session",
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
            "--chdir",
            "/skill",
            sys.executable,
            "-m",
            "siro.skill_worker",
        )
        process = await asyncio.create_subprocess_exec(
            *command,
            env=environment,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        process.stdin.write(json.dumps(validated).encode())
        await process.stdin.drain()
        process.stdin.close()
        output_task = asyncio.create_task(process.stdout.read(limits.output_bytes + 1))
        error_task = asyncio.create_task(process.stderr.read(4097))
        try:
            await asyncio.wait_for(process.wait(), skill.manifest.timeout_ms / 1000)
            output = await output_task
            error = await error_task
        except (TimeoutError, asyncio.CancelledError) as failure:
            process.kill()
            await process.wait()
            output_task.cancel()
            error_task.cancel()
            if isinstance(failure, asyncio.CancelledError):
                raise
            raise SkillExecutionError("skill timed out") from failure
        if len(output) > limits.output_bytes:
            raise SkillExecutionError("skill output exceeded its limit")
        if process.returncode != 0:
            detail = error.decode(errors="replace")[:1024]
            raise SkillExecutionError(f"skill worker failed: {detail}")
        try:
            result = json.loads(output)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SkillExecutionError("skill returned invalid JSON") from error
        return validate_object(skill.output_schema, result)


class SkillDispatcher:
    def __init__(self, registry: SQLiteSkillRegistry, supervisor: WorkerSupervisor) -> None:
        self._registry = registry
        self._supervisor = supervisor

    async def execute(self, skill: InstalledSkill, arguments: object) -> dict[str, object]:
        if not await self._registry.is_enabled(skill.manifest.id, skill.manifest.version):
            raise SkillDisabled("skill is disabled")
        return await self._supervisor.execute(skill, arguments)
