from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.coordinator import Coordinator
from siro.services.agent.planning import (
    CheckpointPoint,
    ModelReply,
    PlanCheckpoint,
    PlanState,
    Subtask,
    SubtaskResult,
    SubtaskState,
    ToolRunResult,
)
from siro.services.agent.planning_adapters import (
    OrchestratorToolPort,
    planner_enabled,
)
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

READ = {"file.read": {"type": "object"}}


def plan_json(*items: dict[str, object]) -> str:
    return json.dumps({"subtasks": list(items)})


def task(capability: str = "file.read", deps: list[str] | None = None) -> dict[str, object]:
    return {
        "title": "t",
        "capability": capability,
        "arguments": {"path": "a.txt"},
        "depends_on": deps or [],
        "expect": "has fact",
    }


class ScriptedModel:
    def __init__(self, plan: str, verdicts: list[str], name: str = "cloud-x") -> None:
        self.plan, self.verdicts, self.name = plan, list(verdicts), name
        self.roles: list[str] = []

    async def complete(self, role: str, prompt: str) -> ModelReply:
        self.roles.append(role)
        if role == "planner":
            return ModelReply(self.plan, self.name)
        if role == "verifier":
            return ModelReply(self.verdicts.pop(0), self.name)
        return ModelReply("report", self.name)


class FakePort:
    def __init__(self, observations: dict[str, object], gate: asyncio.Event | None = None) -> None:
        self.observations, self.gate = observations, gate
        self.ran: list[str] = []
        self.cancelled = False

    async def run_read(self, plan_id: str, subtask: Subtask, session_id: str) -> ToolRunResult:
        self.ran.append(subtask.subtask_id)
        if self.gate is not None:
            await self.gate.wait()
        value = self.observations.get(subtask.subtask_id)
        if value is None:
            return ToolRunResult(f"run-{subtask.subtask_id}", None, None, "FileNotFoundError")
        return ToolRunResult(f"run-{subtask.subtask_id}", f"p-{subtask.subtask_id}", value)

    async def cancel(self, plan_id: str) -> None:
        self.cancelled = True


def good(quote: str) -> str:
    return json.dumps({"verified": True, "reason": "ok", "quotes": [quote]})


@pytest.mark.asyncio
async def test_plan_dependency_verify_report() -> None:
    points: list[CheckpointPoint] = []

    async def hook(cp: PlanCheckpoint) -> None:
        points.append(cp.point)
        cp.to_json()

    model = ScriptedModel(plan_json(task(), task(deps=["s1"])), [good("alpha"), good("beta")])
    port = FakePort({"s1": "alpha fact", "s2": "beta fact"})
    report = await Coordinator(model, port, read_tools=READ, hook=hook).run("sess", "goal")
    assert report.state is PlanState.COMPLETED
    assert [r.state for r in report.results] == [SubtaskState.VERIFIED] * 2
    assert report.results[0].sources[0].excerpt == "alpha"
    assert report.results[0].run_id == "run-s1" and report.results[1].proposal_id == "p-s2"
    assert points[0] is CheckpointPoint.PLAN_CREATED and points[-1] is CheckpointPoint.PLAN_FINISHED
    assert points.count(CheckpointPoint.SUBTASK_OBSERVED) == 2
    assert model.roles == ["planner", "verifier", "verifier", "reporter"]


@pytest.mark.asyncio
async def test_failure_propagates_and_blocks_dependent_without_running_tool() -> None:
    model = ScriptedModel(plan_json(task(), task(deps=["s1"])), [])
    port = FakePort({})  # s1 unreadable
    report = await Coordinator(model, port, read_tools=READ).run("sess", "goal")
    assert report.state is PlanState.FAILED
    assert report.results[0].state is SubtaskState.FAILED
    assert report.results[0].error == "FileNotFoundError"
    assert report.results[1].state is SubtaskState.BLOCKED
    assert port.ran == ["s1"]  # dependent never touched a tool, no invented content


@pytest.mark.asyncio
async def test_fabricated_quote_is_rejected() -> None:
    model = ScriptedModel(plan_json(task()), [good("not in the file")])
    report = await Coordinator(model, FakePort({"s1": "real text"}), read_tools=READ).run("s", "g")
    assert report.results[0].state is SubtaskState.FAILED
    assert report.results[0].error == "quotes_not_in_observation"
    assert report.results[0].sources == ()


@pytest.mark.parametrize(
    "bad",
    [
        plan_json(),
        plan_json(*[task()] * 4),
        plan_json(task("computer.execute")),
        plan_json(task(deps=["s2"])),
        "not json",
    ],
)
@pytest.mark.asyncio
async def test_invalid_plans_fail_without_running_tools(bad: str) -> None:
    port = FakePort({"s1": "x"})
    report = await Coordinator(ScriptedModel(bad, []), port, read_tools=READ).run("s", "g")
    assert report.state is PlanState.FAILED and not report.results and port.ran == []


