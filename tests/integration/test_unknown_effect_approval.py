from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
    ToolDefinition,
)
from siro.services.agent.runs import AgentRunState, SQLiteAgentRunRepository
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import (
    DEFAULT_MODEL_TOOLS,
    ProposalState,
    SQLiteToolProposalRepository,
    ToolCatalog,
    ToolDescriptor,
    ToolOrchestrator,
    ToolProposal,
)

ARGS: dict[str, object] = {"argv": ["synthetic-operation"]}


@dataclass
class Fixture:
    store: SQLiteStore
    runs: SQLiteAgentRunRepository
    proposals: SQLiteToolProposalRepository
    orchestrator: ToolOrchestrator
    effects: list[dict[str, object]]


async def fixture_at(tmp_path: Path, *, effects: dict[str, str] | None = None) -> Fixture:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    recorded: list[dict[str, object]] = []

    async def execute(arguments: dict[str, object]) -> object:
        recorded.append(arguments.copy())
        return {"confirmed": True}

    names = ("computer.execute", "other.effect", "browser.read")
    catalog = None
    if effects is not None:
        catalog = ToolCatalog(
            tuple(
                ToolDescriptor(
                    name,
                    DEFAULT_MODEL_TOOLS[1]
                    if name == "computer.execute"
                    else ToolDefinition(name, "Synthetic fixture", {"type": "object"}),
                    execute,
                    lambda: True,
                    "synthetic-counter",
                    effects.get(name, "computer"),
                )
                for name in names
            )
        )
    proposals = SQLiteToolProposalRepository(store)
    return Fixture(
        store,
        SQLiteAgentRunRepository(store),
        proposals,
        ToolOrchestrator(proposals, dict.fromkeys(names, execute), catalog=catalog),
        recorded,
    )


async def prior_call(
    fixture: Fixture,
    *,
    session: str = "owner-session",
    capability: str = "computer.execute",
    arguments: dict[str, object] | None = None,
    dispatched: bool = True,
    observation: object | None = None,
    fenced: bool = True,
    interrupted: bool = False,
    state: AgentRunState = AgentRunState.FAILED,
    privacy: str = "local_only",
    binding: Literal["linked", "null", "orphan", "cross_session", "wrong_capability"] = "linked",
) -> tuple[str, ToolProposal | None]:
    run = await fixture.runs.start(
        session,
        "SECRET-PRIOR-GOAL",
        runtime_backend="synthetic",
        privacy=privacy,
    )
    await fixture.runs.reserve_round(run.run_id)
    call = ToolCall(str(uuid4()), capability, (ARGS if arguments is None else arguments).copy())
    await fixture.runs.checkpoint(
        run.run_id,
        [
            ModelMessage("system", "SECRET-PRIOR-PROMPT"),
            ModelMessage("user", run.goal),
            ModelMessage("assistant", tool_calls=(call,)),
        ],
    )
    proposal = None
    if binding != "null":
        fixture.orchestrator.start_run(run.run_id, session)
        proposal = await fixture.orchestrator.propose(
            session, call, risk="computer", run_id=run.run_id
        )
        fixture.orchestrator.bind_proposal(run.run_id, proposal)
        if binding == "orphan":
            await fixture.store.run_transaction(
                lambda c: c.execute(
                    "UPDATE run_journal_calls SET proposal_id=? WHERE run_id=?",
                    (str(uuid4()), run.run_id),
                )
            )
        elif binding == "cross_session":
            await fixture.store.run_transaction(
                lambda c: c.execute(
                    "UPDATE tool_proposals SET session_id='another-owner-session' "
                    "WHERE proposal_id=?",
                    (proposal.proposal_id,),
                )
            )
        elif binding == "wrong_capability":
            await fixture.store.run_transaction(
                lambda c: c.execute(
                    "UPDATE tool_proposals SET capability='other.effect' WHERE proposal_id=?",
                    (proposal.proposal_id,),
                )
            )
    if dispatched:
        await fixture.runs.record_dispatch(run.run_id, call.call_id)
    if observation is not None:
        await fixture.runs.record_observation(run.run_id, call.call_id, observation)
    if fenced:
        await fixture.runs.finish_journal(run.run_id, interrupted=interrupted)
        await fixture.runs.append(
            run.run_id,
            "final",
            {"text": "SECRET-PRIOR-FINAL"},
            state=state,
            error="outcome_unknown",
        )
    return run.run_id, proposal


