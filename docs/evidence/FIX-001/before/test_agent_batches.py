from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


class BatchModel:
    name = "batch"

    def __init__(self, duplicate: bool = False, repeat: bool = False) -> None:
        self.requests: list[ModelRequest] = []
        self.duplicate = duplicate
        self.repeat = repeat

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        if len(self.requests) == 1 or self.repeat:
            for index in range(2):
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall(
                        f"call-{len(self.requests)}-{0 if self.duplicate else index}",
                        "computer.execute",
                        {"index": index},
                    ),
                )
        else:
            yield ModelChunk("text", "done")
        yield ModelChunk("finished")


class RecordingHub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    async def broadcast(self, payload: dict[str, object], *, urgent: bool = False) -> None:
        self.events.append(payload)


async def setup(
    tmp_path: Path, model: BatchModel, executor: object, *, automatic: bool = True, steps: int = 8
) -> tuple[IntegratedCompanion, ToolOrchestrator, SQLiteStore, RecordingHub]:
    from typing import cast

    from siro.services.tools.orchestrator import ToolExecutor

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": cast(ToolExecutor, executor)}
    )
    hub = RecordingHub()
    controller = IntegratedCompanion(
        tmp_path,
        model,
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: automatic,
        max_agent_steps=steps,
    )
    return controller, orchestrator, store, hub


@pytest.mark.asyncio
async def test_batch_waits_for_success_and_failure_and_deduplicates_callback(
    tmp_path: Path,
) -> None:
    executed: list[int] = []

    async def execute(arguments: dict[str, object]) -> object:
        executed.append(int(str(arguments["index"])))
        if arguments["index"] == 1:
            raise ValueError("synthetic")
        return {"ok": True}

    model = BatchModel()
    controller, orchestrator, store, hub = await setup(tmp_path, model, execute)
    await controller.respond("batch", "goal")
    assert executed == [0, 1]
    assert len(model.requests) == 2
    messages = model.requests[-1].messages
    assert [m.role for m in messages] == ["system", "user", "assistant", "tool", "tool"]
    assert [m.tool_call_id for m in messages[-2:]] == ["call-1-0", "call-1-1"]
    assert "ValueError" in messages[-1].content
    row = await store.run_transaction(
        lambda c: c.execute("SELECT proposal_id FROM tool_proposals LIMIT 1").fetchone()
    )
    proposal = await orchestrator.get(row[0])
    assert proposal is not None
    await controller.continue_after_tool(proposal)
    assert len(model.requests) == 2
    assert len([e for e in hub.events if e["type"] == "assistant_terminal"]) == 1


