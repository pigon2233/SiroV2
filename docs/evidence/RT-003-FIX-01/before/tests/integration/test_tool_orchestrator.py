from pathlib import Path

import pytest

from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ToolCall
from siro.services.tools.orchestrator import (
    ProposalState,
    SQLiteToolProposalRepository,
    ToolOrchestrator,
)


@pytest.mark.asyncio
async def test_persistent_argument_bound_tool_lifecycle(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    calls: list[dict[str, object]] = []

    async def execute(arguments: dict[str, object]) -> object:
        calls.append(arguments)
        return {"installed": True, "version": "1.2.3"}

    repository = SQLiteToolProposalRepository(store)
    subject = ToolOrchestrator(repository, {"computer": execute})
    proposal = await subject.propose(
        "browser",
        ToolCall("call-1", "computer", {"goal": "install and open VS Code"}),
        risk="normal",
    )
    assert proposal.state is ProposalState.PENDING
    assert calls == []

    # A new repository instance proves the proposal survives process-local state.
    reloaded = SQLiteToolProposalRepository(store)
    persisted = await reloaded.get(proposal.proposal_id)
    assert persisted == proposal

    with pytest.raises(PermissionError, match="arguments changed"):
        await subject.resolve(
            proposal.proposal_id,
            approved=True,
            arguments={"goal": "run arbitrary shell command"},
        )
    assert calls == []

    approved = await subject.resolve(
        proposal.proposal_id,
        approved=True,
        arguments=proposal.arguments,
    )
    assert approved.state is ProposalState.APPROVED
    completed = await subject.execute(proposal.proposal_id)
    assert completed.state is ProposalState.COMPLETED
    assert completed.observation == {"installed": True, "version": "1.2.3"}
    assert calls == [{"goal": "install and open VS Code"}]


@pytest.mark.asyncio
async def test_denied_and_failed_proposals_are_terminal(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()

    async def fail(_arguments: dict[str, object]) -> object:
        raise RuntimeError("boom")

    subject = ToolOrchestrator(SQLiteToolProposalRepository(store), {"computer": fail})
    denied = await subject.propose(
        "browser", ToolCall("deny", "computer", {"goal": "x"}), risk="normal"
    )
    result = await subject.resolve(denied.proposal_id, approved=False, arguments=denied.arguments)
    assert result.state is ProposalState.DENIED

    failing = await subject.propose(
        "browser", ToolCall("fail", "computer", {"goal": "y"}), risk="normal"
    )
    await subject.resolve(failing.proposal_id, approved=True, arguments=failing.arguments)
    failed = await subject.execute(failing.proposal_id)
    assert failed.state is ProposalState.FAILED
    assert failed.error == "RuntimeError"
