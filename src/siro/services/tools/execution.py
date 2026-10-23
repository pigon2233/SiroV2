"""Compatible service entry point for the sole lower-layer process owner."""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path

from siro.adapters import process_execution as _process_execution
from siro.adapters.process_execution import (
    ExecutionCancelled as ExecutionCancelled,
)
from siro.adapters.process_execution import (
    ExecutionCleanupError as ExecutionCleanupError,
)
from siro.adapters.process_execution import (
    ExecutionContext as ExecutionContext,
)

_signal_owned_group = _process_execution._signal_owned_group


def _forward_signal_owned_group(process: asyncio.subprocess.Process, sig: signal.Signals) -> None:
    # Keep the existing service-level cleanup-refusal seam local to this caller.
    _signal_owned_group(process, sig)


async def _protected_cleanup(
    process: asyncio.subprocess.Process, readers: list[asyncio.Task[bytes]]
) -> None:
    """Preserve the owned application-launch cleanup caller's original API."""
    await _process_execution._protected_cleanup(process, readers, _forward_signal_owned_group)


async def execute_bounded_argv(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: float,
    detach: bool = False,
    output_limit: int = 64 * 1024,
    context: ExecutionContext | None = None,
    sample_network: bool = False,
) -> dict[str, object]:
    """Delegate without adding a process, queue, retry, or cancellation owner."""
    return await _process_execution.execute_bounded_argv(
        argv,
        cwd=cwd,
        environment=environment,
        timeout=timeout,
        detach=detach,
        output_limit=output_limit,
        context=context,
        sample_network=sample_network,
        _signal_group=_forward_signal_owned_group,
    )
