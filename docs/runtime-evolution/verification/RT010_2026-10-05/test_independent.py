from pathlib import Path
import pytest
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelChunk, Privacy
from siro.services.agent.runs import AgentRunState, SQLiteAgentRunRepository
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion

@pytest.mark.asyncio
async def test_corrupt_hydration_blocks_provider_and_new_run(tmp_path: Path):
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repository = SQLiteAgentRunRepository(store)
    run = await repository.start("A", "old goal", runtime_backend="synthetic")
    await repository.append(run.run_id, "final", {}, state=AgentRunState.COMPLETED)
    await store.run_transaction(lambda c: c.execute(
        "UPDATE run_journal SET status='terminal',messages_json='{}' WHERE run_id=?", (run.run_id,)))
    calls = []
    class Model:
        name = "forbidden-on-corruption"
        async def stream(self, request, cancellation):
            calls.append(request)
            raise AssertionError("provider reached after corrupt hydration")
            yield ModelChunk("finished")
    controller = IntegratedCompanion(tmp_path, Model(), GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY, runtime_profile="candidate")
    with pytest.raises(ValueError, match="invalid canonical session dialogue"):
        await controller.respond("A", "new goal")
    count = await store.run_transaction(lambda c: c.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0])
    assert count == 1 and not calls
    assert not controller._active_sessions
