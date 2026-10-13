"""Synthetic browser failure wiring; no real provider, website, or private data."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest

import siro.adapters.browser as browser
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.core.authorization import argument_hash
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.execution import ExecutionContext
from siro.services.tools.orchestrator import (
    DEFAULT_MODEL_TOOLS,
    ProposalState,
    SQLiteToolProposalRepository,
    ToolCatalog,
    ToolDescriptor,
    ToolOrchestrator,
    ToolProposal,
)

PUBLIC_URL = "https://synthetic.invalid/public"
CANARY = "synthetic-private-error-canary:not-a-real-secret"


def _proposal(
    state: ProposalState, *, error: str | None = None, observation: object = None
) -> ToolProposal:
    arguments: dict[str, object] = {"url": PUBLIC_URL}
    return ToolProposal(
        "synthetic-proposal",
        "synthetic-session",
        "synthetic-call",
        "browser.navigate+read",
        arguments,
        argument_hash(arguments),
        "observe/read-only",
        state,
        observation,
        error,
    )


@pytest.mark.parametrize("reason", ["redirect_denied", None, CANARY])
def test_failed_model_observation_exposes_only_fixed_error_and_allowed_reason(
    reason: str | None,
) -> None:
    proposal = _proposal(
        ProposalState.FAILED,
        error="ScopeViolation",
        observation={
            "error": "forged-success",
            "reason": reason,
            "url": "https://synthetic.invalid/?query=" + CANARY,
            "message": CANARY,
            "arbitrary": {"credentials": CANARY},
        },
    )
    expected = {"error": "ScopeViolation"}
    if reason == "redirect_denied":
        expected["reason"] = reason
    result = proposal.model_observation()
    assert result == expected
    assert CANARY not in json.dumps(result)


def test_denial_does_not_reuse_failed_observation_or_claim_a_browser_failure() -> None:
    proposal = _proposal(
        ProposalState.DENIED,
        observation={"reason": "redirect_denied", "message": CANARY},
    )
    assert proposal.model_observation() == {"error": "denied"}


def test_completed_readback_retains_existing_success_and_partial_contract() -> None:
    observation = {
        "url": PUBLIC_URL,
        "title": "Synthetic source",
        "text": "Synthetic visible content",
        "screen_version": "fixture-version",
        "load_status": "partial",
        "reason": "subresource_denied",
    }
    assert _proposal(ProposalState.COMPLETED, observation=observation).model_observation() == (
        observation
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        f"[{PUBLIC_URL}]({PUBLIC_URL})",
        "file:///synthetic.txt",
        "javascript:synthetic()",
        "https:///missing-host",
        "https://",
        "",
    ],
)
async def test_malformed_url_is_rejected_before_proposal_and_zero_dispatch(
    tmp_path: Path, url: str
) -> None:
    executed: list[object] = []

    async def execute(arguments: dict[str, object]) -> object:
        executed.append(arguments)
        raise AssertionError("invalid URL reached browser execution")

    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "browser.navigate+read",
                DEFAULT_MODEL_TOOLS[0],
                execute,
                lambda: True,
                "synthetic-browser",
                "read",
            ),
        )
    )
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {}, catalog=catalog)
    with pytest.raises(ValueError, match="invalid tool arguments"):
        await orchestrator.propose(
            "synthetic-session",
            ToolCall("invalid-url", "browser.navigate+read", {"url": url}),
            risk="observe/read-only",
        )
    proposals = await store.run_transaction(
        lambda connection: connection.execute("SELECT COUNT(*) FROM tool_proposals").fetchone()[0]
    )
    assert proposals == 0
    assert executed == []
    assert catalog.require("browser.navigate+read", {"url": PUBLIC_URL}).name == (
        "browser.navigate+read"
    )


class RecordingHub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    async def broadcast(self, payload: dict[str, object], *, urgent: bool = False) -> None:
        self.events.append(payload)


class FailureModel:
    name = "synthetic-browser-failure-wiring"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        if len(self.requests) == 1:
            yield ModelChunk(
                "tool_request",
                tool_call=ToolCall("failure-call", "browser.navigate+read", {"url": PUBLIC_URL}),
            )
        else:
            yield ModelChunk("text", "Synthetic fixture received the failed observation.")
        yield ModelChunk("finished")


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["candidate", "legacy"])
@pytest.mark.parametrize(
    "reason", ["invalid_url", "main_origin_denied", "redirect_denied", "subresource_denied"]
)
async def test_typed_failure_reaches_continuation_ui_and_persistent_journal(
    tmp_path: Path, profile: str, reason: str
) -> None:
    executed: list[dict[str, object]] = []

    async def execute(arguments: dict[str, object]) -> object:
        executed.append(arguments)
        # A synthetic executor supplies the adapter's trusted failure type. It does not browse.
        raise browser.BrowserScopeViolation(browser.BrowserScopeReason(reason))

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "browser.navigate+read",
                DEFAULT_MODEL_TOOLS[0],
                execute,
                lambda: True,
                "synthetic-browser",
                "read",
            ),
        )
    )
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store),
        {"browser.navigate+read": execute},
        catalog=catalog if profile == "candidate" else None,
    )
    hub, model = RecordingHub(), FailureModel()
    controller = IntegratedCompanion(
        tmp_path,
        model,
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile=profile,
        auto_authorize=lambda: True,
    )
    await controller.respond("synthetic-session", "Read the synthetic public source.")
    assert executed == [{"url": PUBLIC_URL}]
    assert len(model.requests) == 2
    expected = {"error": "ScopeViolation", "reason": reason}
    results = [event for event in hub.events if event["type"] == "tool_result"]
    assert len(results) == 1
    assert results[0]["error"] == "ScopeViolation"
    assert results[0]["result"] == expected
    assert len([event for event in hub.events if event["type"] == "assistant_terminal"]) == 1

    persisted = await store.run_transaction(
        lambda connection: connection.execute(
            "SELECT state,error,observation_json FROM tool_proposals"
        ).fetchone()
    )
    assert persisted["state"] == "failed"
    assert persisted["error"] == "ScopeViolation"
    assert json.loads(persisted["observation_json"]) == expected

    if profile == "candidate":
        messages = model.requests[1].messages
        assert [message.role for message in messages] == ["system", "user", "assistant", "tool"]
        assert messages[2].tool_calls[0].call_id == messages[3].tool_call_id == "failure-call"
        assert json.loads(messages[3].content) == expected
        readback = await controller.recovery_readback("synthetic-session")
        assert readback is not None
        calls = cast(list[dict[str, object]], readback["calls"])
        assert len(calls) == 1 and calls[0]["dispatched"] == 1
        assert json.loads(str(calls[0]["observation_json"])) == expected
    else:
        assert model.requests[1].messages == ()
        assert "ScopeViolation" in model.requests[1].prompt
        assert reason in model.requests[1].prompt
    await hub.shutdown()


@pytest.mark.asyncio
async def test_ordinary_exception_cannot_forge_a_browser_scope_reason(tmp_path: Path) -> None:
    async def execute(arguments: dict[str, object]) -> object:
        error = RuntimeError(CANARY)
        error.__dict__["reason"] = "redirect_denied"
        raise error

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"browser.navigate+read": execute}
    )
    proposal = await orchestrator.propose(
        "synthetic-session",
        ToolCall("ordinary-error", "browser.navigate+read", {"url": PUBLIC_URL}),
        risk="observe/read-only",
    )
    await orchestrator.resolve(proposal.proposal_id, approved=True, arguments=proposal.arguments)
    result = await orchestrator.execute(proposal.proposal_id)
    assert result.error == "RuntimeError"
    assert result.observation is None
    assert result.model_observation() == {"error": "RuntimeError"}
    assert CANARY not in json.dumps(result.model_observation())


@pytest.mark.asyncio
async def test_cancelled_browser_work_is_not_misclassified_or_continued(tmp_path: Path) -> None:
    entered = asyncio.Event()

    async def execute(arguments: dict[str, object]) -> object:
        raise AssertionError("candidate bypassed its contextual executor")

    async def contextual(arguments: dict[str, object], context: ExecutionContext) -> object:
        entered.set()
        await context.cancellation.wait()
        context.check()
        raise AssertionError("cancelled work reached a browser result")

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    catalog = ToolCatalog(
        (
            ToolDescriptor(
                "browser.navigate+read",
                DEFAULT_MODEL_TOOLS[0],
                execute,
                lambda: True,
                "synthetic-browser",
                "read",
                contextual,
            ),
        )
    )
    orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {}, catalog=catalog)
    hub, model = RecordingHub(), FailureModel()
    controller = IntegratedCompanion(
        tmp_path,
        model,
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    task = asyncio.create_task(controller.respond("synthetic-session", "Synthetic browser work."))
    await asyncio.wait_for(entered.wait(), timeout=5)
    await controller.cancel("active", "user", session_id="synthetic-session")
    await asyncio.wait_for(task, timeout=5)
    terminals = [event for event in hub.events if event["type"] == "assistant_terminal"]
    assert len(terminals) == 1 and terminals[0]["state"] == "cancelled"
    assert len(model.requests) == 1
    terminal_index = hub.events.index(terminals[0])
    assert not any(
        event["type"] in {"tool_result", "tool_started", "assistant_delta"}
        for event in hub.events[terminal_index + 1 :]
    )
    persisted = await store.run_transaction(
        lambda connection: connection.execute(
            "SELECT error,observation_json FROM tool_proposals"
        ).fetchone()
    )
    assert persisted["error"] == "ExecutionCancelled"
    assert persisted["observation_json"] is None
    await hub.shutdown()