async def fresh_proposal(
    fixture: Fixture,
    *,
    session: str = "owner-session",
    capability: str = "computer.execute",
    arguments: dict[str, object] | None = None,
    risk: str = "computer",
) -> ToolProposal:
    return await fixture.orchestrator.propose(
        session,
        ToolCall(str(uuid4()), capability, (ARGS if arguments is None else arguments).copy()),
        risk=risk,
    )


async def assert_automatic_hold(fixture: Fixture, proposal: ToolProposal) -> None:
    before = await fixture.store.run_transaction(lambda c: tuple(c.iterdump()))
    with pytest.raises(PermissionError) as raised:
        await fixture.orchestrator.resolve(
            proposal.proposal_id,
            approved=True,
            arguments=proposal.arguments,
            automatic=True,
        )
    assert type(raised.value).__name__ == "PriorOutcomeUnknown"
    assert "SECRET" not in str(raised.value)
    actual = await fixture.orchestrator.get(proposal.proposal_id)
    assert actual is not None and actual.state is ProposalState.PENDING
    assert await fixture.store.run_transaction(lambda c: tuple(c.iterdump())) == before
    assert fixture.effects == []


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupted", [False, True])
@pytest.mark.parametrize(
    "state", [AgentRunState.FAILED, AgentRunState.CANCELLED, AgentRunState.COMPLETED]
)
async def test_fenced_unknown_same_content_holds_new_uuid(
    tmp_path: Path, interrupted: bool, state: AgentRunState
) -> None:
    fixture = await fixture_at(tmp_path)
    _, old = await prior_call(fixture, interrupted=interrupted, state=state)
    proposal = await fresh_proposal(fixture)
    assert old is not None and proposal.proposal_id != old.proposal_id
    assert proposal.arguments_hash == old.arguments_hash
    await assert_automatic_hold(fixture, proposal)


@pytest.mark.asyncio
@pytest.mark.parametrize("binding", ["null", "orphan", "cross_session", "wrong_capability"])
async def test_unverifiable_binding_conservatively_holds_same_capability(
    tmp_path: Path,
    binding: Literal["linked", "null", "orphan", "cross_session", "wrong_capability"],
) -> None:
    fixture = await fixture_at(tmp_path)
    await prior_call(fixture, binding=binding)
    proposal = await fresh_proposal(fixture, arguments={"argv": ["different-synthetic-operation"]})
    await assert_automatic_hold(fixture, proposal)


@pytest.mark.asyncio
@pytest.mark.parametrize("fresh_matches_old", [True, False])
async def test_same_owner_capability_but_mismatched_bound_payload_requires_confirmation(
    tmp_path: Path, fresh_matches_old: bool
) -> None:
    fixture = await fixture_at(tmp_path)
    run_id, old = await prior_call(fixture)
    assert old is not None
    wrong = await fresh_proposal(fixture, arguments={"argv": ["different-bound-payload"]})
    await fixture.store.run_transaction(
        lambda c: c.execute(
            "UPDATE run_journal_calls SET proposal_id=? WHERE run_id=?",
            (wrong.proposal_id, run_id),
        )
    )
    fresh = await fresh_proposal(
        fixture, arguments=None if fresh_matches_old else {"argv": ["third-operation"]}
    )
    assert fresh.arguments_hash != wrong.arguments_hash
    if fresh_matches_old:
        assert fresh.arguments_hash == old.arguments_hash
    await assert_automatic_hold(fixture, fresh)


