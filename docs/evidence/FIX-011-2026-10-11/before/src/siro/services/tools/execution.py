"""Bounded subprocess execution and cancellation of owned foreground groups."""

from __future__ import annotations

import asyncio
import os
import signal
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from siro.ports.models import CancellationToken


class ExecutionCancelled(Exception):
    """The run was fenced before dispatch or while its executor was active."""


class ExecutionCleanupError(Exception):
    """Owned process cleanup failed within its bounded grace period."""


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    run_id: str
    session_id: str
    epoch: str
    cancellation: CancellationToken = field(default_factory=CancellationToken)
    deadline: float | None = None  # event-loop monotonic time, not wall clock
    proposal_id: str = ""
    call_id: str = ""
    authorized: bool = False

    def check(self) -> None:
        if self.cancellation.cancelled:
            raise ExecutionCancelled("run cancelled")
        if self.deadline is not None and asyncio.get_running_loop().time() >= self.deadline:
            raise TimeoutError("execution deadline exceeded")


def _signal_owned_group(process: asyncio.subprocess.Process, sig: signal.Signals) -> None:
    # start_new_session=True makes this PID the PGID. Never scan names or other sessions.
    with suppress(ProcessLookupError):
        os.killpg(process.pid, sig)


async def _cleanup_group(
    process: asyncio.subprocess.Process, readers: list[asyncio.Task[bytes]]
) -> None:
    try:
        async with asyncio.timeout(4.5):
            _signal_owned_group(process, signal.SIGTERM)
            await asyncio.sleep(0.25)
            # The leader may have exited while a descendant still holds a pipe.
            _signal_owned_group(process, signal.SIGKILL)
            await asyncio.gather(*readers, process.wait())
    except Exception as error:
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        raise ExecutionCleanupError("owned process group cleanup failed") from error


async def _protected_cleanup(
    process: asyncio.subprocess.Process, readers: list[asyncio.Task[bytes]]
) -> None:
    cleanup = asyncio.create_task(_cleanup_group(process, readers))
    # Repeated task cancellation must not abandon an already-owned child.
    while True:
        try:
            await asyncio.shield(cleanup)
            return
        except asyncio.CancelledError:
            if cleanup.done():
                cleanup.result()
                return


async def execute_bounded_argv(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: int,
    detach: bool = False,
    output_limit: int = 64 * 1024,
    context: ExecutionContext | None = None,
) -> dict[str, object]:
    """Drain both pipes within one byte budget; cancel only the owned process group.

    An acknowledged detach retains the existing session lifetime: subsequent run
    cancellation does not stop that launched application. Cancellation before its
    acknowledgement still cleans the owned group.
    """
    if output_limit < 1:
        raise ValueError("output_limit must be positive")
    if context is not None:
        context.check()
    spawn = asyncio.create_task(
        asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=environment,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL if detach else asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL if detach else asyncio.subprocess.PIPE,
            start_new_session=True,
            limit=64 * 1024,
        )
    )
    try:
        process = await asyncio.shield(spawn)
    except asyncio.CancelledError:
        while not spawn.done():
            try:
                await asyncio.shield(spawn)
            except asyncio.CancelledError:
                continue
        process = spawn.result()
        await _protected_cleanup(process, [])
        raise
    remaining = output_limit
    truncated = False

    async def drain(stream: asyncio.StreamReader | None) -> bytes:
        nonlocal remaining, truncated
        assert stream is not None
        retained = bytearray()
        while chunk := await stream.read(16 * 1024):
            keep = min(len(chunk), remaining)
            retained.extend(chunk[:keep])
            remaining -= keep
            truncated |= keep < len(chunk)
        return bytes(retained)

    readers = (
        []
        if detach
        else [
            asyncio.create_task(drain(process.stdout)),
            asyncio.create_task(drain(process.stderr)),
        ]
    )

    async def collect() -> tuple[bytes, bytes]:
        if detach:
            await asyncio.sleep(0.25)
            return b"", b""
        stdout, stderr = await asyncio.gather(*readers)
        await process.wait()
        return stdout, stderr

    result_task = asyncio.create_task(collect())
    cancel_task = asyncio.create_task(context.cancellation.wait()) if context is not None else None
    try:
        if context is not None:
            context.check()
        budget = float(timeout)
        if context is not None and context.deadline is not None:
            budget = min(budget, context.deadline - asyncio.get_running_loop().time())
        watched = {result_task} if cancel_task is None else {result_task, cancel_task}
        done, _ = await asyncio.wait(
            watched, timeout=max(0, budget), return_when=asyncio.FIRST_COMPLETED
        )
        if context is not None:
            context.check()  # cancellation wins the simultaneous-completion boundary
        if result_task not in done:
            raise TimeoutError("computer.execute exceeded its timeout")
        stdout, stderr = result_task.result()
    except BaseException:
        # Keep readers draining through TERM/KILL, including descendants' inherited pipes.
        try:
            await _protected_cleanup(process, readers)
        finally:
            result_task.cancel()
            await asyncio.gather(result_task, return_exceptions=True)
        raise
    finally:
        if cancel_task is not None:
            cancel_task.cancel()
            await asyncio.gather(cancel_task, return_exceptions=True)
    if detach:
        return {"argv": list(argv), "pid": process.pid, "state": "started"}
    return {
        "argv": list(argv),
        "cwd": str(cwd),
        "returncode": process.returncode,
        "stdout": stdout.decode(errors="replace"),
        "stderr": stderr.decode(errors="replace"),
        "truncated": truncated,
    }
