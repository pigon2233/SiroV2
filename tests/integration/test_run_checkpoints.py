"""R06: checkpoints survive a crash at each boundary with zero duplicate side effects."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from checkpoint_crash import (
    AFTER_EFFECT,
    AFTER_SAVE,
    BEFORE_DISPATCH,
    CrashPoint,
    World,
    resume,
    run_step,
)

from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.checkpoints import (
    CheckpointError,
    DuplicateDispatch,
    Effect,
    Outcome,
    Phase,
    ResumeAction,
    SQLiteCheckpointRepository,
)

RUN = "run-1"


async def _open(path: Path) -> SQLiteCheckpointRepository:
    store = SQLiteStore(path / "siro.db")
    await store.initialize()
    return SQLiteCheckpointRepository(store)


async def _crash(path: Path, world: World, effect: Effect, point: str) -> None:
    repo = await _open(path)
    with pytest.raises(CrashPoint):
        await run_step(repo, world, RUN, "s1", effect, crash_at=point)


@pytest.mark.asyncio
@pytest.mark.parametrize("effect", [Effect.READ, Effect.WRITE])
async def test_crash_before_dispatch_runs_exactly_once(tmp_path: Path, effect: Effect) -> None:
    world = World()
    await _crash(tmp_path, world, effect, BEFORE_DISPATCH)
    assert world.executions == 0
    repo = await _open(tmp_path)  # restart
    actions = await resume(repo, world, RUN, readback=False)
    assert actions == {"s1": ResumeAction.RUN}
    assert world.executions == 1
    cp = await repo.get(RUN, "s1")
    assert cp is not None and cp.phase is Phase.SAVED and cp.outcome is Outcome.SUCCESS
    assert await resume(repo, world, RUN, readback=False) == {"s1": ResumeAction.SKIP}
    assert world.executions == 1


@pytest.mark.asyncio
async def test_crash_after_effect_read_only_reruns_safely(tmp_path: Path) -> None:
    world = World()
    await _crash(tmp_path, world, Effect.READ, AFTER_EFFECT)
    assert world.executions == 1
    repo = await _open(tmp_path)
    assert await resume(repo, world, RUN, readback=False) == {"s1": ResumeAction.RUN}
    cp = await repo.get(RUN, "s1")
    assert cp is not None and cp.phase is Phase.SAVED and cp.outcome is Outcome.SUCCESS


@pytest.mark.asyncio
async def test_crash_after_effect_write_without_readback_waits_for_owner(tmp_path: Path) -> None:
    world = World()
    await _crash(tmp_path, world, Effect.WRITE, AFTER_EFFECT)
    repo = await _open(tmp_path)
    assert await resume(repo, world, RUN, readback=False) == {"s1": ResumeAction.AWAIT_OWNER}
    assert world.executions == 1  # no duplicate
    cp = await repo.get(RUN, "s1")
    assert cp is not None and cp.outcome is Outcome.UNKNOWN and cp.phase is Phase.DISPATCHED
    # a second restart changes nothing and still never claims success
    repo2 = await _open(tmp_path)
    assert await resume(repo2, world, RUN, readback=False) == {"s1": ResumeAction.AWAIT_OWNER}
    cp = await repo2.get(RUN, "s1")
    assert cp is not None and cp.outcome is Outcome.UNKNOWN and world.executions == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("effect", [Effect.WRITE, Effect.UNKNOWN_CLASS])
async def test_crash_after_effect_write_with_readback_adopts_real_result(
    tmp_path: Path, effect: Effect
) -> None:
    world = World()
    await _crash(tmp_path, world, effect, AFTER_EFFECT)
    repo = await _open(tmp_path)
    assert await resume(repo, world, RUN, readback=True) == {"s1": ResumeAction.READBACK}
    assert world.executions == 1 and world.readbacks == 1
    cp = await repo.get(RUN, "s1")
    assert cp is not None and cp.outcome is Outcome.SUCCESS and cp.resolved_by == "readback"
    assert cp.phase is Phase.SAVED


@pytest.mark.asyncio
async def test_readback_that_finds_nothing_stays_unknown(tmp_path: Path) -> None:
    world = World()
    await _crash(tmp_path, world, Effect.WRITE, AFTER_EFFECT)
    world.applied.clear()  # the external system has no trace of it
    repo = await _open(tmp_path)
    await resume(repo, world, RUN, readback=True)
    cp = await repo.get(RUN, "s1")
    assert cp is not None and cp.outcome is Outcome.UNKNOWN
    assert world.executions == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("effect", [Effect.READ, Effect.WRITE])
async def test_crash_after_save_is_not_repeated(tmp_path: Path, effect: Effect) -> None:
    world = World()
    await _crash(tmp_path, world, effect, AFTER_SAVE)
    repo = await _open(tmp_path)
    assert await resume(repo, world, RUN, readback=True) == {"s1": ResumeAction.SKIP}
    assert world.executions == 1 and world.readbacks == 0


@pytest.mark.asyncio
async def test_acked_but_unsaved_result_is_adopted_not_rerun(tmp_path: Path) -> None:
    world = World()
    repo = await _open(tmp_path)
    cp = await repo.plan(RUN, "s1", "demo.tool", {"n": "s1"}, Effect.WRITE)
    await repo.mark_dispatched(RUN, "s1")
    await repo.ack(RUN, "s1", Outcome.SUCCESS, world.execute(cp.idempotency_key, "s1"))
    repo = await _open(tmp_path)
    assert await resume(repo, world, RUN, readback=False) == {"s1": ResumeAction.ADOPT}
    assert world.executions == 1


@pytest.mark.asyncio
async def test_remaining_read_steps_continue_after_crash(tmp_path: Path) -> None:
    world = World()
    repo = await _open(tmp_path)
    await run_step(repo, world, RUN, "s1", Effect.READ)
    with pytest.raises(CrashPoint):
        await run_step(repo, world, RUN, "s2", Effect.READ, crash_at=BEFORE_DISPATCH)
    await repo.plan(RUN, "s3", "demo.tool", {"n": "s3"}, Effect.READ)
    repo = await _open(tmp_path)
    actions = await resume(repo, world, RUN, readback=False)
    assert actions == {"s1": ResumeAction.SKIP, "s2": ResumeAction.RUN, "s3": ResumeAction.RUN}
    assert world.executions == 3  # s1 once, s2 once, s3 once
    assert all(c.phase is Phase.SAVED for c in await repo.steps(RUN))


@pytest.mark.asyncio
async def test_unknown_can_never_become_success_by_ack_or_reconcile(tmp_path: Path) -> None:
    world = World()
    await _crash(tmp_path, world, Effect.WRITE, AFTER_EFFECT)
    repo = await _open(tmp_path)
    await repo.reconcile(RUN)
    with pytest.raises(CheckpointError):
        await repo.ack(RUN, "s1", Outcome.SUCCESS, {"ok": 1})  # plain ack on unknown
    with pytest.raises(CheckpointError):
        await repo.resolve_unknown(RUN, "s1", Outcome.SUCCESS, {}, by="model")
    with pytest.raises(CheckpointError):
        await repo.rearm_read(RUN, "s1")  # side-effect steps are never re-armed
    with pytest.raises(DuplicateDispatch):
        await repo.mark_dispatched(RUN, "s1")
    cp = await repo.get(RUN, "s1")
    assert cp is not None and cp.outcome is Outcome.UNKNOWN
    await repo.reconcile(RUN)  # idempotent
    await repo.resolve_unknown(RUN, "s1", Outcome.SUCCESS, {"ok": 1}, by="owner")
    cp = await repo.get(RUN, "s1")
    assert cp is not None and cp.outcome is Outcome.SUCCESS and cp.resolved_by == "owner"


@pytest.mark.asyncio
async def test_plan_is_idempotent_and_conflict_refused(tmp_path: Path) -> None:
    repo = await _open(tmp_path)
    a = await repo.plan(RUN, "s1", "demo.tool", {"n": 1}, Effect.READ)
    b = await repo.plan(RUN, "s1", "demo.tool", {"n": 1}, Effect.READ)
    assert a == b
    with pytest.raises(CheckpointError):
        await repo.plan(RUN, "s1", "demo.tool", {"n": 2}, Effect.READ)
    with pytest.raises(CheckpointError):
        await repo.plan(RUN, "s1", "demo.tool", {"n": 1}, Effect.WRITE)


@pytest.mark.asyncio
async def test_double_dispatch_is_refused(tmp_path: Path) -> None:
    repo = await _open(tmp_path)
    await repo.plan(RUN, "s1", "demo.tool", {}, Effect.WRITE)
    await repo.mark_dispatched(RUN, "s1")
    with pytest.raises(DuplicateDispatch):
        await repo.mark_dispatched(RUN, "s1")