@pytest.mark.asyncio
async def test_structurally_equal_nested_json_and_unicode_do_not_hold_unrelated_call(
    tmp_path: Path,
) -> None:
    fixture = await fixture_at(tmp_path)
    # Checkpoint uses the model's key order and UTF-8; proposal storage sorts keys
    # and escapes Unicode. A byte comparison would misclassify this valid binding.
    original: dict[str, object] = {
        "z": {"nested": [{"界": "合成", "a": True}, None, 1.5]},
        "argv": ["synthetic-operation"],
        "a": {"second": [], "first": {}},
    }
    run_id, old = await prior_call(fixture, arguments=original)
    assert old is not None
    row = await fixture.store.run_transaction(
        lambda c: c.execute(
            "SELECT p.arguments_json AS proposal_json,c.arguments_json AS call_json "
            "FROM run_journal_calls c JOIN tool_proposals p ON p.proposal_id=c.proposal_id "
            "WHERE c.run_id=?",
            (run_id,),
        ).fetchone()
    )
    assert row is not None and row["proposal_json"] != row["call_json"]
    fresh = await fresh_proposal(fixture)
    assert fresh.arguments_hash != old.arguments_hash
    approved = await fixture.orchestrator.resolve(
        fresh.proposal_id, approved=True, arguments=fresh.arguments, automatic=True
    )
    assert approved.state is ProposalState.APPROVED
    assert fixture.effects == []


@pytest.mark.asyncio
async def test_sqlite_large_integer_atom_collision_does_not_validate_wrong_binding(
    tmp_path: Path,
) -> None:
    fixture = await fixture_at(tmp_path)
    original: dict[str, object] = {"argv": ["synthetic-operation"], "count": 2**80}
    run_id, old = await prior_call(fixture, arguments=original)
    assert old is not None
    wrong = await fresh_proposal(
        fixture, arguments={"argv": ["synthetic-operation"], "count": 2**80 + 1}
    )
    assert wrong.arguments_hash != old.arguments_hash
    await fixture.store.run_transaction(
        lambda c: c.execute(
            "UPDATE run_journal_calls SET proposal_id=? WHERE run_id=?",
            (wrong.proposal_id, run_id),
        )
    )
    row = await fixture.store.run_transaction(
        lambda c: c.execute(
            "SELECT (SELECT atom FROM json_tree(c.arguments_json) WHERE fullkey='$.count') "
            "AS call_atom,(SELECT atom FROM json_tree(p.arguments_json) "
            "WHERE fullkey='$.count') AS proposal_atom "
            "FROM run_journal_calls c JOIN tool_proposals p ON p.proposal_id=c.proposal_id "
            "WHERE c.run_id=?",
            (run_id,),
        ).fetchone()
    )
    assert row is not None and row["call_atom"] == row["proposal_atom"]
    await assert_automatic_hold(fixture, await fresh_proposal(fixture, arguments=original))


@pytest.mark.asyncio
async def test_unextractable_numeric_key_does_not_validate_wrong_binding(tmp_path: Path) -> None:
    fixture = await fixture_at(tmp_path)
    original: dict[str, object] = {"argv": ["synthetic-operation"], 'quote"key': 2**80}
    run_id, old = await prior_call(fixture, arguments=original)
    assert old is not None
    wrong = await fresh_proposal(
        fixture, arguments={"argv": ["synthetic-operation"], 'quote"key': 2**80 + 1}
    )
    assert wrong.arguments_hash != old.arguments_hash
    await fixture.store.run_transaction(
        lambda c: c.execute(
            "UPDATE run_journal_calls SET proposal_id=? WHERE run_id=?",
            (wrong.proposal_id, run_id),
        )
    )
    row = await fixture.store.run_transaction(
        lambda c: c.execute(
            "SELECT (SELECT c.arguments_json -> fullkey FROM json_tree(c.arguments_json) "
            "WHERE type='integer') AS call_lexeme, "
            "(SELECT p.arguments_json -> fullkey FROM json_tree(p.arguments_json) "
            "WHERE type='integer') AS proposal_lexeme "
            "FROM run_journal_calls c JOIN tool_proposals p ON p.proposal_id=c.proposal_id "
            "WHERE c.run_id=?",
            (run_id,),
        ).fetchone()
    )
    assert row is not None and row["call_lexeme"] is None and row["proposal_lexeme"] is None
    await assert_automatic_hold(fixture, await fresh_proposal(fixture, arguments=original))


@pytest.mark.asyncio
async def test_duplicate_object_keys_are_not_a_verified_binding(tmp_path: Path) -> None:
    fixture = await fixture_at(tmp_path)
    run_id, _ = await prior_call(fixture)
    # SQLite accepts this JSON and a set of tree rows hides the duplicate. The
    # final effective value also matches the proposal, so refuse the ambiguity.
    duplicate = '{"argv":["synthetic-operation"],"argv":["synthetic-operation"]}'
    await fixture.store.run_transaction(
        lambda c: c.execute(
            "UPDATE run_journal_calls SET arguments_json=? WHERE run_id=?", (duplicate, run_id)
        )
    )
    assert await fixture.store.run_transaction(
        lambda c: c.execute("SELECT json_valid(?)", (duplicate,)).fetchone()[0]
    )
    fresh = await fresh_proposal(fixture, arguments={"argv": ["different-new-operation"]})
    await assert_automatic_hold(fixture, fresh)


