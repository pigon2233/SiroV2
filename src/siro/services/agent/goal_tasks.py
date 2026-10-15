"""One owned, explicitly approved durable document task; no generic agent scheduler."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

from siro.core.cognition import ActionCandidate, Clock, Goal, GoalService, GoalState, Planner
from siro.core.goal_tasks import DocumentObservation, GoalTask, observe_document
from siro.persistence.goals import SQLiteGoalRepository
from siro.persistence.planning import SQLitePlanningRepository
from siro.persistence.sqlite import SQLiteStore
from siro.services.tools.execution import ExecutionCancelled, ExecutionContext

READ_TIMEOUT_SECONDS = 10.0
TERMINAL = frozenset({GoalState.COMPLETED, GoalState.FAILED, GoalState.CANCELLED})


class ReadWorkspace(Protocol):
    root: Path

    @property
    def available(self) -> bool: ...
    async def execute(
        self, capability: str, arguments: dict[str, object], context: ExecutionContext
    ) -> object: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class GoalTaskError(RuntimeError):
    def __init__(self, code: str, status: int = 409) -> None:
        self.code, self.status = code, status
        super().__init__(code)


async def _joined[T](operation: Awaitable[T]) -> T:
    """Keep this caller's SQLite transaction/lock alive until its real IO finishes."""
    owned = asyncio.ensure_future(operation)
    cancelled = False
    while not owned.done():
        try:
            await asyncio.shield(owned)
        except asyncio.CancelledError:
            cancelled = True
    result = owned.result()
    if cancelled:
        raise asyncio.CancelledError
    return result


def _view(goal: Goal) -> dict[str, object]:
    assert goal.task is not None
    return {
        "goal_id": goal.goal_id,
        "state": goal.state.value,
        "next_step": goal.next_step,
        "revision": goal.revision,
        "steps_used": goal.steps_used,
        "max_steps": goal.max_steps,
        "deadline": goal.deadline.isoformat() if goal.deadline is not None else None,
        "task": goal.task.model_dump(mode="json", exclude={"owner_session_id", "workspace"}),
    }


