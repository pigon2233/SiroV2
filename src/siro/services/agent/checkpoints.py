"""Durable per-step checkpoints for safe restart continuation (R06).

A step moves planned -> dispatched -> acked -> saved and never backwards. A step that
was dispatched but has no recorded result has outcome ``unknown``; unknown is never
promoted to success except by an explicit read-back or owner resolution. Final results
are protected by the guarded UPDATE conditions below (migrations cannot hold triggers).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from siro.persistence.sqlite import SQLiteStore


class Effect(StrEnum):
    READ = "read"
    WRITE = "write"
    UNKNOWN_CLASS = "unknown_class"  # unclassified: treated as having side effects


class Phase(StrEnum):
    PLANNED = "planned"
    DISPATCHED = "dispatched"
    ACKED = "acked"
    SAVED = "saved"


class Outcome(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ResumeAction(StrEnum):
    SKIP = "skip"  # saved: nothing to do
    ADOPT = "adopt"  # result recorded but not saved: save it, never re-run
    RUN = "run"  # safe to dispatch (never dispatched, or read-only and idempotent)
    READBACK = "readback"  # side effect with unknown outcome: only query the result
    AWAIT_OWNER = "await_owner"  # side effect, unknown, no readback: owner decides


class CheckpointError(RuntimeError):
    pass


class DuplicateDispatch(CheckpointError):
    pass


@dataclass(frozen=True, slots=True)
class Checkpoint:
    run_id: str
    step_id: str
    seq: int
    plan_id: str | None
    capability: str
    arguments: object
    effect: Effect
    phase: Phase
    idempotency_key: str
    outcome: Outcome | None
    resolved_by: str | None
    observation: object | None


@dataclass(frozen=True, slots=True)
class ResumeStep:
    step_id: str
    action: ResumeAction


def idempotency_key(run_id: str, step_id: str, capability: str, arguments: object) -> str:
    canonical = json.dumps(
        [run_id, step_id, capability, arguments], sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def decide(cp: Checkpoint, *, readback_available: bool) -> ResumeAction:
    """Pure resume decision for one step."""
    if cp.phase is Phase.SAVED:
        return ResumeAction.SKIP
    if cp.phase is Phase.ACKED:
        return ResumeAction.ADOPT
    if cp.phase is Phase.PLANNED:
        return ResumeAction.RUN
    # dispatched without a recorded result: the effect may or may not have happened
    if cp.effect is Effect.READ:
        return ResumeAction.RUN
    return ResumeAction.READBACK if readback_available else ResumeAction.AWAIT_OWNER


class SQLiteCheckpointRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def plan(
        self,
        run_id: str,
        step_id: str,
        capability: str,
        arguments: object,
        effect: Effect,
        *,
        plan_id: str | None = None,
    ) -> Checkpoint:
        """Register a step. Re-planning the same step is idempotent; a changed one is refused."""
        encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
        key = idempotency_key(run_id, step_id, capability, arguments)

        def write(c: sqlite3.Connection) -> Checkpoint:
            row = self._row(c, run_id, step_id)
            if row is not None:
                if row["idempotency_key"] != key or row["effect"] != effect.value:
                    raise CheckpointError("conflicting checkpoint for step")
                return self._cp(row)
            seq = c.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM run_checkpoints WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            now = _now()
            c.execute(
                "INSERT INTO run_checkpoints(run_id,step_id,seq,plan_id,capability,"
                "arguments_json,effect,phase,idempotency_key,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,'planned',?,?,?)",
                (run_id, step_id, seq, plan_id, capability, encoded, effect.value, key, now, now),
            )
            return self._cp(self._row(c, run_id, step_id))

        return await self._store.run_transaction(write)

    async def mark_dispatched(self, run_id: str, step_id: str) -> None:
        """The dispatch boundary: recorded before the handler runs, exactly once."""

        def write(c: sqlite3.Connection) -> None:
            changed = c.execute(
                "UPDATE run_checkpoints SET phase='dispatched',updated_at=? "
                "WHERE run_id=? AND step_id=? AND phase='planned'",
                (_now(), run_id, step_id),
            ).rowcount
            if changed != 1:
                raise DuplicateDispatch("step already dispatched or unknown")

        await self._store.run_transaction(write)

    async def ack(self, run_id: str, step_id: str, outcome: Outcome, observation: object) -> None:
        """Record the effect result. Only success/failed; unknown comes from reconcile."""
        if outcome is Outcome.UNKNOWN:
            raise CheckpointError("an acknowledged result cannot be unknown")
        encoded = json.dumps(observation, ensure_ascii=False)

        def write(c: sqlite3.Connection) -> None:
            changed = c.execute(
                "UPDATE run_checkpoints SET phase='acked',outcome=?,observation_json=?,"
                "updated_at=? WHERE run_id=? AND step_id=? AND phase='dispatched' "
                "AND outcome IS NULL",
                (outcome.value, encoded, _now(), run_id, step_id),
            ).rowcount
            if changed != 1:
                raise CheckpointError("step is not awaiting an acknowledgement")

        await self._store.run_transaction(write)

    async def save(self, run_id: str, step_id: str) -> None:
        def write(c: sqlite3.Connection) -> None:
            changed = c.execute(
                "UPDATE run_checkpoints SET phase='saved',updated_at=? "
                "WHERE run_id=? AND step_id=? AND phase='acked'",
                (_now(), run_id, step_id),
            ).rowcount
            if changed != 1:
                raise CheckpointError("step has no acknowledged result to save")

        await self._store.run_transaction(write)

    async def reconcile(self, run_id: str | None = None) -> int:
        """After a restart: dispatched steps without a result become unknown. Runs nothing."""

        def write(c: sqlite3.Connection) -> int:
            sql = (
                "UPDATE run_checkpoints SET outcome='unknown',updated_at=? "
                "WHERE phase='dispatched' AND outcome IS NULL"
            )
            args: list[object] = [_now()]
            if run_id is not None:
                sql += " AND run_id=?"
                args.append(run_id)
            return c.execute(sql, args).rowcount

        return await self._store.run_transaction(write)

    async def resolve_unknown(
        self,
        run_id: str,
        step_id: str,
        outcome: Outcome,
        observation: object,
        *,
        by: str,
    ) -> None:
        """Only a read-back of the real result or an explicit owner decision may resolve."""
        if by not in {"readback", "owner"} or outcome is Outcome.UNKNOWN:
            raise CheckpointError("unknown needs a readback or owner resolution")
        encoded = json.dumps(observation, ensure_ascii=False)

        def write(c: sqlite3.Connection) -> None:
            changed = c.execute(
                "UPDATE run_checkpoints SET phase='acked',outcome=?,resolved_by=?,"
                "observation_json=?,updated_at=? WHERE run_id=? AND step_id=? "
                "AND phase='dispatched' AND outcome='unknown'",
                (outcome.value, by, encoded, _now(), run_id, step_id),
            ).rowcount
            if changed != 1:
                raise CheckpointError("step is not in an unknown state")

        await self._store.run_transaction(write)

    async def rearm_read(self, run_id: str, step_id: str) -> None:
        """Let an unknown read-only step be dispatched again. Side-effect steps are refused."""

        def write(c: sqlite3.Connection) -> None:
            changed = c.execute(
                "UPDATE run_checkpoints SET phase='planned',outcome=NULL,updated_at=? "
                "WHERE run_id=? AND step_id=? AND phase='dispatched' AND outcome='unknown' "
                "AND effect='read'",
                (_now(), run_id, step_id),
            ).rowcount
            if changed != 1:
                raise CheckpointError("only an unknown read-only step can be re-dispatched")

        await self._store.run_transaction(write)

    async def get(self, run_id: str, step_id: str) -> Checkpoint | None:
        def read(c: sqlite3.Connection) -> Checkpoint | None:
            row = self._row(c, run_id, step_id)
            return None if row is None else self._cp(row)

        return await self._store.run_transaction(read)

    async def steps(self, run_id: str) -> tuple[Checkpoint, ...]:
        def read(c: sqlite3.Connection) -> tuple[Checkpoint, ...]:
            rows = c.execute(
                "SELECT * FROM run_checkpoints WHERE run_id=? ORDER BY seq", (run_id,)
            ).fetchall()
            return tuple(self._cp(r) for r in rows)

        return await self._store.run_transaction(read)

    async def resume_plan(
        self, run_id: str, *, has_readback: Callable[[str], bool] = lambda _c: False
    ) -> tuple[ResumeStep, ...]:
        return tuple(
            ResumeStep(cp.step_id, decide(cp, readback_available=has_readback(cp.capability)))
            for cp in await self.steps(run_id)
        )

    @staticmethod
    def _row(c: sqlite3.Connection, run_id: str, step_id: str) -> sqlite3.Row | None:
        row: sqlite3.Row | None = c.execute(
            "SELECT * FROM run_checkpoints WHERE run_id=? AND step_id=?", (run_id, step_id)
        ).fetchone()
        return row

    @staticmethod
    def _cp(row: sqlite3.Row | None) -> Checkpoint:
        assert row is not None
        raw = row["observation_json"]
        return Checkpoint(
            str(row["run_id"]),
            str(row["step_id"]),
            int(row["seq"]),
            row["plan_id"],
            str(row["capability"]),
            json.loads(row["arguments_json"]),
            Effect(row["effect"]),
            Phase(row["phase"]),
            str(row["idempotency_key"]),
            Outcome(row["outcome"]) if row["outcome"] is not None else None,
            row["resolved_by"],
            json.loads(raw) if raw is not None else None,
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()
