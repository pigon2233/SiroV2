from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore, apply_migrations, load_migrations
from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
)
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.presentation.gateway import GatewayHub, create_app
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


class NeverModel:
    name = "recovery-must-not-generate"

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        raise AssertionError("readback must never call model")
        yield ModelChunk("finished")


def controller_at(directory: Path) -> IntegratedCompanion:
    async def forbidden(arguments: dict[str, object]) -> object:
        raise AssertionError("recovery must never dispatch")

    return IntegratedCompanion(
        directory,
        NeverModel(),
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        runtime_profile="candidate",
        tool_orchestrator=ToolOrchestrator(
            SQLiteToolProposalRepository(SQLiteStore(directory / "siro.db")),
            {"computer.execute": forbidden},
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phase", ["before_dispatch", "after_dispatch", "before_observation", "after_observation"]
)
async def test_abrupt_process_crash_readback_never_replays(tmp_path: Path, phase: str) -> None:
    fixture = Path(__file__).parents[1] / "fixtures/run_journal_crash.py"
    outcome = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, str(fixture), str(tmp_path), phase],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert outcome.returncode == 42, outcome.stderr
    marker = tmp_path / "effect.txt"
    before = marker.read_text() if marker.exists() else ""
    assert bool(before) == (phase in {"before_observation", "after_observation"})
    controller = controller_at(tmp_path)
    await controller.startup()
    readback = await controller.recovery_readback("crash-session")
    assert readback is not None
    assert readback["recovery_status"] == "interrupted"
    assert readback["state"] == "failed"
    assert readback["model_rounds"] == 1 and readback["max_model_rounds"] == 8
    assert readback["tool_calls"] == 1 and readback["runtime_profile"] == "candidate"
    assert readback["backend"] == "synthetic-crash-model"
    assert readback["privacy"] == "local_only"
    assert readback["goal"] == "synthetic goal; do not replay"
    messages = cast(list[dict[str, object]], readback["messages"])
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool"]
    assert messages[-1]["tool_call_id"] == "effect-1"
    observation = json.loads(str(messages[-1]["content"]))
    if phase == "after_observation":
        assert observation == {"confirmed": True}
        assert readback["error"] == "interrupted_restart"
    else:
        # RUNNING persisted before intent is conservative unknown, even if no effect occurred.
        assert observation["error"] == "outcome_unknown"
        assert readback["error"] == "outcome_unknown"
    assert (marker.read_text() if marker.exists() else "") == before
    again = controller_at(tmp_path)
    await again.startup()
    assert await again.recovery_readback("crash-session") == readback
    assert await again.recovery_readback("other-session") is None
    store = SQLiteStore(tmp_path / "siro.db")
    row = await store.run_transaction(
        lambda c: c.execute("SELECT * FROM tool_proposals").fetchone()
    )
    assert row is not None and row["state"] == "failed"
    assert controller._tool_orchestrator is not None
    with pytest.raises(ValueError):
        await controller._tool_orchestrator.execute(str(row["proposal_id"]))
    assert await store.integrity_check() == "ok"


@pytest.mark.asyncio
async def test_partial_batch_pending_approval_fenced_and_pairs_ordered(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    run = await repo.start("partial", "goal")
    await repo.start_journal(run.run_id, backend="synthetic", privacy="local_only", max_rounds=2)
    assert await repo.reserve_round(run.run_id) == 1
    calls = (ToolCall("one", "computer.execute", {}), ToolCall("two", "computer.execute", {}))
    history = [ModelMessage("user", "goal"), ModelMessage("assistant", tool_calls=calls)]
    await repo.checkpoint(run.run_id, history)
    await repo.checkpoint(run.run_id, history)  # idempotent checkpoint; counters do not inflate
    await repo.record_dispatch(run.run_id, "one")
    await repo.record_observation(run.run_id, "one", {"ok": True})
    await repo.record_observation(run.run_id, "one", {"ok": True})
    with pytest.raises(ValueError, match="conflicting"):
        await repo.record_observation(run.run_id, "one", {"ok": False})

    async def forbidden(arguments: dict[str, object]) -> object:
        raise AssertionError("old approval dispatched")

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": forbidden}
    )
    proposal = await orchestrator.propose("partial", calls[1], risk="computer")
    # Abrupt crash between proposal creation and journal bind: match canonical call on restart.
    await orchestrator.resolve(proposal.proposal_id, approved=True, arguments={})
    with pytest.raises(ValueError, match="replayed"):
        await orchestrator.execute(proposal.proposal_id)  # legacy has no live journal ownership
    assert await repo.reconcile() == 1
    assert await repo.reconcile() == 0
    readback = await repo.readback("partial")
    assert readback is not None and readback["tool_calls"] == 2
    messages = cast(list[dict[str, object]], readback["messages"])
    assert [m.get("tool_call_id") for m in messages[-2:]] == ["one", "two"]
    assert json.loads(str(messages[-2]["content"])) == {"ok": True}
    assert json.loads(str(messages[-1]["content"]))["error"] == "not_dispatched"
    fenced = await orchestrator.get(proposal.proposal_id)
    assert fenced is not None and fenced.state.value == "denied"
    with pytest.raises(ValueError):
        await orchestrator.execute(proposal.proposal_id)


