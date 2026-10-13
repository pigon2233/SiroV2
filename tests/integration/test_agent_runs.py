from pathlib import Path

import pytest

from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.runs import AgentRunState, SQLiteAgentRunRepository


@pytest.mark.asyncio
async def test_agent_run_persists_goal_steps_and_observations(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repository = SQLiteAgentRunRepository(store)
    run = await repository.start("browser", "download, install, and open VS Code")
    waiting = await repository.append(
        run.run_id,
        "tool_call",
        {"argv": ["curl", "https://example.test/code.deb"]},
        capability="computer.execute",
        state=AgentRunState.WAITING_TOOL,
        proposal_id="proposal-1",
    )
    assert waiting.current_proposal_id == "proposal-1"
    running = await repository.append(
        run.run_id,
        "observation",
        {"returncode": 0},
        capability="computer.execute",
        state=AgentRunState.RUNNING,
    )
    completed = await repository.append(
        run.run_id,
        "final",
        {"text": "done"},
        state=AgentRunState.COMPLETED,
    )

    reloaded = SQLiteAgentRunRepository(store)
    assert await reloaded.latest("browser") == completed
    assert running.step_count == 2
    steps = await reloaded.steps(run.run_id)
    assert [step.kind for step in steps] == ["tool_call", "observation", "final"]
    with pytest.raises(ValueError, match="terminal"):
        await reloaded.append(run.run_id, "observation", {})
