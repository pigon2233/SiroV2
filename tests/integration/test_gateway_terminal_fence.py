from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from siro.services.presentation.gateway import ClientChannel


class BufferedSocket:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.drained = asyncio.Event()
        self.messages: list[dict[str, object]] = []

    async def send_json(self, data: object) -> None:
        assert isinstance(data, dict)
        if data["type"] == "snapshot":
            self.entered.set()
            await self.release.wait()
        self.messages.append(data)
        if data["type"] == "barrier":
            self.drained.set()

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_urgent", [False, True])
async def test_real_writer_buffers_100_cancelled_streams(terminal_urgent: bool) -> None:
    for iteration in range(100):
        socket = BufferedSocket()
        channel = ClientChannel(
            "client", socket, urgent_capacity=64, normal_capacity=64, terminal_fencing=True
        )
        assert channel.enqueue({"type": "snapshot"})
        channel.start()
        try:
            await asyncio.wait_for(socket.entered.wait(), 2)
            stream = str(iteration)
            for kind in ["tool_proposal", "tool_started", "tool_result"] * 10:
                assert channel.enqueue({"type": kind, "stream_id": stream}, urgent=True)
            assert channel.enqueue(
                {"type": "assistant_terminal", "stream_id": stream}, urgent=terminal_urgent
            )
            for kind in [
                "assistant_started",
                "assistant_delta",
                "affect_state",
                "agent_step",
                "tool_proposal",
                "tool_started",
                "tool_result",
                "assistant_terminal",
            ]:
                assert channel.enqueue({"type": kind, "stream_id": stream})
            assert channel.enqueue({"type": "assistant_delta", "stream_id": "next"})
            assert channel.enqueue({"type": "assistant_delta", "stream_id": "other-session"})
            assert channel.enqueue({"type": "barrier"})
            socket.release.set()
            await asyncio.wait_for(socket.drained.wait(), 2)
            terminal = next(
                i
                for i, event in enumerate(socket.messages)
                if event["type"] == "assistant_terminal"
            )
            assert not any(
                event.get("stream_id") == stream for event in socket.messages[terminal + 1 :]
            ), iteration
            assert {event.get("stream_id") for event in socket.messages[terminal + 1 :]} >= {
                "next",
                "other-session",
            }
        finally:
            socket.release.set()
            await channel.stop()


def test_actual_frontend_terminal_consumer() -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    block = html[html.index("function createTerminalFence") : html.index("async function boot")]
    script = (
        block
        + """
const assert = require('node:assert/strict');
assert(acceptRunEvent({type:'assistant_terminal', stream_id:'old'}));
for (const type of ['assistant_started','assistant_delta','affect_state','agent_step',
                    'tool_proposal','tool_started','tool_result','assistant_terminal']) {
  assert.equal(acceptRunEvent({type,stream_id:'old'}),false);
  assert.equal(acceptRunEvent({type,stream_id:'new-'+type}),true);
}
assert(acceptRunEvent({type:'assistant_delta'}));
"""
    )
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    assert html.index("if (!acceptRunEvent(data)) return;") < html.index("log(data);")


@pytest.mark.asyncio
async def test_manual_proposal_events_share_delivery_stream() -> None:
    from siro.services.presentation.gateway import GatewayHub

    hub = GatewayHub()
    hub.enable_terminal_fencing()
    socket = BufferedSocket()
    await hub.connect(socket, {"type": "snapshot"})
    try:
        await asyncio.wait_for(socket.entered.wait(), 2)
        await hub.broadcast(
            {"type": "tool_proposal", "proposal_id": "p", "stream_id": "s"}, urgent=True
        )
        # The HTTP/manual caller has proposal identity, not controller stream identity.
        await hub.broadcast({"type": "tool_started", "proposal_id": "p"}, urgent=True)
        await hub.broadcast({"type": "tool_result", "proposal_id": "p"}, urgent=True)
        await hub.broadcast({"type": "assistant_terminal", "stream_id": "s"})
        await hub.broadcast({"type": "tool_result", "stream_id": "s"})
        await hub.broadcast({"type": "barrier"})
        socket.release.set()
        await asyncio.wait_for(socket.drained.wait(), 2)
        tool_events = [event for event in socket.messages if str(event["type"]).startswith("tool_")]
        assert len(tool_events) == 3
        assert all(event["stream_id"] == "s" for event in tool_events)
    finally:
        socket.release.set()
        await hub.shutdown()


@pytest.mark.asyncio
async def test_real_controller_cancel_fences_buffered_tool_batch(tmp_path: Path) -> None:
    from collections.abc import AsyncIterator

    from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
    from siro.persistence.sqlite import SQLiteStore
    from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
    from siro.services.presentation.gateway import GatewayHub
    from siro.services.presentation.integrated import IntegratedCompanion
    from siro.services.tools.execution import ExecutionContext
    from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

    class Model:
        name = "buffered-batch"

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            for index in range(10):
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall(str(index), "computer.execute", {"index": index}),
                )
            yield ModelChunk("finished")

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    entered = asyncio.Event()

    async def old(arguments: dict[str, object]) -> object:
        raise AssertionError("legacy bypass")

    async def execute(arguments: dict[str, object], context: ExecutionContext) -> object:
        if arguments["index"] == 9:
            entered.set()
            await context.cancellation.wait()
            context.check()
        return arguments

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store),
        {"computer.execute": old},
        contextual_executors={"computer.execute": execute},
    )
    hub = GatewayHub()
    socket = BufferedSocket()
    await hub.connect(socket, {"type": "snapshot"})
    await asyncio.wait_for(socket.entered.wait(), 2)
    controller = IntegratedCompanion(
        tmp_path,
        Model(),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    await controller._ensure_core()
    task = asyncio.create_task(controller.respond("session", "synthetic goal"))
    try:
        await asyncio.wait_for(entered.wait(), 10)
        await asyncio.wait_for(controller.cancel("active", "stop"), 2)
        await asyncio.wait_for(task, 2)
        await hub.broadcast({"type": "barrier"})
        socket.release.set()
        await asyncio.wait_for(socket.drained.wait(), 2)
        terminal = next(
            i for i, event in enumerate(socket.messages) if event["type"] == "assistant_terminal"
        )
        ended = socket.messages[terminal]["stream_id"]
        assert not any(event.get("stream_id") == ended for event in socket.messages[terminal + 1 :])
        assert not controller._event_streams
    finally:
        socket.release.set()
        if not task.done():
            await controller.cancel("active", "cleanup")
            await task
        await hub.shutdown()