@pytest.mark.asyncio
async def test_durable_budget_and_finished_crash_window(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    repo = SQLiteAgentRunRepository(store)
    run = await repo.start("budget", "goal")
    await repo.start_journal(run.run_id, backend="synthetic", privacy="local_only", max_rounds=1)
    assert await repo.reserve_round(run.run_id) == 1
    reopened = SQLiteAgentRunRepository(SQLiteStore(store.path))
    with pytest.raises(RuntimeError, match="agent_step_limit"):
        await reopened.reserve_round(run.run_id)
    await repo.checkpoint(
        run.run_id, [ModelMessage("user", "goal"), ModelMessage("assistant", "done")]
    )
    await repo.finish_journal(run.run_id)
    # Crash before old agent_runs final append must not leave a forever-RUNNING run.
    assert await reopened.reconcile() == 1
    row = await reopened.readback("budget")
    assert row is not None and row["state"] == "failed"
    assert row["model_rounds"] == 1
    assert cast(list[dict[str, object]], row["messages"])[-1]["content"] == "done"


@pytest.mark.parametrize("old_version", [0, 10, 12])
def test_additive_upgrade_and_old_reader_rollback(tmp_path: Path, old_version: int) -> None:
    path = tmp_path / "upgrade.db"
    migrations = load_migrations()
    assert migrations[12].version == 13
    assert migrations[12].name == "run_journal"
    with sqlite3.connect(path) as c:
        apply_migrations(c, migrations[:old_version])
        if old_version:
            c.execute("INSERT INTO identities VALUES ('old', '{}', 1, 'synthetic')")
            c.commit()
        apply_migrations(c, migrations)
        snapshot = c.execute("SELECT * FROM schema_migrations").fetchall()
        apply_migrations(c, migrations)
        assert c.execute("SELECT * FROM schema_migrations").fetchall() == snapshot
        # Prior loader accepts unknown additive migration and old table contracts remain usable.
        apply_migrations(c, migrations[:12])
        assert c.execute("SELECT name FROM sqlite_master WHERE name='run_journal'").fetchone()
        assert c.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        if old_version:
            assert c.execute(
                "SELECT core_json FROM identities WHERE identity_id='old'"
            ).fetchone() == ("{}",)


def test_readback_auth_startup_and_legacy_unrestorable(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    asyncio.run(store.initialize())
    repo = SQLiteAgentRunRepository(store)
    asyncio.run(repo.start("legacy", "old assembled prompt"))
    controller = controller_at(tmp_path)
    with TestClient(
        create_app(on_startup=controller.startup, on_recovery=controller.recovery_readback)
    ) as client:
        assert controller._core is not None  # startup, not first turn, composes and reconciles
        assert client.get("/v1/agent-runs/legacy").status_code == 401
        token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
            "token"
        ]
        response = client.get("/v1/agent-runs/legacy", headers={"authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["recovery_status"] == "legacy_unrestorable"
        assert "messages" not in response.json()
        assert (
            client.get(
                "/v1/agent-runs/missing", headers={"authorization": f"Bearer {token}"}
            ).status_code
            == 404
        )


class ManualModel:
    name = "synthetic-manual"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        if len(self.requests) == 1:
            yield ModelChunk(
                "tool_request", tool_call=ToolCall("manual-call", "computer.execute", {})
            )
        else:
            yield ModelChunk("text", "confirmed")
        yield ModelChunk("finished")


def test_http_approval_uses_dispatch_and_observation_journal(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    asyncio.run(store.initialize())
    model = ManualModel()
    effects: list[str] = []

    async def effect(arguments: dict[str, object]) -> object:
        effects.append("once")
        return {"confirmed": True}

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": effect}
    )
    controller = IntegratedCompanion(
        tmp_path,
        model,
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        runtime_profile="candidate",
        tool_orchestrator=orchestrator,
    )
    with TestClient(
        create_app(
            on_startup=controller.startup,
            on_turn=controller.respond,
            on_recovery=controller.recovery_readback,
            on_tool_result=controller.continue_after_tool,
            tool_orchestrator=orchestrator,
        )
    ) as client:
        token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
            "token"
        ]
        headers = {"authorization": f"Bearer {token}"}
        assert (
            client.post(
                "/v1/conversations/manual/turns", headers=headers, json={"text": "synthetic goal"}
            ).status_code
            == 200
        )
        with sqlite3.connect(store.path) as c:
            proposal_id = c.execute("SELECT proposal_id FROM tool_proposals").fetchone()[0]
        assert (
            client.post(
                f"/v1/tool-proposals/{proposal_id}/approve",
                headers=headers,
                json={"approved": True},
            ).status_code
            == 200
        )
        readback = client.get("/v1/agent-runs/manual", headers=headers).json()
        assert readback["state"] == "completed" and readback["recovery_status"] == "terminal"
        assert readback["model_rounds"] == 2 and readback["tool_calls"] == 1
        assert readback["calls"][0]["dispatched"] == 1
        assert json.loads(readback["calls"][0]["observation_json"]) == {"confirmed": True}
        assert (
            client.post(
                f"/v1/tool-proposals/{proposal_id}/approve",
                headers=headers,
                json={"approved": True},
            ).status_code
            == 404
        )
    assert effects == ["once"] and len(model.requests) == 2
    assert model.requests[1].messages[-1].tool_call_id == "manual-call"


def test_actual_frontend_recovery_notice() -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    function = html[html.index("function recoveryNotice(") : html.index("async function boot()")]
    boot = html[html.index("async function boot()") : html.index("function connectControl()")]
    assert "/v1/agent-runs/browser" in boot and "recoveryNotice(run)" in boot
    script = (
        function
        + """
const assert = require('node:assert/strict');
assert.match(recoveryNotice({recovery_status:'interrupted',error:'outcome_unknown'}), /結果未知/);
assert.match(
 recoveryNotice({recovery_status:'interrupted',error:'interrupted_restart'}), /沒有重新執行/
);
assert.equal(recoveryNotice({recovery_status:'terminal'}), null);
assert.equal(recoveryNotice({recovery_status:'legacy_unrestorable'}), null);
"""
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["before", "after"])
async def test_atomic_candidate_proposal_crash_never_replays(tmp_path: Path, phase: str) -> None:
    fixture = Path("docs/evidence/RT-003-FIX-01/identity_crash.py")
    outcome = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, str(fixture), str(tmp_path), phase],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert outcome.returncode == 42, outcome.stderr
    controller = controller_at(tmp_path)
    await controller.startup()
    readback = await controller.recovery_readback("identity-crash")
    assert readback is not None and readback["state"] == "failed"
    assert readback["error"] == "interrupted_restart"
    calls = cast(list[dict[str, object]], readback["calls"])
    assert calls[0]["call_id"] == "call-0" and calls[0]["dispatched"] == 0
    assert (calls[0]["proposal_id"] is not None) == (phase == "after")
    assert json.loads(str(calls[0]["observation_json"]))["error"] == "not_dispatched"
    if phase == "after":
        assert controller._tool_orchestrator is not None
        proposal = await controller._tool_orchestrator.get(str(calls[0]["proposal_id"]))
        assert proposal is not None and proposal.call_id == "call-0"
        assert proposal.state.value == "denied"
        with pytest.raises(ValueError, match="recovered"):
            await controller._tool_orchestrator.execute(proposal.proposal_id)
    assert not (tmp_path / "effect.txt").exists()


def test_http_reused_provider_id_manual_approval_and_denial(tmp_path: Path) -> None:
    from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

    class Model:
        name = "reused-http"

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            if request.messages[-1].role == "tool":
                assert request.messages[-1].tool_call_id == "call-0"
                yield ModelChunk("text", "done")
            else:
                yield ModelChunk(
                    "tool_request", tool_call=ToolCall("call-0", "computer.execute", {})
                )
            yield ModelChunk("finished")

    class RecordingHub(GatewayHub):
        def __init__(self) -> None:
            super().__init__()
            self.events: list[dict[str, object]] = []

        async def broadcast(self, payload: dict[str, object], *, urgent: bool = False) -> None:
            self.events.append(payload)

    hub = RecordingHub()
    effects: list[object] = []

    async def effect(arguments: dict[str, object]) -> object:
        effects.append(arguments)
        return {"confirmed": True}

    store = SQLiteStore(tmp_path / "siro.db")
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": effect}
    )
    controller = IntegratedCompanion(
        tmp_path,
        Model(),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        runtime_profile="candidate",
        tool_orchestrator=orchestrator,
        auto_authorize=lambda: False,
    )
    with TestClient(
        create_app(
            hub=hub,
            on_startup=controller.startup,
            on_turn=controller.respond,
            on_recovery=controller.recovery_readback,
            on_tool_result=controller.continue_after_tool,
            tool_orchestrator=orchestrator,
        )
    ) as client:
        token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
            "token"
        ]
        headers = {"authorization": f"Bearer {token}"}
        for approved in (True, False):
            assert (
                client.post(
                    "/v1/conversations/reuse/turns",
                    headers=headers,
                    json={"text": "synthetic goal"},
                ).status_code
                == 200
            )
            with sqlite3.connect(store.path) as c:
                proposal_id = c.execute(
                    "SELECT proposal_id FROM tool_proposals WHERE state='pending'"
                ).fetchone()[0]
            response = client.post(
                f"/v1/tool-proposals/{proposal_id}/approve",
                headers=headers,
                json={"approved": approved},
            )
            assert response.status_code == 200, response.text
            assert response.json() == {"status": "completed" if approved else "denied"}
            readback = client.get("/v1/agent-runs/reuse", headers=headers).json()
            assert readback["state"] == "completed" and readback["calls"][0]["call_id"] == "call-0"
            assert (
                client.post(
                    f"/v1/tool-proposals/{proposal_id}/approve",
                    headers=headers,
                    json={"approved": True},
                ).status_code
                == 404
            )
    assert effects == [{}]
    tool_events = [
        e for e in hub.events if e["type"] in {"tool_proposal", "tool_started", "tool_result"}
    ]
    assert tool_events and all(e["call_id"] == "call-0" for e in tool_events)