@pytest.mark.asyncio
@pytest.mark.parametrize("column_owner", ["call", "proposal"])
@pytest.mark.parametrize("malformed", [False, True])
async def test_oversized_or_invalid_bound_arguments_fail_closed(
    tmp_path: Path, column_owner: str, malformed: bool
) -> None:
    fixture = await fixture_at(tmp_path)
    run_id, old = await prior_call(fixture)
    assert old is not None
    raw = "synthetic-invalid-json" if malformed else '{"payload":"' + "界" * 22_000 + '"}'
    if not malformed:
        assert len(raw) < 65_536 < len(raw.encode())

    def corrupt_temporary_arguments(connection: object) -> None:
        import sqlite3

        assert isinstance(connection, sqlite3.Connection)
        # Only a diagnostic temporary DB can contain invalid checkpoint JSON.
        connection.execute("PRAGMA ignore_check_constraints=ON")
        try:
            if column_owner == "call":
                connection.execute(
                    "UPDATE run_journal_calls SET arguments_json=? WHERE run_id=?", (raw, run_id)
                )
            else:
                connection.execute(
                    "UPDATE tool_proposals SET arguments_json=? WHERE proposal_id=?",
                    (raw, old.proposal_id),
                )
        finally:
            connection.execute("PRAGMA ignore_check_constraints=OFF")

    await fixture.store.run_transaction(corrupt_temporary_arguments)
    # An unverifiable old payload must not be treated as a valid different hash.
    fresh = await fresh_proposal(fixture, arguments={"argv": ["unrelated-new-operation"]})
    await assert_automatic_hold(fixture, fresh)


@pytest.mark.asyncio
@pytest.mark.parametrize("difference", ["arguments", "session", "capability"])
async def test_verified_binding_does_not_block_unrelated_new_call(
    tmp_path: Path, difference: str
) -> None:
    fixture = await fixture_at(tmp_path)
    await prior_call(fixture)
    proposal = await fresh_proposal(
        fixture,
        arguments={"argv": ["different-operation"]} if difference == "arguments" else None,
        session="different-session" if difference == "session" else "owner-session",
        capability="other.effect" if difference == "capability" else "computer.execute",
    )
    approved = await fixture.orchestrator.resolve(
        proposal.proposal_id, approved=True, arguments=proposal.arguments, automatic=True
    )
    assert approved.state is ProposalState.APPROVED
    assert fixture.effects == []


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["known_success", "known_failure", "not_dispatched", "active"])
async def test_guard_requires_fenced_dispatched_unknown(tmp_path: Path, case: str) -> None:
    fixture = await fixture_at(tmp_path)
    await prior_call(
        fixture,
        dispatched=case != "not_dispatched",
        observation={"confirmed": True}
        if case == "known_success"
        else ({"error": "ValueError"} if case == "known_failure" else {"error": "outcome_unknown"}),
        fenced=case != "active",
    )
    proposal = await fresh_proposal(fixture)
    approved = await fixture.orchestrator.resolve(
        proposal.proposal_id, approved=True, arguments=proposal.arguments, automatic=True
    )
    assert approved.state is ProposalState.APPROVED


@pytest.mark.asyncio
@pytest.mark.parametrize("receipt", [None, "synthetic corrupt JSON"])
async def test_fenced_dispatch_without_parseable_receipt_holds(
    tmp_path: Path, receipt: str | None
) -> None:
    fixture = await fixture_at(tmp_path)
    run_id, _ = await prior_call(fixture)

    def corrupt_temporary_fixture(connection: object) -> None:
        # Corruption recovery only: production's JSON CHECK remains unchanged.
        # A fresh connection cannot retain this fixture-only SQLite setting.
        import sqlite3

        assert isinstance(connection, sqlite3.Connection)
        connection.execute("PRAGMA ignore_check_constraints=ON")
        try:
            connection.execute(
                "UPDATE run_journal_calls SET observation_json=? WHERE run_id=?",
                (receipt, run_id),
            )
        finally:
            connection.execute("PRAGMA ignore_check_constraints=OFF")

    await fixture.store.run_transaction(corrupt_temporary_fixture)
    await assert_automatic_hold(fixture, await fresh_proposal(fixture))


