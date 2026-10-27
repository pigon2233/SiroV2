"""R06: crash a real R05 coordinator run at each hook point, restart, and resume safely."""

from __future__ import annotations

import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

pytest.importorskip("siro.services.agent.coordinator", reason="needs the R05 coordinator")
sys.path.insert(0, str(Path(__file__).parent))

from checkpoint_crash import CrashPoint

from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.checkpoints import (
    Effect,
    Outcome,
    Phase,
    SQLiteCheckpointRepository,
)
from siro.services.agent.coordinator import Coordinator
from siro.services.agent.planning import (
    CheckpointPoint,
    ModelReply,
    PlanCheckpoint,
    PlanState,
    Subtask,
    ToolRunResult,
)
from siro.services.agent.resume import (
    ResumeWorker,
    build_resume,
    make_checkpoint_hook,
)

READ = {"file.read": {"type": "object"}}


def _task(deps: list[str] | None = None) -> dict[str, object]:
    return {
        "title": "t",
        "capability": "file.read",
        "arguments": {"path": "a.txt"},
        "depends_on": deps or [],
        "expect": "has fact",
    }


PLAN = json.dumps({"subtasks": [_task(), _task(["s1"])]})


class Model:
    def __init__(self, quotes: list[str]) -> None:
        self.quotes = list(quotes)
        self.roles: list[str] = []

    async def complete(self, role: str, prompt: str) -> ModelReply:
        self.roles.append(role)
        if role == "planner":
            return ModelReply(PLAN, "cloud-x")
        if role == "verifier":
            quote = self.quotes.pop(0)
            return ModelReply(
                json.dumps({"verified": True, "reason": "ok", "quotes": [quote]}), "cloud-x"
            )
        return ModelReply("report", "cloud-x")


class Port:
    """Shared across simulated restarts: counts real tool executions per subtask."""

    def __init__(self, crash_after_tool: str | None = None) -> None:
        self.ran: list[str] = []
        self.crash_after_tool = crash_after_tool

    async def run_read(self, plan_id: str, subtask: Subtask, session_id: str) -> ToolRunResult:
        self.ran.append(subtask.subtask_id)
        if self.crash_after_tool == subtask.subtask_id:
            self.crash_after_tool = None
            raise CrashPoint("after tool, before ack")
        return ToolRunResult(
            f"run-{subtask.subtask_id}", f"p-{subtask.subtask_id}", f"alpha {subtask.subtask_id}"
        )

    async def cancel(self, plan_id: str) -> None:
        return None


async def _repo(path: Path) -> SQLiteCheckpointRepository:
    store = SQLiteStore(path / "siro.db")
    await store.initialize()
    return SQLiteCheckpointRepository(store)


def _crashing(
    repo: SQLiteCheckpointRepository, point: CheckpointPoint, subtask: str, *, after: bool
) -> Callable[[PlanCheckpoint], Awaitable[None]]:
    inner = make_checkpoint_hook(repo, session_of=lambda _p: "sess")

    async def hook(cp: PlanCheckpoint) -> None:
        hit = cp.point is point and (
            (
                cp.point is CheckpointPoint.SUBTASK_DISPATCH
                and not any(r.subtask_id == subtask for r in cp.results)
                and len(cp.results) == int(subtask[1:]) - 1
            )
            or (
                cp.point is not CheckpointPoint.SUBTASK_DISPATCH
                and cp.results
                and cp.results[-1].subtask_id == subtask
            )
        )
        if hit and not after:
            raise CrashPoint(point.value)
        await inner(cp)
        if hit and after:
            raise CrashPoint(point.value)

    return hook


async def _crash_run(
    path: Path, port: Port, point: CheckpointPoint | None, subtask: str, *, after: bool
) -> str:
    repo = await _repo(path)
    hook = (
        make_checkpoint_hook(repo, session_of=lambda _p: "sess")
        if point is None
        else _crashing(repo, point, subtask, after=after)
    )
    model = Model(["alpha s1", "alpha s2"])
    with pytest.raises(CrashPoint):
        await Coordinator(model, port, read_tools=READ, hook=hook).run("sess", "goal")
    plans = await repo.unfinished_plans()
    assert len(plans) == 1
    return plans[0].plan_id