class ReadTaskOwner:
    def __init__(
        self,
        store: SQLiteStore,
        workspace: ReadWorkspace,
        *,
        busy: Callable[[], bool],
        allowed: Callable[[], bool],
        clock: Clock | None = None,
    ) -> None:
        self._workspace, self._busy, self._allowed = workspace, busy, allowed
        self._clock = clock or SystemClock()
        self._repository = SQLiteGoalRepository(store)
        self._goals = GoalService(self._repository, self._clock)
        self._planner = Planner(SQLitePlanningRepository(store), self._clock)
        self._control = asyncio.Lock()
        self._work: asyncio.Task[None] | None = None
        self._context: ExecutionContext | None = None
        self._active: str | None = None
        self._reason = "paused"
        self._started = False
        self._epoch = 0

    @property
    def busy(self) -> bool:
        return self._work is not None and not self._work.done()

    @property
    def available(self) -> bool:
        return self._started and self._allowed() and self._workspace.available

    def _ready(self) -> None:
        if not self._started:
            raise GoalTaskError("unavailable", 503)

    async def start(self) -> None:
        if self._started:
            return
        # Composition initializes the existing store; GET never migrates it.
        try:
            for goal in await _joined(self._repository.tasks()):
                if goal.state in {GoalState.RUNNING, GoalState.READY}:
                    await self._paused(goal.goal_id, "interrupted_restart")
        except ValueError:
            # Invalid optional task metadata disables this caller, preserving existing chat.
            return
        self._started = True

    async def _required(self, owner: str, goal_id: str, revision: int | None = None) -> Goal:
        self._ready()
        goal = await _joined(self._repository.get(goal_id))
        if goal is None or goal.task is None or goal.task.owner_session_id != owner:
            raise GoalTaskError("not_found", 404)
        if revision is not None and (type(revision) is not int or goal.revision != revision):
            raise GoalTaskError("conflict")
        return goal

    def _scope(self, goal: Goal) -> None:
        if not self.available:
            raise GoalTaskError("unavailable", 503)
        assert goal.task is not None
        if goal.task.workspace != str(self._workspace.root):
            raise GoalTaskError("scope_changed")

    async def propose(self, owner: str, paths: tuple[str, ...]) -> dict[str, object]:
        async with self._control:
            self._ready()
            if not self.available:
                raise GoalTaskError("unavailable", 503)
            try:
                task = GoalTask(
                    owner_session_id=owner, workspace=str(self._workspace.root), paths=paths
                )
            except ValueError as error:
                raise GoalTaskError("invalid_task", 422) from error
            goal = Goal(
                str(uuid4()),
                GoalState.PROPOSED,
                task.paths[0],
                self._clock.now() + timedelta(hours=24),
                max_steps=8,
                task=task,
            )
            try:
                await _joined(self._goals.propose(goal))
            except OverflowError as error:
                raise GoalTaskError("history_full", 429) from error
            return _view(goal)

    async def approve(self, owner: str, goal_id: str, revision: int) -> dict[str, object]:
        async with self._control:
            goal = await self._required(owner, goal_id, revision)
            self._scope(goal)
            if self.busy:
                raise GoalTaskError("busy")
            if goal.state is not GoalState.PROPOSED:
                raise GoalTaskError("conflict")
            epoch = self._epoch
            updated = await _joined(self._goals.approve_task(goal_id, expected_revision=revision))
            if epoch != self._epoch:
                await self._paused(goal_id, self._reason)
                return _view(await self._required(owner, goal_id))
            self._scope(updated)
            self._launch(updated)
            return _view(updated)

    async def resume(self, owner: str, goal_id: str, revision: int) -> dict[str, object]:
        async with self._control:
            goal = await self._required(owner, goal_id, revision)
            self._scope(goal)
            if self.busy:
                raise GoalTaskError("busy")
            if goal.state is not GoalState.WAITING_EXTERNAL:
                raise GoalTaskError("terminal" if goal.state in TERMINAL else "conflict")
            if goal.task is None or goal.task.approved_at is None:
                raise GoalTaskError("not_approved")
            epoch = self._epoch
            updated = await _joined(self._goals.transition(goal_id, GoalState.READY))
            if epoch != self._epoch:
                await self._paused(goal_id, self._reason)
                return _view(await self._required(owner, goal_id))
            self._scope(updated)
            self._launch(updated)
            return _view(updated)

    def _launch(self, goal: Goal) -> None:
        assert goal.task is not None
        self._active, self._reason = goal.goal_id, "paused"
        self._context = ExecutionContext(
            goal.goal_id, goal.task.owner_session_id, str(uuid4()), authorized=True
        )
        self._work = asyncio.create_task(self._run(goal.goal_id), name="siro-approved-read-task")
        self._work.add_done_callback(lambda work: None if work.cancelled() else work.exception())

    async def _paused(self, goal_id: str, reason: str) -> None:
        goal = await _joined(self._repository.get(goal_id))
        if goal is None or goal.task is None or goal.state in TERMINAL:
            return
        if goal.state is GoalState.READY:
            goal = await _joined(self._goals.transition(goal_id, GoalState.RUNNING))
        if goal.state is GoalState.RUNNING:
            assert goal.task is not None
            task = GoalTask.model_validate_json(
                goal.task.model_copy(update={"pause_reason": reason}).model_dump_json()
            )
            await _joined(self._goals.checkpoint_task(goal_id, task, next_step=goal.next_step))
            await _joined(self._goals.transition(goal_id, GoalState.WAITING_EXTERNAL))

    async def _stop(self, reason: str) -> None:
        self._reason = reason
        if self._context is not None:
            self._context.cancellation.cancel()
        work = self._work
        if work is not None and not work.done():
            if not work.cancelling():
                work.cancel()
            # The owned job catches cancellation, joins started DB work and persists pause.
            await _joined(asyncio.gather(work, return_exceptions=True))
        self._work, self._context, self._active = None, None, None

    async def foreground(self, reason: str = "foreground") -> None:
        self._epoch += 1
        self._reason = reason
        if self._context is not None:
            self._context.cancellation.cancel()
        if self._work is not None and not self._work.done() and not self._work.cancelling():
            self._work.cancel()
        async with self._control:
            await self._stop(reason)

    async def pause(
        self, owner: str, goal_id: str, revision: int | None = None
    ) -> dict[str, object]:
        async with self._control:
            goal = await self._required(owner, goal_id)
            if goal.state in TERMINAL:
                return _view(goal)
            if self._active == goal_id:
                await self._stop("paused")
            elif goal.state is not GoalState.PROPOSED:
                await self._paused(goal_id, "paused")
            return _view(await self._required(owner, goal_id))

    async def cancel(
        self, owner: str, goal_id: str, revision: int | None = None
    ) -> dict[str, object]:
        async with self._control:
            goal = await self._required(owner, goal_id)
            if self._active == goal_id:
                await self._stop("paused")
                goal = await self._required(owner, goal_id)
            if goal.state not in TERMINAL:
                goal = await _joined(self._goals.transition(goal_id, GoalState.CANCELLED))
            return _view(goal)

    async def remove(self, owner: str, goal_id: str, revision: int) -> bool:
        async with self._control:
            goal = await self._required(owner, goal_id, revision)
            if goal.state not in TERMINAL or (self._active == goal_id and self.busy):
                raise GoalTaskError("conflict")
            return await _joined(self._repository.remove_task(goal_id, owner, revision))

    async def snapshot(self, owner: str) -> dict[str, object]:
        self._ready()
        goals = await _joined(self._repository.tasks(owner))
        return {
            "available": self.available,
            "profile": "document-checklist-v1",
            "max_tasks": 20,
            "active_goal_id": self._active
            if self.busy and any(goal.goal_id == self._active for goal in goals)
            else None,
            "goals": [_view(goal) for goal in goals],
        }

    async def close(self) -> None:
        self._started = False
        self._epoch += 1
        self._reason = "shutdown"
        if self._context is not None:
            self._context.cancellation.cancel()
        if self._work is not None and not self._work.done() and not self._work.cancelling():
            self._work.cancel()
        async with self._control:
            await self._stop("shutdown")

    async def _run(self, goal_id: str) -> None:
        context = self._context
        assert context is not None
        try:
            goal = await _joined(self._goals.transition(goal_id, GoalState.RUNNING))
            assert goal.task is not None
            for path in goal.task.paths:
                loaded = await _joined(self._repository.get(goal_id))
                assert loaded is not None and loaded.task is not None
                goal = loaded
                assert goal.task is not None
                if any(item.path == path for item in goal.task.observations):
                    continue
                context.check()
                if not self._allowed():
                    await self._paused(goal_id, "tools_disabled")
                    return
                self._scope(goal)
                candidate = ActionCandidate(
                    "read:" + path,
                    "filesystem.read",
                    {"path": path},
                    "actual UTF-8 readback and source lines",
                    0,
                    goal.deadline,
                    1,
                    ("owner-approved exact document",),
                    permission_allowed=goal.task.approved_at is not None,
                    busy_allowed=not self._busy(),
                )
                none = ActionCandidate(
                    "none", "none", {}, "keep pending", 0, None, 0, ("foreground first",)
                )
                decision = await _joined(self._planner.plan(goal_id, (candidate,), none))
                if decision.selected_candidate_id == "none":
                    await self._paused(goal_id, "foreground")
                    return
                goal = await _joined(self._goals.spend(goal_id, cost=0))
                if goal.state is GoalState.FAILED:
                    return
                assert goal.task is not None
                task = goal.task.model_copy(update={"intent_path": path, "pause_reason": None})
                goal = await _joined(self._goals.checkpoint_task(goal_id, task, next_step=path))
                context.check()
                if not self._allowed():
                    await self._paused(goal_id, "tools_disabled")
                    return
                self._scope(goal)
                try:
                    attempt_context = replace(
                        context, deadline=asyncio.get_running_loop().time() + READ_TIMEOUT_SECONDS
                    )
                    async with asyncio.timeout(READ_TIMEOUT_SECONDS):
                        result = await self._workspace.execute(
                            "filesystem.read", {"path": path}, attempt_context
                        )
                    attempt_context.check()
                    if (
                        not isinstance(result, dict)
                        or set(result) != {"text"}
                        or not isinstance(result["text"], str)
                    ):
                        raise ValueError("invalid_result")
                    observation = observe_document(path, result["text"], self._clock.now())
                except ExecutionCancelled as error:
                    raise asyncio.CancelledError from error
                except (OSError, ValueError, PermissionError, TimeoutError, RuntimeError) as error:
                    code: Literal["path_denied", "timeout", "invalid_result", "read_failed"] = (
                        "path_denied"
                        if isinstance(error, PermissionError)
                        else "timeout"
                        if isinstance(error, TimeoutError)
                        else "invalid_result"
                        if isinstance(error, ValueError)
                        else "read_failed"
                    )
                    observation = DocumentObservation(
                        path=path, status="failed", read_at=self._clock.now(), error=code
                    )
                assert goal.task is not None
                updated = goal.task.model_copy(
                    update={
                        "intent_path": None,
                        "observations": (*goal.task.observations, observation),
                    }
                )
                following = next(
                    (
                        name
                        for name in goal.task.paths
                        if name != path
                        and not any(item.path == name for item in goal.task.observations)
                    ),
                    None,
                )
                goal = await _joined(
                    self._goals.checkpoint_task(goal_id, updated, next_step=following)
                )
                context.check()
                if observation.status == "failed":
                    await _joined(self._goals.transition(goal_id, GoalState.FAILED))
                    return
            context.check()
            final = await _joined(self._repository.get(goal_id))
            assert final is not None and final.task is not None
            verified = len(final.task.observations) == len(final.task.paths) and all(
                item.status == "completed" for item in final.task.observations
            )
            await _joined(
                self._goals.transition(
                    goal_id, GoalState.COMPLETED if verified else GoalState.FAILED
                )
            )
        except asyncio.CancelledError:
            await self._paused(goal_id, self._reason)
        except ExecutionCancelled:
            await self._paused(goal_id, self._reason)
        except GoalTaskError as error:
            if error.code == "unavailable":
                await self._paused(
                    goal_id, "tools_disabled" if not self._allowed() else self._reason
                )
            else:
                await _joined(self._goals.transition(goal_id, GoalState.FAILED))
        except Exception:
            # Corrupt/unknown metadata stays unavailable; never expose raw validation data.
            with suppress(Exception):
                failed_goal = await _joined(self._repository.get(goal_id))
                if failed_goal is not None and failed_goal.state is GoalState.RUNNING:
                    await _joined(self._goals.transition(goal_id, GoalState.FAILED))