@pytest.mark.asyncio
async def test_unknown_effect_does_not_expire_or_depend_on_model_privacy_route(
    tmp_path: Path,
) -> None:
    fixture = await fixture_at(tmp_path)
    run_id, _ = await prior_call(fixture, privacy="cloud_allowed")
    await fixture.store.run_transaction(
        lambda c: c.execute(
            "UPDATE agent_runs SET created_at='2000-01-01T00:00:00+00:00', "
            "updated_at='2000-01-01T00:00:00+00:00' WHERE run_id=?",
            (run_id,),
        )
    )
    await assert_automatic_hold(fixture, await fresh_proposal(fixture))


@pytest.mark.asyncio
async def test_repository_transition_cannot_bypass_automatic_guard(tmp_path: Path) -> None:
    fixture = await fixture_at(tmp_path)
    await prior_call(fixture)
    proposal = await fresh_proposal(fixture)
    with pytest.raises(PermissionError) as raised:
        await fixture.proposals.transition(
            proposal.proposal_id, ProposalState.PENDING, ProposalState.APPROVED, automatic=True
        )
    assert type(raised.value).__name__ == "PriorOutcomeUnknown"
    actual = await fixture.proposals.get(proposal.proposal_id)
    assert actual is not None and actual.state is ProposalState.PENDING


@pytest.mark.asyncio
async def test_manual_default_remains_hash_bound_and_executes_only_once(tmp_path: Path) -> None:
    fixture = await fixture_at(tmp_path)
    await prior_call(fixture)
    proposal = await fresh_proposal(fixture)
    await assert_automatic_hold(fixture, proposal)
    with pytest.raises(PermissionError):
        await fixture.orchestrator.resolve(
            proposal.proposal_id, approved=True, arguments={"argv": ["changed"]}
        )
    pending = await fixture.orchestrator.get(proposal.proposal_id)
    assert pending is not None and pending.state is ProposalState.PENDING
    await fixture.orchestrator.resolve(
        proposal.proposal_id, approved=True, arguments=proposal.arguments
    )
    completed = await fixture.orchestrator.execute(proposal.proposal_id)
    assert completed.state is ProposalState.COMPLETED
    with pytest.raises(ValueError):
        await fixture.orchestrator.execute(proposal.proposal_id)
    assert fixture.effects == [ARGS]


@pytest.mark.asyncio
async def test_denial_ignores_automatic_hold_and_does_not_dispatch(tmp_path: Path) -> None:
    fixture = await fixture_at(tmp_path)
    await prior_call(fixture)
    proposal = await fresh_proposal(fixture)
    denied = await fixture.orchestrator.resolve(
        proposal.proposal_id, approved=False, arguments=proposal.arguments, automatic=True
    )
    assert denied.state is ProposalState.DENIED
    assert fixture.effects == []


@pytest.mark.asyncio
@pytest.mark.parametrize("catalog_effect", [None, "computer", "unknown"])
async def test_untrusted_read_only_risk_does_not_exempt_effectful_call(
    tmp_path: Path, catalog_effect: str | None
) -> None:
    fixture = await fixture_at(
        tmp_path, effects=None if catalog_effect is None else {"computer.execute": catalog_effect}
    )
    await prior_call(fixture)
    proposal = await fresh_proposal(fixture, risk="observe/read-only")
    await assert_automatic_hold(fixture, proposal)


@pytest.mark.asyncio
async def test_trusted_read_descriptor_can_repeat_readback(tmp_path: Path) -> None:
    fixture = await fixture_at(tmp_path, effects={"browser.read": "read"})
    await prior_call(fixture, capability="browser.read", arguments={})
    proposal = await fresh_proposal(fixture, capability="browser.read", arguments={})
    approved = await fixture.orchestrator.resolve(
        proposal.proposal_id, approved=True, arguments=proposal.arguments, automatic=True
    )
    assert approved.state is ProposalState.APPROVED
    assert fixture.effects == []


