from pathlib import Path
from collections.abc import AsyncIterator
import pytest
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

class ReusedCallModel:
    name = "independent-synthetic"
    def __init__(self):
        self.count = 0
    async def stream(self, request: ModelRequest, cancellation: CancellationToken) -> AsyncIterator[ModelChunk]:
        self.count += 1
        if self.count % 2:
            yield ModelChunk("tool_request", tool_call=ToolCall("same-call", "computer.execute", {}))
        else:
            yield ModelChunk("text", "done")
        yield ModelChunk("finished")

@pytest.mark.asyncio
async def test_separate_runs_may_reuse_provider_call_id(tmp_path: Path):
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    effects = []
    async def effect(arguments):
        effects.append("once")
        return {"ok": True}
    controller = IntegratedCompanion(tmp_path, ReusedCallModel(), GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()), privacy=Privacy.LOCAL_ONLY,
        runtime_profile="candidate", auto_authorize=lambda: True,
        tool_orchestrator=ToolOrchestrator(SQLiteToolProposalRepository(store), {"computer.execute": effect}))
    await controller.respond("same-session", "first goal")
    first = await controller._agent_runs.latest("same-session")
    assert first.state.value == "completed"
    await controller.respond("same-session", "second goal")
    second = await controller._agent_runs.latest("same-session")
    assert second.state.value == "completed"
    assert effects == ["once", "once"]
