"""Synthetic abrupt process death around real candidate execution/journal boundaries."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


class SyntheticModel:
    name = "synthetic-crash-model"

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        yield ModelChunk("tool_request", tool_call=ToolCall("effect-1", "computer.execute", {}))
        yield ModelChunk("finished")


async def main(directory: Path, phase: str) -> None:
    store = SQLiteStore(directory / "siro.db")
    await store.initialize()

    async def effect(arguments: dict[str, object]) -> object:
        # A real external file append survives the abruptly killed controller process.
        with (directory / "effect.txt").open("a") as stream:
            stream.write("one-effect\n")
            stream.flush()
            os.fsync(stream.fileno())
        return {"confirmed": True}

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": effect}
    )
    controller = IntegratedCompanion(
        directory,
        SyntheticModel(),
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    await controller.startup()
    original = orchestrator.journal_hook
    assert original is not None

    async def crash_hook(run: str, call: str, event: str, value: object) -> None:
        if (phase == "before_dispatch" and event == "dispatch") or (
            phase == "before_observation" and event == "observation"
        ):
            os._exit(42)
        await original(run, call, event, value)
        if (phase == "after_dispatch" and event == "dispatch") or (
            phase == "after_observation" and event == "observation"
        ):
            os._exit(42)

    orchestrator.journal_hook = crash_hook
    await controller.respond("crash-session", "synthetic goal; do not replay")
    raise AssertionError("fixture did not reach crash boundary")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), sys.argv[2]))