@pytest.mark.asyncio
async def test_stale_pending_and_simultaneous_approvals_keep_compare_and_set(
    tmp_path: Path,
) -> None:
    fixture = await fixture_at(tmp_path)
    proposal = await fresh_proposal(fixture)
    results = await asyncio.gather(
        *(
            fixture.orchestrator.resolve(
                proposal.proposal_id, approved=True, arguments=proposal.arguments, automatic=True
            )
            for _ in range(2)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(result, ToolProposal) for result in results) == 1
    assert sum(isinstance(result, ValueError) for result in results) == 1
    await prior_call(fixture)
    with pytest.raises(ValueError):
        await fixture.orchestrator.resolve(
            proposal.proposal_id, approved=True, arguments=proposal.arguments, automatic=True
        )
    assert fixture.effects == []


@pytest.mark.asyncio
async def test_fence_committed_before_approval_transaction_is_seen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = await fixture_at(tmp_path)
    run_id, _ = await prior_call(fixture, fenced=False)
    proposal = await fresh_proposal(fixture)
    entered, proceed = asyncio.Event(), asyncio.Event()
    original = fixture.proposals.transition

    async def paused_transition(
        proposal_id: str,
        expected: ProposalState,
        target: ProposalState,
        *,
        observation: object | None = None,
        error: str | None = None,
        automatic: bool = False,
    ) -> ToolProposal:
        entered.set()
        await proceed.wait()
        return await original(
            proposal_id,
            expected,
            target,
            observation=observation,
            error=error,
            automatic=automatic,
        )

    monkeypatch.setattr(fixture.proposals, "transition", paused_transition)
    task = asyncio.create_task(
        fixture.orchestrator.resolve(
            proposal.proposal_id, approved=True, arguments=proposal.arguments, automatic=True
        )
    )
    ready = asyncio.create_task(entered.wait())
    try:
        done, _ = await asyncio.wait({task, ready}, timeout=2, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            await task
            pytest.fail("approval bypassed its transaction")
        assert ready in done, "approval did not reach the fixture barrier"
        await fixture.runs.finish_journal(run_id)
        await fixture.runs.append(
            run_id, "final", {}, state=AgentRunState.FAILED, error="outcome_unknown"
        )
        proceed.set()
        with pytest.raises(PermissionError) as raised:
            await asyncio.wait_for(task, 2)
        assert type(raised.value).__name__ == "PriorOutcomeUnknown"
        assert fixture.effects == []
    finally:
        proceed.set()
        ready.cancel()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, ready, return_exceptions=True)


class CounterModel:
    name = "synthetic-unknown-effect"

    def __init__(self, calls: tuple[ToolCall, ...]) -> None:
        self.calls = calls
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        if len(self.requests) == 1:
            for call in self.calls:
                yield ModelChunk("tool_request", tool_call=call)
        else:
            yield ModelChunk("text", "Synthetic observed completion")
        yield ModelChunk("finished")


class RecordingHub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    async def broadcast(self, payload: dict[str, object], *, urgent: bool = False) -> None:
        self.events.append(payload)


async def controller_at(
    tmp_path: Path, *, batch: bool = False
) -> tuple[Fixture, IntegratedCompanion, CounterModel, RecordingHub]:
    fixture = await fixture_at(tmp_path)
    calls: tuple[ToolCall, ...] = (ToolCall("fresh-held", "computer.execute", ARGS.copy()),)
    if batch:
        calls += (ToolCall("fresh-normal", "computer.execute", {"argv": ["new-operation"]}),)
    model, hub = CounterModel(calls), RecordingHub()
    controller = IntegratedCompanion(
        tmp_path,
        model,
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=fixture.orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    await controller.startup()
    await prior_call(fixture)
    return fixture, controller, model, hub


def held_event(hub: RecordingHub) -> dict[str, object]:
    proposals = [event for event in hub.events if event["type"] == "tool_proposal"]
    held = [event for event in proposals if event["call_id"] == "fresh-held"]
    assert len(held) == 1
    assert held[0]["automatic_approval_blocked"] == "prior_outcome_unknown"
    assert held[0]["status"] == "pending"
    assert not any(
        event["type"] in {"tool_started", "tool_result"} and event.get("call_id") == "fresh-held"
        for event in hub.events
    )
    return held[0]


@pytest.mark.asyncio
async def test_full_mode_fresh_identical_call_waits_for_owner_without_effects(
    tmp_path: Path,
) -> None:
    fixture, controller, model, hub = await controller_at(tmp_path)
    await controller.respond("owner-session", "Please repeat the operation")
    event = held_event(hub)
    assert fixture.effects == []
    assert len(model.requests) == 1
    assert not any(event["type"] == "assistant_terminal" for event in hub.events)
    assert "SECRET-PRIOR" not in model.requests[0].prompt
    proposal = await fixture.orchestrator.get(str(event["proposal_id"]))
    assert proposal is not None and proposal.state is ProposalState.PENDING
    await controller.cancel("active", "fixture cleanup", session_id="owner-session")


@pytest.mark.asyncio
async def test_held_call_manual_approval_completes_once(tmp_path: Path) -> None:
    fixture, controller, model, hub = await controller_at(tmp_path)
    await controller.respond("owner-session", "Please repeat the operation")
    event = held_event(hub)
    proposal_id = str(event["proposal_id"])
    proposal = await fixture.orchestrator.get(proposal_id)
    assert proposal is not None
    await fixture.orchestrator.resolve(proposal_id, approved=True, arguments=proposal.arguments)
    result = await fixture.orchestrator.execute(proposal_id)
    await controller.continue_after_tool(result)
    await controller.continue_after_tool(result)
    with pytest.raises(ValueError):
        await fixture.orchestrator.execute(proposal_id)
    assert fixture.effects == [ARGS]
    assert len(model.requests) == 2
    assert len([event for event in hub.events if event["type"] == "assistant_terminal"]) == 1


@pytest.mark.asyncio
async def test_held_call_denial_is_observed_without_execution(tmp_path: Path) -> None:
    fixture, controller, model, hub = await controller_at(tmp_path)
    await controller.respond("owner-session", "Please repeat the operation")
    event = held_event(hub)
    proposal_id = str(event["proposal_id"])
    denied = await fixture.orchestrator.resolve(proposal_id, approved=False, arguments=ARGS)
    await controller.continue_after_tool(denied)
    assert fixture.effects == []
    assert len(model.requests) == 2
    assert '"error": "denied"' in model.requests[-1].messages[-1].content
    assert len([event for event in hub.events if event["type"] == "assistant_terminal"]) == 1


@pytest.mark.asyncio
async def test_cancel_held_call_fences_late_manual_approval(tmp_path: Path) -> None:
    fixture, controller, model, hub = await controller_at(tmp_path)
    await controller.respond("owner-session", "Please repeat the operation")
    event = held_event(hub)
    await controller.cancel("active", "synthetic owner cancellation", session_id="owner-session")
    with pytest.raises(ValueError):
        await fixture.orchestrator.resolve(str(event["proposal_id"]), approved=True, arguments=ARGS)
    assert fixture.effects == []
    assert len(model.requests) == 1
    terminal = [event for event in hub.events if event["type"] == "assistant_terminal"]
    assert len(terminal) == 1 and terminal[0]["state"] == "cancelled"


@pytest.mark.asyncio
async def test_held_batch_allows_unrelated_call_and_resumes_after_manual_once(
    tmp_path: Path,
) -> None:
    fixture, controller, model, hub = await controller_at(tmp_path, batch=True)
    await controller.respond("owner-session", "Repeat operation and perform the new one")
    event = held_event(hub)
    assert fixture.effects == [{"argv": ["new-operation"]}]
    assert len(model.requests) == 1
    proposals = [event for event in hub.events if event["type"] == "tool_proposal"]
    assert len(proposals) == 2
    assert not any(event["type"] == "assistant_terminal" for event in hub.events)
    proposal_id = str(event["proposal_id"])
    await fixture.orchestrator.resolve(proposal_id, approved=True, arguments=ARGS)
    result = await fixture.orchestrator.execute(proposal_id)
    await controller.continue_after_tool(result)
    assert fixture.effects == [{"argv": ["new-operation"]}, ARGS]
    assert len(model.requests) == 2
    assert [message.tool_call_id for message in model.requests[-1].messages[-2:]] == [
        "fresh-held",
        "fresh-normal",
    ]
    assert len([event for event in hub.events if event["type"] == "assistant_terminal"]) == 1
