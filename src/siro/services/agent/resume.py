"""R06 adapters between the R05 plan coordinator and durable checkpoints.

hook:   PlanCheckpoint (R05) -> run_checkpoints rows
resume: run_checkpoints rows -> PlanCheckpoint snapshot for ``coordinator.run(resume=...)``

R05 types are imported lazily so this module (and the storage layer) does not depend on
R05 being merged. Mapping: checkpoint run_id = plan_id, step_id = subtask_id.
"""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from siro.services.agent.checkpoints import (
    Checkpoint,
    CheckpointError,
    Effect,
    Outcome,
    Phase,
    ResumeAction,
    SQLiteCheckpointRepository,
)

if TYPE_CHECKING:
    from siro.services.agent.planning import PlanCheckpoint, SubtaskResult

# Set by the entry point so the hook can record which session owns a new plan.
CURRENT_SESSION: ContextVar[str] = ContextVar("siro_plan_session", default="")

_UNKNOWN_ERRORS = ("outcome_unknown", "prior_outcome_unknown")


def resume_enabled(env: dict[str, str] | None = None, *, default: str = "0") -> bool:
    return (env if env is not None else os.environ).get("SIRO_AGENT_RESUME_ENABLED", default) == "1"


def _dump(value: object) -> Any:
    return json.loads(json.dumps(asdict(value), ensure_ascii=False, default=str))  # type: ignore[call-overload]


def _decode_result(data: dict[str, Any]) -> SubtaskResult:
    from siro.services.agent.planning import Source, SubtaskResult, SubtaskState, Verdict

    verdict = data.get("verdict")
    return SubtaskResult(
        data["subtask_id"],
        SubtaskState(data["state"]),
        data.get("run_id"),
        data.get("proposal_id"),
        data.get("observation"),
        tuple(Source(**s) for s in data.get("sources") or ()),
        None
        if verdict is None
        else Verdict(
            verdict["verified"],
            verdict["reason"],
            tuple(verdict["quotes"]),
            verdict["verifier_model"],
            verdict["degraded"],
        ),
        data.get("error"),
    )


def _decode_plan(data: dict[str, Any]) -> Any:
    from siro.services.agent.planning import Plan, Subtask

    return Plan(
        data["plan_id"],
        data["goal"],
        tuple(
            Subtask(
                s["subtask_id"],
                s["title"],
                s["capability"],
                s["arguments"],
                tuple(s["depends_on"]),
                s["expect"],
            )
            for s in data["subtasks"]
        ),
        data["planner_model"],
        data["degraded"],
    )


def _current_subtask(cp: PlanCheckpoint) -> str | None:
    """Prefer an explicit subtask_id (R05 may add it); otherwise infer from the snapshot."""
    explicit = getattr(cp, "subtask_id", None)
    if explicit is not None:
        return str(explicit)
    if cp.point.value == "subtask_dispatch":
        if cp.plan is None:
            return None
        seen = {r.subtask_id for r in cp.results}
        return next((s.subtask_id for s in cp.plan.subtasks if s.subtask_id not in seen), None)
    return cp.results[-1].subtask_id if cp.results else None


def make_checkpoint_hook(
    repo: SQLiteCheckpointRepository,
    *,
    session_of: Callable[[str], str] = lambda _plan_id: CURRENT_SESSION.get(),
) -> Callable[[PlanCheckpoint], Awaitable[None]]:
    """Build the R05 ``CheckpointHook``. Checkpoints are written before the coordinator goes on."""

    async def hook(cp: PlanCheckpoint) -> None:
        point = cp.point.value
        pid = cp.plan_id
        if point == "plan_created" and cp.plan is not None:
            await repo.put_snapshot(pid, session_of(pid), cp.plan.goal, _dump(cp.plan))
            for sub in cp.plan.subtasks:
                await repo.plan(
                    pid, sub.subtask_id, sub.capability, sub.arguments, Effect.READ, plan_id=pid
                )
            return
        if point == "plan_finished":
            await repo.finish_snapshot(pid, cp.state.value)
            return
        sid = _current_subtask(cp)
        if sid is None:
            return
        if point == "subtask_dispatch":
            await repo.mark_dispatched(pid, sid)
            return
        result = next(r for r in cp.results if r.subtask_id == sid)
        if point == "subtask_blocked":
            await repo.close_unrun(pid, sid, result.error or "blocked")
        elif point == "subtask_observed":
            await repo.ack(pid, sid, Outcome.SUCCESS, _dump(result))
        elif point == "subtask_verified":
            current = await repo.get(pid, sid)
            if current is None or current.phase is Phase.SAVED:
                return
            if current.phase is Phase.DISPATCHED:
                if result.error in _UNKNOWN_ERRORS:
                    await repo.reconcile(pid)  # dispatched without a result -> unknown
                    return
                await repo.ack(pid, sid, Outcome.FAILED, _dump(result))
            await repo.save(pid, sid, _dump(result))

    return hook


