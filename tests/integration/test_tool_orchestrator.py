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


@pytest.mark.asyncio
async def test_candidate_insert_binding_is_atomic_and_public_id_is_preserved(
    tmp_path: Path,
) -> None:
    from siro.ports.models import ModelMessage
    from siro.services.agent.runs import SQLiteAgentRunRepository

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    runs = SQLiteAgentRunRepository(store)
    run = await runs.start("atomic", "goal", runtime_backend="test")
    call = ToolCall("call-0", "computer", {"index": 1})
    await runs.checkpoint(run.run_id, [ModelMessage("assistant", "", (call,))])

    async def execute(arguments: dict[str, object]) -> object:
        return arguments

    repository = SQLiteToolProposalRepository(store)
    subject = ToolOrchestrator(repository, {"computer": execute})
    subject.start_run(run.run_id, "atomic")
    # Force failure after INSERT but before binding commit: transaction must leave neither half.
    await store.run_transaction(
        lambda c: c.execute(
            "CREATE TRIGGER fail_binding BEFORE UPDATE OF proposal_id ON run_journal_calls "
            "BEGIN SELECT RAISE(ABORT, 'injected binding failure'); END"
        )
    )
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        await subject.propose("atomic", call, risk="computer", run_id=run.run_id)
    assert (
        await store.run_transaction(
            lambda c: c.execute("SELECT COUNT(*) FROM tool_proposals").fetchone()[0]
        )
        == 0
    )
    assert (
        await store.run_transaction(
            lambda c: c.execute("SELECT proposal_id FROM run_journal_calls").fetchone()[0]
        )
        is None
    )
    await store.run_transaction(lambda c: c.execute("DROP TRIGGER fail_binding"))
    proposal = await subject.propose("atomic", call, risk="computer", run_id=run.run_id)
    loaded = await repository.get(proposal.proposal_id)
    assert loaded == proposal and loaded.call_id == "call-0"
    assert await repository.journal_owner(loaded) == run.run_id
    raw = await store.run_transaction(
        lambda c: c.execute("SELECT call_id FROM tool_proposals").fetchone()[0]
    )
    assert raw == proposal.proposal_id and raw != "call-0"
    # Rebinding a provider call to another proposal must not replace ownership.
    await runs.bind_call(run.run_id, "call-0", "not-the-owner")
    assert (
        await store.run_transaction(
            lambda c: c.execute("SELECT proposal_id FROM run_journal_calls").fetchone()[0]
        )
        == proposal.proposal_id
    )


@pytest.mark.asyncio
async def test_ambiguous_historical_unbound_owner_fails_closed(tmp_path: Path) -> None:
    from siro.ports.models import ModelMessage
    from siro.services.agent.runs import SQLiteAgentRunRepository

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    runs = SQLiteAgentRunRepository(store)
    call = ToolCall("legacy-gap", "computer", {})
    for _ in range(2):
        run = await runs.start("ambiguous", "goal", runtime_backend="test")
        await runs.checkpoint(run.run_id, [ModelMessage("assistant", "", (call,))])

    async def forbidden(arguments: dict[str, object]) -> object:
        raise AssertionError("ambiguous owner dispatched")

    subject = ToolOrchestrator(SQLiteToolProposalRepository(store), {"computer": forbidden})
    proposal = await subject.propose("ambiguous", call, risk="computer")
    await subject.resolve(proposal.proposal_id, approved=True, arguments={})
    with pytest.raises(ValueError, match="ambiguous"):
        await subject.execute(proposal.proposal_id)