@pytest.mark.asyncio
async def test_mixed_legacy_and_mapped_rows_reconcile_exact_owners(tmp_path: Path) -> None:
    from siro.services.tools.orchestrator import (
        ProposalState,
        SQLiteToolProposalRepository,
        ToolOrchestrator,
    )

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    runs = SQLiteAgentRunRepository(store)
    repository = SQLiteToolProposalRepository(store)

    async def forbidden(arguments: dict[str, object]) -> object:
        raise AssertionError("mixed-row recovery replayed")

    orchestrator = ToolOrchestrator(repository, {"computer.execute": forbidden})
    old = await runs.start("mixed", "old", runtime_backend="test")
    call = ToolCall("call-0", "computer.execute", {})
    await runs.checkpoint(old.run_id, [ModelMessage("assistant", "", (call,))])
    legacy = await orchestrator.propose("mixed", call, risk="computer")
    await orchestrator.resolve(legacy.proposal_id, approved=True, arguments={})
    await repository.transition(legacy.proposal_id, ProposalState.APPROVED, ProposalState.RUNNING)
    # Historical insert->bind gap RUNNING is conservative unknown even without dispatch intent.
    new = await runs.start("mixed", "new", runtime_backend="test")
    await runs.checkpoint(new.run_id, [ModelMessage("assistant", "", (call,))])
    orchestrator.start_run(new.run_id, "mixed")
    mapped = await orchestrator.propose("mixed", call, risk="computer", run_id=new.run_id)
    await orchestrator.resolve(mapped.proposal_id, approved=True, arguments={})
    assert await repository.journal_owner(mapped) == new.run_id
    assert await repository.journal_owner(legacy) == old.run_id
    # A truly legacy proposal with no journal keeps its original call ID and lifecycle.
    standalone = await orchestrator.propose("legacy-only", call, risk="computer")
    assert await repository.journal_owner(standalone) is None
    await runs.reconcile()
    rows = await store.run_transaction(
        lambda c: c.execute("SELECT * FROM run_journal_calls ORDER BY rowid").fetchall()
    )
    assert rows[0]["run_id"] == old.run_id and rows[0]["dispatched"] == 1
    assert json.loads(rows[0]["observation_json"])["error"] == "outcome_unknown"
    assert rows[1]["run_id"] == new.run_id and rows[1]["dispatched"] == 0
    assert json.loads(rows[1]["observation_json"])["error"] == "not_dispatched"
    for proposal, state in (
        (legacy, ProposalState.FAILED),
        (mapped, ProposalState.DENIED),
        (standalone, ProposalState.PENDING),
    ):
        loaded = await repository.get(proposal.proposal_id)
        assert loaded is not None and loaded.state is state
    fresh = ToolOrchestrator(repository, {"computer.execute": forbidden})
    for proposal in (legacy, mapped):
        with pytest.raises(ValueError, match="recovered"):
            await fresh.execute(proposal.proposal_id)