@dataclass(frozen=True, slots=True)
class ResumePlan:
    session_id: str
    goal: str
    checkpoint: PlanCheckpoint
    awaiting_owner: tuple[str, ...]  # side-effect steps with unknown outcome: do not resume


def _saved_result(cp: Checkpoint) -> SubtaskResult:
    from siro.services.agent.planning import SubtaskResult, SubtaskState

    payload = cp.observation
    if isinstance(payload, dict) and "subtask_id" in payload:
        return _decode_result(payload)
    reason = payload.get("error") if isinstance(payload, dict) else None
    return SubtaskResult(cp.step_id, SubtaskState.BLOCKED, error=str(reason or "blocked"))


async def build_resume(
    repo: SQLiteCheckpointRepository,
    plan_id: str,
    *,
    has_readback: Callable[[str], bool] = lambda _c: False,
) -> ResumePlan | None:
    """Rebuild a resume snapshot. Re-arms unknown read-only steps; never runs anything."""
    from siro.services.agent.planning import PlanCheckpoint, PlanState

    snap = await repo.get_snapshot(plan_id)
    if snap is None or snap.state not in {"planning", "running"}:
        return None
    await repo.reconcile(plan_id)
    plan = _decode_plan(snap.snapshot)  # type: ignore[arg-type]
    steps = {cp.step_id: cp for cp in await repo.steps(plan_id)}
    actions = {
        s.step_id: s.action for s in await repo.resume_plan(plan_id, has_readback=has_readback)
    }
    results: list[SubtaskResult] = []
    owner: list[str] = []
    for sub in plan.subtasks:
        cp = steps.get(sub.subtask_id)
        action = actions.get(sub.subtask_id)
        if cp is None or action is None:
            continue  # never planned: the coordinator treats it as new
        if action is ResumeAction.SKIP:
            results.append(_saved_result(cp))
        elif action is ResumeAction.ADOPT:
            results.append(_decode_result(cp.observation))  # type: ignore[arg-type]
        elif action is ResumeAction.RUN:
            if cp.phase is Phase.DISPATCHED:
                try:
                    await repo.rearm_read(plan_id, cp.step_id)  # read-only only
                except CheckpointError:
                    owner.append(cp.step_id)
        else:
            owner.append(cp.step_id)
    checkpoint = PlanCheckpoint(
        plan_id,
        _point("subtask_dispatch"),
        PlanState.RUNNING,
        plan,
        tuple(results),
    )
    return ResumePlan(snap.session_id, snap.goal, checkpoint, tuple(owner))


def _point(name: str) -> Any:
    from siro.services.agent.planning import CheckpointPoint

    return CheckpointPoint(name)


class ResumeWorker:
    """Resumes unfinished plans after a restart, only behind SIRO_AGENT_RESUME_ENABLED."""

    def __init__(
        self,
        repo: SQLiteCheckpointRepository,
        coordinator: Any,
        *,
        has_readback: Callable[[str], bool] = lambda _c: False,
        enabled: Callable[[], bool] = resume_enabled,
    ) -> None:
        self._repo, self._coordinator = repo, coordinator
        self._has_readback, self._enabled = has_readback, enabled

    async def resume_all(self) -> dict[str, str]:
        """plan_id -> 'resumed' | 'awaiting_owner' | 'disabled'. Checkpoints are kept either way."""
        await self._repo.reconcile()
        plans = await self._repo.unfinished_plans()
        outcome: dict[str, str] = {}
        for snap in plans:
            if not self._enabled():
                outcome[snap.plan_id] = "disabled"
                continue
            built = await build_resume(self._repo, snap.plan_id, has_readback=self._has_readback)
            if built is None:
                continue
            if built.awaiting_owner:
                outcome[snap.plan_id] = "awaiting_owner"
                continue
            await self._coordinator.run(built.session_id, built.goal, resume=built.checkpoint)
            outcome[snap.plan_id] = "resumed"
        return outcome
