"""Bounded subprocess execution and cancellation of owned foreground groups."""

from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from siro.adapters.process_network import probe_capability, sample_group
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


SignalGroup = Callable[[asyncio.subprocess.Process, signal.Signals], None]


def _signal_owned_group(process: asyncio.subprocess.Process, sig: signal.Signals) -> None:
    # start_new_session=True makes this PID the PGID. Never scan names or other sessions.
    with suppress(ProcessLookupError):
        os.killpg(process.pid, sig)


async def _cleanup_group(
    process: asyncio.subprocess.Process,
    readers: list[asyncio.Task[bytes]],
    signal_group: SignalGroup,
) -> None:
    try:
        async with asyncio.timeout(4.5):
            signal_group(process, signal.SIGTERM)
            await asyncio.sleep(0.25)
            # The leader may have exited while a descendant still holds a pipe.
            signal_group(process, signal.SIGKILL)
            await asyncio.gather(*readers, process.wait())
    except Exception as error:
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        raise ExecutionCleanupError("owned process group cleanup failed") from error


async def _protected_cleanup(
    process: asyncio.subprocess.Process,
    readers: list[asyncio.Task[bytes]],
    signal_group: SignalGroup,
) -> None:
    cleanup = asyncio.create_task(_cleanup_group(process, readers, signal_group))
    # Repeated task cancellation must not abandon an already-owned child.
    while True:
        try:
            await asyncio.shield(cleanup)
            return
        except asyncio.CancelledError:
            if cleanup.done():
                cleanup.result()
                return


_SAMPLE_INTERVAL = 0.1
_SAMPLE_LIMIT = 20


async def _sample_network(pgid: int, seen: dict[tuple[str, str, int], None]) -> None:
    while True:
        for c in await asyncio.to_thread(sample_group, pgid):
            if len(seen) < _SAMPLE_LIMIT:
                seen.setdefault((c.protocol, c.remote, c.port))
        await asyncio.sleep(_SAMPLE_INTERVAL)


def _network_sample(seen: dict[tuple[str, str, int], None]) -> dict[str, object]:
    capability = probe_capability()
    if capability.status != "sampled":
        return {"status": "unsupported", "reason": capability.reason, "connections": []}
    return {
        "status": "sampled",
        "connections": [{"protocol": p, "remote": r, "port": n} for p, r, n in seen],
    }


async def execute_bounded_argv(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: float,
    detach: bool = False,
    output_limit: int = 64 * 1024,
    context: ExecutionContext | None = None,
    stdout_errors: Literal["replace", "strict"] = "replace",
    sample_network: bool = False,
    _signal_group: SignalGroup | None = None,
) -> dict[str, object]:
    """Drain both pipes within one byte budget; cancel only the owned process group.

    An acknowledged detach retains the existing session lifetime: subsequent run
    cancellation does not stop that launched application. Cancellation before its
    acknowledgement still cleans the owned group.
    """
    signal_group = _signal_owned_group if _signal_group is None else _signal_group
    if stdout_errors not in {"replace", "strict"}:
        raise ValueError("stdout_errors must be replace or strict")
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
        await _protected_cleanup(process, [], signal_group)
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
    seen: dict[tuple[str, str, int], None] = {}
    sampler = (
        asyncio.create_task(_sample_network(process.pid, seen))
        if sample_network and not detach and probe_capability().status == "sampled"
        else None
    )
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
            await _protected_cleanup(process, readers, signal_group)
        finally:
            result_task.cancel()
            await asyncio.gather(result_task, return_exceptions=True)
        raise
    finally:
        for task in (cancel_task, sampler):
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    if detach:
        return {"argv": list(argv), "pid": process.pid, "state": "started"}
    result: dict[str, object] = {
        "argv": list(argv),
        "cwd": str(cwd),
        "returncode": process.returncode,
        "stdout": stdout.decode(errors=stdout_errors),
        "stderr": stderr.decode(errors="replace"),
        "truncated": truncated,
    }
    if sample_network:
        result["network_sample"] = _network_sample(seen)
    return result