async def _restart(path: Path, port: Port, quotes: list[str]) -> tuple[Model, dict[str, str]]:
    repo = await _repo(path)  # fresh process state, same database
    model = Model(quotes)
    hook = make_checkpoint_hook(repo, session_of=lambda _p: "sess")
    coordinator = Coordinator(model, port, read_tools=READ, hook=hook)
    worker = ResumeWorker(repo, coordinator, enabled=lambda: True)
    return model, await worker.resume_all()


async def _states(path: Path, plan_id: str) -> dict[str, tuple[Phase, Outcome | None]]:
    repo = await _repo(path)
    return {c.step_id: (c.phase, c.outcome) for c in await repo.steps(plan_id)}


@pytest.mark.asyncio
async def test_crash_before_dispatch_runs_each_tool_once(tmp_path: Path) -> None:
    port = Port()
    pid = await _crash_run(tmp_path, port, CheckpointPoint.SUBTASK_DISPATCH, "s1", after=False)
    assert port.ran == []
    model, outcome = await _restart(tmp_path, port, ["alpha s1", "alpha s2"])
    assert outcome == {pid: "resumed"}
    assert port.ran == ["s1", "s2"] and "planner" not in model.roles
    assert set((await _states(tmp_path, pid)).values()) == {(Phase.SAVED, Outcome.SUCCESS)}


@pytest.mark.asyncio
async def test_crash_after_tool_before_ack_reruns_read_only_step(tmp_path: Path) -> None:
    port = Port(crash_after_tool="s1")
    pid = await _crash_run(tmp_path, port, None, "s1", after=False)
    assert port.ran == ["s1"]  # effect happened, result never acknowledged
    states = await _states(tmp_path, pid)
    assert states["s1"][0] is Phase.DISPATCHED
    _, outcome = await _restart(tmp_path, port, ["alpha s1", "alpha s2"])
    assert outcome == {pid: "resumed"}
    assert port.ran == ["s1", "s1", "s2"]  # read-only: one allowed re-read, never s2 twice
    final = await _states(tmp_path, pid)
    assert final == {"s1": (Phase.SAVED, Outcome.SUCCESS), "s2": (Phase.SAVED, Outcome.SUCCESS)}


@pytest.mark.asyncio
async def test_crash_after_observed_save_only_reverifies(tmp_path: Path) -> None:
    port = Port()
    pid = await _crash_run(tmp_path, port, CheckpointPoint.SUBTASK_OBSERVED, "s1", after=True)
    assert port.ran == ["s1"]
    model, _ = await _restart(tmp_path, port, ["alpha s1", "alpha s2"])
    assert port.ran == ["s1", "s2"]  # s1 tool is NOT run again
    assert model.roles.count("verifier") == 2
    assert all(v == (Phase.SAVED, Outcome.SUCCESS) for v in (await _states(tmp_path, pid)).values())


@pytest.mark.asyncio
async def test_crash_after_verified_saved_is_not_redone(tmp_path: Path) -> None:
    port = Port()
    pid = await _crash_run(tmp_path, port, CheckpointPoint.SUBTASK_VERIFIED, "s1", after=True)
    assert port.ran == ["s1"]
    model, _ = await _restart(tmp_path, port, ["alpha s2"])
    assert port.ran == ["s1", "s2"]
    assert model.roles.count("verifier") == 1  # s1 verdict was kept
    repo = await _repo(tmp_path)
    snap = await repo.get_snapshot(pid)
    assert snap is not None and snap.state == "completed"
    assert await repo.unfinished_plans() == ()


@pytest.mark.asyncio
async def test_blocked_step_is_persisted_and_never_runs(tmp_path: Path) -> None:
    repo = await _repo(tmp_path)

    class Failing(Port):
        async def run_read(self, plan_id: str, subtask: Subtask, session_id: str) -> ToolRunResult:
            self.ran.append(subtask.subtask_id)
            return ToolRunResult("run-1", None, None, "FileNotFoundError")

    port = Failing()
    hook = make_checkpoint_hook(repo, session_of=lambda _p: "sess")
    report = await Coordinator(Model([]), port, read_tools=READ, hook=hook).run("sess", "goal")
    assert report.state is PlanState.FAILED and port.ran == ["s1"]
    states = {c.step_id: (c.phase, c.outcome) for c in await repo.steps(report.plan_id)}
    assert states["s1"] == (Phase.SAVED, Outcome.FAILED)
    assert states["s2"] == (Phase.SAVED, Outcome.FAILED)  # blocked, closed unrun
    assert await repo.unfinished_plans() == ()


