"""Scoped Linux file and process primitives used by built-in computer skills."""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import tempfile
from dataclasses import dataclass
from pathlib import Path


class ScopeViolation(PermissionError):
    pass


class ComputerActionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class ScopedFileDriver:
    def __init__(self, roots: tuple[Path, ...], *, output_limit: int = 1024 * 1024) -> None:
        if not roots:
            raise ValueError("at least one file root is required")
        self._roots = tuple(root.resolve(strict=True) for root in roots)
        self._output_limit = output_limit
        self._ledger: dict[str, object] = {}

    def read_text(self, path: Path) -> str:
        resolved = self._resolve(path, must_exist=True)
        data = resolved.read_bytes()
        if len(data) > self._output_limit:
            raise ComputerActionError("file exceeds output limit")
        return data.decode("utf-8")

    def list(self, path: Path) -> tuple[str, ...]:
        resolved = self._resolve(path, must_exist=True)
        names = tuple(sorted(item.name for item in resolved.iterdir()))
        if sum(len(name.encode()) for name in names) > self._output_limit:
            raise ComputerActionError("directory listing exceeds output limit")
        return names

    def write_text(self, action_id: str, path: Path, text: str) -> int:
        previous = self._ledger.get(action_id)
        if previous is not None:
            if not isinstance(previous, int):
                raise ComputerActionError("action id was reused for another operation")
            return previous
        encoded = text.encode("utf-8")
        if len(encoded) > self._output_limit:
            raise ComputerActionError("write exceeds output limit")
        resolved = self._resolve(path, must_exist=False)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".siro-", dir=resolved.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, resolved)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        self._ledger[action_id] = len(encoded)
        return len(encoded)

    def move(self, action_id: str, source: Path, destination: Path) -> str:
        previous = self._ledger.get(action_id)
        if previous is not None:
            if not isinstance(previous, str):
                raise ComputerActionError("action id was reused for another operation")
            return previous
        resolved_source = self._resolve(source, must_exist=True)
        resolved_destination = self._resolve(destination, must_exist=False)
        if resolved_destination.exists():
            raise FileExistsError(resolved_destination)
        resolved_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(resolved_source, resolved_destination)
        result = str(resolved_destination)
        self._ledger[action_id] = result
        return result

    def _resolve(self, path: Path, *, must_exist: bool) -> Path:
        resolved = path.resolve(strict=must_exist)
        if not any(resolved == root or root in resolved.parents for root in self._roots):
            raise ScopeViolation(f"path escapes allowed roots: {path}")
        return resolved


class ProcessDriver:
    def __init__(self, allowed_cwds: tuple[Path, ...], *, output_limit: int = 1024 * 1024) -> None:
        self._allowed_cwds = tuple(path.resolve(strict=True) for path in allowed_cwds)
        self._output_limit = output_limit
        self._managed: dict[int, asyncio.subprocess.Process] = {}
        self._start_ledger: dict[str, int] = {}
        self._run_ledger: dict[str, ProcessResult] = {}

    def list_managed(self) -> tuple[int, ...]:
        return tuple(
            sorted(pid for pid, process in self._managed.items() if process.returncode is None)
        )

    async def start(self, action_id: str, argv: tuple[str, ...], cwd: Path) -> int:
        previous = self._start_ledger.get(action_id)
        if previous is not None:
            return previous
        resolved_cwd = self._validate_command(argv, cwd)
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=resolved_cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        self._managed[process.pid] = process
        self._start_ledger[action_id] = process.pid
        return process.pid

    async def stop(self, pid: int, *, timeout: float = 1.0) -> None:
        process = self._managed.get(pid)
        if process is None:
            raise ScopeViolation("process is not owned by this driver")
        if process.returncode is None:
            os.killpg(pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), timeout)
            except TimeoutError:
                os.killpg(pid, signal.SIGKILL)
                await process.wait()
        self._managed.pop(pid, None)

    async def run(
        self, action_id: str, argv: tuple[str, ...], cwd: Path, *, timeout: float
    ) -> ProcessResult:
        previous = self._run_ledger.get(action_id)
        if previous is not None:
            return previous
        resolved_cwd = self._validate_command(argv, cwd)

        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=resolved_cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = await asyncio.wait_for(self._collect(process), timeout)
        except (TimeoutError, asyncio.CancelledError) as failure:
            os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
            if isinstance(failure, asyncio.CancelledError):
                raise
            raise ComputerActionError("process timed out") from failure
        if len(stdout) + len(stderr) > self._output_limit:
            raise ComputerActionError("process output exceeds limit")
        result = ProcessResult(process.returncode or 0, stdout, stderr)
        self._run_ledger[action_id] = result
        return result

    def _validate_command(self, argv: tuple[str, ...], cwd: Path) -> Path:
        if not argv or any("\x00" in argument for argument in argv):
            raise ValueError("argv must contain non-empty safe strings")
        resolved_cwd = cwd.resolve(strict=True)
        if not any(
            resolved_cwd == allowed or allowed in resolved_cwd.parents
            for allowed in self._allowed_cwds
        ):
            raise ScopeViolation("cwd escapes allowed roots")
        return resolved_cwd

    async def _collect(self, process: asyncio.subprocess.Process) -> tuple[bytes, bytes]:
        assert process.stdout is not None
        assert process.stderr is not None
        stdout_task = asyncio.create_task(process.stdout.read(self._output_limit + 1))
        stderr_task = asyncio.create_task(process.stderr.read(self._output_limit + 1))
        wait_task = asyncio.create_task(process.wait())
        pending: set[asyncio.Task[object]] = {stdout_task, stderr_task, wait_task}
        while not wait_task.done():
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task in (stdout_task, stderr_task):
                    data = task.result()
                    if isinstance(data, bytes) and len(data) > self._output_limit:
                        os.killpg(process.pid, signal.SIGKILL)
                        await wait_task
                        for remaining in pending - done:
                            remaining.cancel()
                        raise ComputerActionError("process output exceeds limit")
                pending.discard(task)
        stdout, stderr = await asyncio.gather(stdout_task, stderr_task)
        return stdout, stderr