@pytest.mark.asyncio
async def test_degraded_model_is_reported() -> None:
    model = ScriptedModel(plan_json(task()), [good("x")], name="local-qwen")
    report = await Coordinator(
        model, FakePort({"s1": "x"}), read_tools=READ, expected_models=frozenset({"cloud-x"})
    ).run("s", "g")
    assert report.degraded and "local-qwen" in report.models


@pytest.mark.asyncio
async def test_cancel_stops_pending_subtasks() -> None:
    gate = asyncio.Event()
    port = FakePort({"s1": "x", "s2": "y"}, gate)
    coordinator = Coordinator(
        ScriptedModel(plan_json(task(), task()), [good("x")]), port, read_tools=READ
    )
    running = asyncio.create_task(coordinator.run("s", "g"))
    while not port.ran:
        await asyncio.sleep(0)
    plan_id = next(iter(coordinator._active))
    await coordinator.cancel(plan_id)
    report = await running
    assert report.state is PlanState.CANCELLED and port.cancelled
    assert port.ran == ["s1"]
    assert all(
        r.state in {SubtaskState.CANCELLED} or r.state in {SubtaskState.VERIFIED}
        for r in report.results
    )


@pytest.mark.asyncio
async def test_resume_does_not_rerun_verified_and_flags_unknown() -> None:
    seen: list[PlanCheckpoint] = []

    async def hook(cp: PlanCheckpoint) -> None:
        seen.append(cp)

    model = ScriptedModel(plan_json(task(), task(), task()), [good("a")])
    await Coordinator(model, FakePort({"s1": "a", "s2": "b"}), read_tools=READ, hook=hook).run(
        "s", "g"
    )
    # crash point: s1 verified, s2 dispatched (run_id, no observation)
    cp = next(
        c for c in seen if c.point is CheckpointPoint.SUBTASK_OBSERVED and len(c.results) == 2
    )
    cp = PlanCheckpoint(
        cp.plan_id,
        cp.point,
        PlanState.RUNNING,
        cp.plan,
        (
            cp.results[0],
            SubtaskResult("s2", SubtaskState.RUNNING, run_id="run-s2"),
        ),
    )
    port = FakePort({"s3": "c"})
    resumed = ScriptedModel("", [good("c")])
    report = await Coordinator(resumed, port, read_tools=READ).run("s", "g", resume=cp)
    assert port.ran == ["s3"]  # s1 not rerun, s2 never resent
    assert report.results[1].error == "outcome_unknown"


@pytest.mark.asyncio
async def test_real_orchestrator_and_journal(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    calls: list[dict[str, object]] = []

    async def reader(arguments: dict[str, object]) -> object:
        calls.append(arguments)
        return "alpha fact"

    orch = ToolOrchestrator(SQLiteToolProposalRepository(store), {"browser.navigate+read": reader})
    runs = SQLiteAgentRunRepository(store)
    port = OrchestratorToolPort(orch, runs, backend="cloud-x")
    sub = Subtask("s1", "t", "browser.navigate+read", {"url": "https://example.com"}, (), "e")
    result = await port.run_read("plan1", sub, "sess")
    assert result.error is None and result.observation == "alpha fact" and calls
    row = await runs.get(result.run_id or "")
    assert row is not None and result.proposal_id
    proposal = await orch.get(result.proposal_id)
    assert proposal is not None and proposal.state.value == "completed"


def test_flag_default_off() -> None:
    assert planner_enabled({}) is False
    assert planner_enabled({"SIRO_AGENT_PLANNER_ENABLED": "1"}) is True


@pytest.mark.asyncio
async def test_integrated_entry_is_off_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
    from siro.adapters.models.mock import MockModel
    from siro.ports.models import Privacy
    from siro.services.presentation.gateway import GatewayHub
    from siro.services.presentation.integrated import IntegratedCompanion

    built: list[object] = []

    def factory(runs: SQLiteAgentRunRepository) -> Coordinator:
        built.append(runs)
        return Coordinator(
            ScriptedModel(plan_json(task()), [good("x")]), FakePort({"s1": "x"}), read_tools=READ
        )

    companion = IntegratedCompanion(
        tmp_path,
        MockModel(),
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        agent_planner_factory=factory,
    )
    monkeypatch.delenv("SIRO_AGENT_PLANNER_ENABLED", raising=False)
    assert await companion.run_agent_plan("s", "g") is None and not built
    monkeypatch.setenv("SIRO_AGENT_PLANNER_ENABLED", "1")
    report = await companion.run_agent_plan("s", "g")
    assert report is not None and report.state is PlanState.COMPLETED and len(built) == 1
