"""R05 contract: bounded plan, subtasks, results and checkpoint snapshots."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Protocol

MAX_SUBTASKS = 3


class PlanState(StrEnum):
    PLANNING = "planning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubtaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    VERIFIED = "verified"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class CheckpointPoint(StrEnum):
    PLAN_CREATED = "plan_created"
    SUBTASK_DISPATCH = "subtask_dispatch"
    SUBTASK_OBSERVED = "subtask_observed"
    SUBTASK_VERIFIED = "subtask_verified"
    SUBTASK_BLOCKED = "subtask_blocked"
    PLAN_FINISHED = "plan_finished"


class PlanError(ValueError):
    """The planner output is not an acceptable bounded read-only plan."""


@dataclass(frozen=True, slots=True)
class Subtask:
    subtask_id: str
    title: str
    capability: str
    arguments: dict[str, object]
    depends_on: tuple[str, ...]
    expect: str


@dataclass(frozen=True, slots=True)
class Plan:
    plan_id: str
    goal: str
    subtasks: tuple[Subtask, ...]
    planner_model: str
    degraded: bool


@dataclass(frozen=True, slots=True)
class Source:
    capability: str
    ref: str
    excerpt: str


@dataclass(frozen=True, slots=True)
class Verdict:
    verified: bool
    reason: str
    quotes: tuple[str, ...]
    verifier_model: str
    degraded: bool


@dataclass(frozen=True, slots=True)
class SubtaskResult:
    subtask_id: str
    state: SubtaskState
    run_id: str | None = None
    proposal_id: str | None = None
    observation: object | None = None
    sources: tuple[Source, ...] = ()
    verdict: Verdict | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PlanReport:
    plan_id: str
    state: PlanState
    results: tuple[SubtaskResult, ...]
    summary: str
    models: tuple[str, ...]
    degraded: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


@dataclass(frozen=True, slots=True)
class PlanCheckpoint:
    plan_id: str
    point: CheckpointPoint
    state: PlanState
    plan: Plan | None
    results: tuple[SubtaskResult, ...]
    subtask_id: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


@dataclass(frozen=True, slots=True)
class ModelReply:
    text: str
    model_name: str


@dataclass(frozen=True, slots=True)
class ToolRunResult:
    run_id: str | None
    proposal_id: str | None
    observation: object | None
    error: str | None = None


class PlannerModel(Protocol):
    """role is planner | verifier | reporter; implementations must use cloud privacy."""

    async def complete(self, role: str, prompt: str) -> ModelReply: ...


class SubtaskToolPort(Protocol):
    async def run_read(self, plan_id: str, subtask: Subtask, session_id: str) -> ToolRunResult: ...

    async def cancel(self, plan_id: str) -> None: ...


CheckpointHook = Callable[[PlanCheckpoint], Awaitable[None]]
