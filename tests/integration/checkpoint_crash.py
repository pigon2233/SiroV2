"""Crash-injection harness for R06 checkpoints.

A "crash" is a CrashPoint raised at a phase boundary; the test then discards all in-memory
state and reopens the same SQLite file, exactly like a process restart.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from siro.services.agent.checkpoints import (
    Effect,
    Outcome,
    ResumeAction,
    SQLiteCheckpointRepository,
    idempotency_key,
)


class CrashPoint(BaseException):
    """BaseException so no handler in the code under test can swallow the crash."""


BEFORE_DISPATCH = "before_dispatch"  # planned, nothing sent
AFTER_EFFECT = "after_effect"  # effect happened, result not yet acknowledged
AFTER_SAVE = "after_save"  # result acknowledged and saved


@dataclass
class World:
    """The external system: counts real side effects, shared across simulated restarts."""

    applied: dict[str, object] = field(default_factory=dict)  # idempotency_key -> result
    executions: int = 0
    readbacks: int = 0

    def execute(self, key: str, value: object) -> object:
        self.executions += 1
        self.applied[key] = value
        return {"ok": value}

    def read_back(self, key: str) -> object | None:
        self.readbacks += 1
        return {"ok": self.applied[key]} if key in self.applied else None


async def run_step(
    repo: SQLiteCheckpointRepository,
    world: World,
    run_id: str,
    step_id: str,
    effect: Effect,
    *,
    crash_at: str | None = None,
) -> None:
    cp = await repo.plan(run_id, step_id, "demo.tool", {"n": step_id}, effect)
    if crash_at == BEFORE_DISPATCH:
        raise CrashPoint(crash_at)
    await repo.mark_dispatched(run_id, step_id)
    observation = world.execute(cp.idempotency_key, step_id)
    if crash_at == AFTER_EFFECT:
        raise CrashPoint(crash_at)
    await repo.ack(run_id, step_id, Outcome.SUCCESS, observation)
    await repo.save(run_id, step_id)
    if crash_at == AFTER_SAVE:
        raise CrashPoint(crash_at)


async def resume(
    repo: SQLiteCheckpointRepository,
    world: World,
    run_id: str,
    *,
    readback: bool,
) -> dict[str, ResumeAction]:
    """What a restart does: reconcile (runs nothing), then act per the resume plan."""
    await repo.reconcile(run_id)
    done: dict[str, ResumeAction] = {}
    for step in await repo.resume_plan(run_id, has_readback=lambda _c: readback):
        cp = await repo.get(run_id, step.step_id)
        assert cp is not None
        done[step.step_id] = step.action
        if step.action is ResumeAction.ADOPT:
            await repo.save(run_id, step.step_id)
        elif step.action is ResumeAction.RUN:
            if cp.phase.value == "dispatched":  # unknown read-only: allowed to run again
                await repo.rearm_read(run_id, step.step_id)
            await repo.mark_dispatched(run_id, step.step_id)
            result = world.execute(cp.idempotency_key, step.step_id)
            await repo.ack(run_id, step.step_id, Outcome.SUCCESS, result)
            await repo.save(run_id, step.step_id)
        elif step.action is ResumeAction.READBACK:
            found = world.read_back(
                idempotency_key(run_id, step.step_id, cp.capability, cp.arguments)
            )
            if found is not None:
                await repo.resolve_unknown(
                    run_id, step.step_id, Outcome.SUCCESS, found, by="readback"
                )
                await repo.save(run_id, step.step_id)
            # not found: stays unknown; never guessed
    return done