@pytest.mark.asyncio
async def test_manual_denied_batch_and_out_of_order_callbacks(tmp_path: Path) -> None:
    executed: list[object] = []

    async def execute(arguments: dict[str, object]) -> object:
        executed.append(arguments)
        return {"ok": True}

    model = BatchModel()
    controller, orchestrator, store, hub = await setup(tmp_path, model, execute, automatic=False)
    await controller.respond("manual", "goal")
    rows = await store.run_transaction(
        lambda c: c.execute("SELECT proposal_id FROM tool_proposals ORDER BY call_id").fetchall()
    )
    proposals = [await orchestrator.get(row[0]) for row in rows]
    first, second = proposals
    assert first is not None and second is not None
    denied = await orchestrator.resolve(
        second.proposal_id, approved=False, arguments=second.arguments
    )
    await controller.continue_after_tool(denied)
    await controller.continue_after_tool(denied)
    assert len(model.requests) == 1
    await orchestrator.resolve(first.proposal_id, approved=True, arguments=first.arguments)
    completed = await orchestrator.execute(first.proposal_id)
    await controller.continue_after_tool(completed)
    assert len(executed) == 1
    assert len(model.requests) == 2
    assert "denied" in model.requests[-1].messages[-1].content
    assert len([e for e in hub.events if e["type"] == "assistant_terminal"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicate", [True, False])
async def test_duplicate_and_step_budget_fail_once(tmp_path: Path, duplicate: bool) -> None:
    executed: list[object] = []

    async def execute(arguments: dict[str, object]) -> object:
        executed.append(arguments)
        return {}

    model = BatchModel(duplicate=duplicate, repeat=True)
    controller, _, store, hub = await setup(tmp_path, model, execute, steps=1)
    await controller.respond("limit", "goal")
    assert len(executed) == (0 if duplicate else 2)
    assert len(model.requests) == 1
    assert len([e for e in hub.events if e["type"] == "assistant_terminal"]) == 1
    row = await store.run_transaction(
        lambda c: c.execute("SELECT state FROM agent_runs").fetchone()
    )
    assert row[0] == "failed"


async def wait_for_executor_entry(
    task: asyncio.Task[None], entered: asyncio.Event, iteration: int, *, timeout: float = 10
) -> None:
    """Fixture readiness is separate from the product's two-second stop deadline."""
    ready = asyncio.create_task(entered.wait())
    try:
        done, _ = await asyncio.wait(
            {task, ready}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
        )
        if ready in done:
            return
        if task in done:
            await task  # expose the original exception instead of a misleading barrier timeout
            pytest.fail(f"iteration {iteration}: respond ended before executor entry")
        stack = [(frame.f_code.co_name, frame.f_lineno) for frame in task.get_stack()]
        pytest.fail(f"iteration {iteration}: fixture entry exceeded {timeout}s; task stack={stack}")
    finally:
        ready.cancel()
        await asyncio.gather(ready, return_exceptions=True)
        if not entered.is_set() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("completion_first", [False, True])
async def test_cancel_completion_orderings_100_times(
    tmp_path: Path, completion_first: bool
) -> None:
    for iteration in range(100):
        entered, release = asyncio.Event(), asyncio.Event()
        executed: list[object] = []

        async def execute(
            arguments: dict[str, object],
            executed: list[object] = executed,
            entered: asyncio.Event = entered,
            release: asyncio.Event = release,
        ) -> object:
            executed.append(arguments)
            entered.set()
            await release.wait()
            return {}

        model = BatchModel()
        controller, _, store, hub = await setup(tmp_path / str(iteration), model, execute)
        await controller._ensure_core()  # move SQLite/identity startup outside the race barrier
        task = asyncio.create_task(controller.respond("race", "goal"))
        await wait_for_executor_entry(task, entered, iteration)
        if completion_first:
            release.set()
            await asyncio.wait_for(task, 2)
        elif iteration % 2:
            release.set()
        await controller.cancel("active", "test cancel")
        release.set()
        await asyncio.wait_for(task, 2)
        terminal = [i for i, e in enumerate(hub.events) if e["type"] == "assistant_terminal"]
        assert len(terminal) == 1
        assert not any(
            e["type"] in {"assistant_delta", "tool_result", "tool_started"}
            for e in hub.events[terminal[0] + 1 :]
        )
        assert len(executed) == (2 if completion_first else 1)
        assert len(model.requests) == (2 if completion_first else 1)
        row = await store.run_transaction(
            lambda c: c.execute("SELECT state FROM agent_runs").fetchone()
        )
        assert row[0] == ("completed" if completion_first else "cancelled")


@pytest.mark.asyncio
async def test_cancel_pending_batch_prevents_later_approval(tmp_path: Path) -> None:
    async def execute(arguments: dict[str, object]) -> object:
        raise AssertionError("cancelled queued call must not execute")

    controller, orchestrator, store, hub = await setup(
        tmp_path, BatchModel(), execute, automatic=False
    )
    await controller.respond("queued", "goal")
    await controller.cancel("active", "stop")
    rows = await store.run_transaction(
        lambda c: c.execute("SELECT proposal_id, state FROM tool_proposals").fetchall()
    )
    assert len(rows) == 2
    for row in rows:
        assert row[1] == "denied"
        with pytest.raises(ValueError):
            await orchestrator.resolve(row[0], approved=True, arguments={})
    assert len([e for e in hub.events if e["type"] == "assistant_terminal"]) == 1


def test_http_denial_never_executes_and_delivers_terminal_result(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from siro.services.presentation.gateway import create_app
    from siro.services.tools.orchestrator import ProposalState, ToolProposal

    store = SQLiteStore(tmp_path / "http.db")
    asyncio.run(store.initialize())
    delivered: list[ToolProposal] = []

    async def execute(arguments: dict[str, object]) -> object:
        raise AssertionError("denied call executed")

    async def result(proposal: ToolProposal) -> None:
        delivered.append(proposal)

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": execute}
    )
    proposal = asyncio.run(
        orchestrator.propose("http", ToolCall("denied", "computer.execute", {}), risk="computer")
    )
    origin = "http://127.0.0.1:8000"
    with TestClient(create_app(tool_orchestrator=orchestrator, on_tool_result=result)) as client:
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        response = client.post(
            f"/v1/tool-proposals/{proposal.proposal_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
            json={"approved": False},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "denied"}
    assert len(delivered) == 1
    assert delivered[0].state is ProposalState.DENIED


@pytest.mark.asyncio
async def test_executor_entry_exposes_original_error() -> None:
    async def fail() -> None:
        raise RuntimeError("original respond failure")

    task = asyncio.create_task(fail())
    with pytest.raises(RuntimeError, match="original respond failure"):
        await wait_for_executor_entry(task, asyncio.Event(), 17)


@pytest.mark.asyncio
async def test_executor_entry_timeout_diagnoses_and_cleans_task() -> None:
    task = asyncio.create_task(asyncio.sleep(100))
    with pytest.raises(pytest.fail.Exception, match=r"iteration 23.*task stack"):
        await wait_for_executor_entry(task, asyncio.Event(), 23, timeout=0.01)
    assert task.cancelled()