@pytest.mark.asyncio
async def test_disabled_flag_keeps_checkpoints_and_runs_nothing(tmp_path: Path) -> None:
    port = Port()
    pid = await _crash_run(tmp_path, port, CheckpointPoint.SUBTASK_DISPATCH, "s1", after=True)
    repo = await _repo(tmp_path)
    worker = ResumeWorker(
        repo, Coordinator(Model([]), port, read_tools=READ), enabled=lambda: False
    )
    assert await worker.resume_all() == {pid: "disabled"}
    assert port.ran == []
    assert len(await repo.steps(pid)) == 2


@pytest.mark.asyncio
async def test_side_effect_unknown_step_waits_for_owner_and_never_resumes(tmp_path: Path) -> None:
    repo = await _repo(tmp_path)
    plan_dict = {
        "plan_id": "p1",
        "goal": "g",
        "subtasks": [
            {
                "subtask_id": "s1",
                "title": "t",
                "capability": "file.write",
                "arguments": {},
                "depends_on": [],
                "expect": "e",
            }
        ],
        "planner_model": "cloud-x",
        "degraded": False,
    }
    await repo.put_snapshot("p1", "sess", "g", plan_dict)
    await repo.plan("p1", "s1", "file.write", {}, Effect.WRITE, plan_id="p1")
    await repo.mark_dispatched("p1", "s1")  # crash here: effect may have happened
    built = await build_resume(repo, "p1")
    assert built is not None and built.awaiting_owner == ("s1",)

    port = Port()
    worker = ResumeWorker(repo, Coordinator(Model([]), port, read_tools=READ), enabled=lambda: True)
    assert await worker.resume_all() == {"p1": "awaiting_owner"}
    assert port.ran == []
    cp = await repo.get("p1", "s1")
    assert cp is not None and cp.outcome is Outcome.UNKNOWN and cp.phase is Phase.DISPATCHED


def _companion(path: Path, port: Port, quotes: list[str]) -> object:
    from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
    from siro.adapters.models.mock import MockModel
    from siro.ports.models import Privacy
    from siro.services.agent.runs import SQLiteAgentRunRepository
    from siro.services.presentation.gateway import GatewayHub
    from siro.services.presentation.integrated import IntegratedCompanion

    def factory(runs: SQLiteAgentRunRepository) -> Coordinator:
        return Coordinator(Model(quotes), port, read_tools=READ)

    return IntegratedCompanion(
        path,
        MockModel(),
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        agent_planner_factory=factory,
    )


@pytest.mark.asyncio
async def test_integrated_flag_off_writes_no_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIRO_AGENT_PLANNER_ENABLED", "1")
    monkeypatch.delenv("SIRO_AGENT_RESUME_ENABLED", raising=False)
    port = Port()
    companion = _companion(tmp_path, port, ["alpha s1", "alpha s2"])
    report = await companion.run_agent_plan("sess", "goal")  # type: ignore[attr-defined]
    assert report is not None and report.state is PlanState.COMPLETED
    assert companion._resume_task is None and companion._checkpoints is None  # type: ignore[attr-defined]
    repo = await _repo(tmp_path)
    assert await repo.unfinished_plans() == () and await repo.get_snapshot(report.plan_id) is None


@pytest.mark.asyncio
async def test_integrated_flag_on_records_and_resumes_after_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIRO_AGENT_PLANNER_ENABLED", "1")
    monkeypatch.setenv("SIRO_AGENT_RESUME_ENABLED", "1")
    port = Port(crash_after_tool="s2")  # s1 finishes, process dies during s2
    first = _companion(tmp_path, port, ["alpha s1", "alpha s2"])
    with pytest.raises(CrashPoint):
        await first.run_agent_plan("sess", "goal")  # type: ignore[attr-defined]
    assert port.ran == ["s1", "s2"]
    repo = await _repo(tmp_path)
    (snap,) = await repo.unfinished_plans()
    assert snap.session_id == "sess"

    second = _companion(tmp_path, port, ["alpha s2"])  # restart on the same data dir
    await second._ensure_core()  # type: ignore[attr-defined]
    task = second._resume_task  # type: ignore[attr-defined]
    assert task is not None
    await task
    assert port.ran == ["s1", "s2", "s2"]  # s1 not repeated; read-only s2 re-read once
    done = await repo.get_snapshot(snap.plan_id)
    assert done is not None and done.state == "completed"
    assert all(
        c.phase is Phase.SAVED and c.outcome is Outcome.SUCCESS
        for c in await repo.steps(snap.plan_id)
    )
