"""Reserve terminal-bookkeeping time without reducing contextual cleanup ownership."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.execution import ExecutionContext
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


class SyntheticToolModel:
    name = "cancel-budget-synthetic"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        assert len(self.requests) == 1, "a cancelled run must not resume its model"
        yield ModelChunk(
            "tool_request",
            tool_call=ToolCall("owned-call", "computer.execute", {"argv": ["synthetic-owned"]}),
        )
        yield ModelChunk("finished")


class ObservedHub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    async def broadcast(self, message: dict[str, object], *, urgent: bool = False) -> None:
        self.events.append(message)


def unknown_call(view: dict[str, object]) -> None:
    assert view["runtime_profile"] == "candidate" and view["runtime_version"] == 1
    assert view["recovery_status"] == "terminal"
    calls = view["calls"]
    assert isinstance(calls, list) and len(calls) == 1
    call = calls[0]
    assert isinstance(call, dict)
    assert call["call_id"] == "owned-call" and call["dispatched"] == 1
    encoded = call["observation_json"]
    assert isinstance(encoded, str)
    observation = json.loads(encoded)
    assert isinstance(observation, dict) and observation["error"] == "outcome_unknown"


@pytest.fixture
def terminal_bookkeeping_delay(monkeypatch: pytest.MonkeyPatch) -> asyncio.Event:
    """A controlled await at the existing journal boundary; never changes SQLite behavior."""
    original = SQLiteAgentRunRepository.finish_journal
    entered = asyncio.Event()

    async def delayed(
        self: SQLiteAgentRunRepository, run_id: str, *, interrupted: bool = False
    ) -> None:
        entered.set()
        await asyncio.sleep(0.5)
        await original(self, run_id, interrupted=interrupted)

    monkeypatch.setattr(SQLiteAgentRunRepository, "finish_journal", delayed)
    return entered


@pytest.mark.asyncio
async def test_arguments_only_cancel_reserves_terminal_bookkeeping_with_original_total_bound(
    tmp_path: Path, terminal_bookkeeping_delay: asyncio.Event
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(arguments: dict[str, object]) -> object:
        assert arguments == {"argv": ["synthetic-owned"]}
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()  # Fixture intentionally cannot prove cleanup before release.
        return {"not_proven_stopped": True}

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": handler}
    )
    hub = ObservedHub()
    controller = IntegratedCompanion(
        tmp_path,
        SyntheticToolModel(),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    task = asyncio.create_task(controller.respond("owned-arguments", "synthetic goal"))
    try:
        await asyncio.wait_for(entered.wait(), 10)
        started = asyncio.get_running_loop().time()
        await controller.cancel("active", "stop", session_id="owned-arguments")
        elapsed = asyncio.get_running_loop().time() - started
        assert terminal_bookkeeping_delay.is_set()
        readback = await controller.recovery_readback("owned-arguments")
        assert readback is not None and readback["state"] == "failed"
        assert readback["error"] == "ExecutionCleanupError"
        unknown_call(readback)
        assert any(orchestrator._active.values()), "late cleanup must retain task ownership"
        event_count = len(hub.events)
        release.set()
        await asyncio.wait_for(task, 2)
        assert await controller.recovery_readback("owned-arguments") == readback
        assert len(hub.events) == event_count
        assert not any(orchestrator._active.values())
        assert len([event for event in hub.events if event["type"] == "assistant_terminal"]) == 1
        assert elapsed < 5, "original user-total cancellation bound includes terminal bookkeeping"
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_contextual_cancel_keeps_backend_cleanup_window_and_joins_before_terminal(
    tmp_path: Path, terminal_bookkeeping_delay: asyncio.Event
) -> None:
    entered, cleaned = asyncio.Event(), asyncio.Event()

    async def arguments_only(arguments: dict[str, object]) -> object:
        raise AssertionError("contextual executor must own this dispatch")

    async def contextual(arguments: dict[str, object], context: ExecutionContext) -> object:
        assert arguments == {"argv": ["synthetic-owned"]} and context.authorized
        entered.set()
        await context.cancellation.wait()
        await asyncio.sleep(4.2)  # A backend cleanup that fits the original 4.75-second window.
        cleaned.set()
        context.check()
        raise AssertionError("cancelled contextual dispatch must not claim success")

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store),
        {"computer.execute": arguments_only},
        contextual_executors={"computer.execute": contextual},
    )
    hub = ObservedHub()
    controller = IntegratedCompanion(
        tmp_path,
        SyntheticToolModel(),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    task = asyncio.create_task(controller.respond("owned-contextual", "synthetic goal"))
    try:
        await asyncio.wait_for(entered.wait(), 10)
        started = asyncio.get_running_loop().time()
        await controller.cancel("active", "stop", session_id="owned-contextual")
        elapsed = asyncio.get_running_loop().time() - started
        assert cleaned.is_set(), "the contextual cleanup must finish before terminal"
        assert terminal_bookkeeping_delay.is_set()
        assert not any(orchestrator._active.values())
        readback = await controller.recovery_readback("owned-contextual")
        assert readback is not None and readback["state"] == "cancelled"
        assert readback["error"] == "stop"
        unknown_call(readback)
        event_count = len(hub.events)
        await asyncio.wait_for(task, 2)
        assert await controller.recovery_readback("owned-contextual") == readback
        assert len(hub.events) == event_count
        assert len([event for event in hub.events if event["type"] == "assistant_terminal"]) == 1
        assert elapsed < 5, "contextual cleanup and bookkeeping retain the original total bound"
    finally:
        if not task.done():
            await controller.cancel("active", "fixture cleanup", session_id="owned-contextual")
        await asyncio.gather(task, return_exceptions=True)
