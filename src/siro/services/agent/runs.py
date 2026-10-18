"""Persistent goals and ordered observations for resumable agent work."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import cast
from uuid import UUID, uuid4

from siro.persistence.activity_events import record_event
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelMessage

_STATUS_ERROR_NAMES = frozenset(
    {
        "HTTPStatusError",
        "ConnectError",
        "ReadTimeout",
        "TimeoutError",
        "ConnectionError",
        "RuntimeError",
        "ValueError",
        "PermissionError",
        "ProviderOutputTruncated",
        "ProviderOutputIncomplete",
        "ContextBudgetExceeded",
        "ContextBudgetUnavailable",
        "ExecutionCleanupError",
        "ExecutionCancelled",
        "agent_step_limit",
        "duplicate_or_excess_tool_calls",
        "superseded",
        "cancelled",
        "timeout",
        "outcome_unknown",
        "interrupted_restart",
    }
)


class AgentRunState(StrEnum):
    RUNNING = "running"
    WAITING_TOOL = "waiting_tool"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class AgentRun:
    run_id: str
    session_id: str
    goal: str
    state: AgentRunState
    step_count: int
    max_steps: int
    current_proposal_id: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AgentStep:
    run_id: str
    step_index: int
    kind: str
    capability: str | None
    payload: object


class SQLiteAgentRunRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def start(
        self,
        session_id: str,
        goal: str,
        *,
        max_steps: int = 8,
        runtime_backend: str | None = None,
        privacy: str = "local_only",
        max_model_rounds: int = 8,
    ) -> AgentRun:
        if not goal.strip() or max_steps < 1:
            raise ValueError("agent run requires a goal and positive step budget")
        now = datetime.now(UTC).isoformat()
        run = AgentRun(str(uuid4()), session_id, goal.strip(), AgentRunState.RUNNING, 0, max_steps)

        def write(connection: sqlite3.Connection) -> None:
            connection.execute(
                "INSERT INTO agent_runs(run_id, session_id, goal, state, step_count, max_steps, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
                (run.run_id, session_id, run.goal, run.state.value, max_steps, now, now),
            )
            record_event(
                connection,
                session_id=session_id,
                entity="run",
                entity_id=run.run_id,
                state=run.state.value,
            )
            if runtime_backend is not None:
                connection.execute(
                    "INSERT INTO run_journal VALUES "
                    "(?, 1, 'candidate', ?, ?, ?, '[]', 0, ?, 0, 'active')",
                    (run.run_id, runtime_backend, privacy, run.run_id, max_model_rounds),
                )

        await self._store.run_transaction(write)
        return run

    async def get(self, run_id: str) -> AgentRun | None:
        row = await self._store.run_transaction(
            lambda connection: connection.execute(
                "SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        )
        return None if row is None else self._run(row)

    async def latest(self, session_id: str) -> AgentRun | None:
        row = await self._store.run_transaction(
            lambda connection: connection.execute(
                "SELECT * FROM agent_runs WHERE session_id = ? ORDER BY updated_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        )
        return None if row is None else self._run(row)

    async def append(
        self,
        run_id: str,
        kind: str,
        payload: object,
        *,
        capability: str | None = None,
        state: AgentRunState | None = None,
        proposal_id: str | None = None,
        error: str | None = None,
    ) -> AgentRun:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        def write(connection: sqlite3.Connection) -> sqlite3.Row:
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            current = self._run(row)
            if current.state in {
                AgentRunState.COMPLETED,
                AgentRunState.FAILED,
                AgentRunState.CANCELLED,
            }:
                raise ValueError("agent run is terminal")
            index = current.step_count + 1
            if index > current.max_steps:
                raise RuntimeError("agent step budget exhausted")
            now = datetime.now(UTC).isoformat()
            connection.execute(
                "INSERT INTO agent_steps VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, index, kind, capability, encoded, now),
            )
            connection.execute(
                "UPDATE agent_runs SET state = ?, step_count = ?, current_proposal_id = ?, "
                "error = ?, updated_at = ? WHERE run_id = ?",
                (
                    (state or current.state).value,
                    index,
                    proposal_id,
                    error,
                    now,
                    run_id,
                ),
            )
            if (state or current.state) != current.state:
                record_event(
                    connection,
                    session_id=current.session_id,
                    entity="run",
                    entity_id=run_id,
                    state=(state or current.state).value,
                    phase=error,
                )
            updated = connection.execute(
                "SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            assert updated is not None
            return cast(sqlite3.Row, updated)

        return self._run(await self._store.run_transaction(write))

    async def steps(self, run_id: str) -> tuple[AgentStep, ...]:
        rows = await self._store.run_transaction(
            lambda connection: connection.execute(
                "SELECT * FROM agent_steps WHERE run_id = ? ORDER BY step_index", (run_id,)
            ).fetchall()
        )
        return tuple(
            AgentStep(
                str(row["run_id"]),
                int(row["step_index"]),
                str(row["kind"]),
                str(row["capability"]) if row["capability"] is not None else None,
                json.loads(row["payload_json"]),
            )
            for row in rows
        )

    @staticmethod
    def _run(row: sqlite3.Row) -> AgentRun:
        return AgentRun(
            str(row["run_id"]),
            str(row["session_id"]),
            str(row["goal"]),
            AgentRunState(str(row["state"])),
            int(row["step_count"]),
            int(row["max_steps"]),
            str(row["current_proposal_id"]) if row["current_proposal_id"] is not None else None,
            str(row["error"]) if row["error"] is not None else None,
        )

    async def start_journal(
        self, run_id: str, *, backend: str, privacy: str, max_rounds: int
    ) -> None:
        await self._store.run_transaction(
            lambda c: c.execute(
                "INSERT INTO run_journal VALUES "
                "(?, 1, 'candidate', ?, ?, ?, '[]', 0, ?, 0, 'active')",
                (run_id, backend, privacy, run_id, max_rounds),
            )
        )

    async def reserve_round(self, run_id: str) -> int:
        def write(c: sqlite3.Connection) -> int:
            row = c.execute("SELECT * FROM run_journal WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["status"] != "active":
                raise ValueError("journal is not active")
            count = int(row["model_rounds"]) + 1
            if count > int(row["max_model_rounds"]):
                raise RuntimeError("agent_step_limit")
            c.execute("UPDATE run_journal SET model_rounds=? WHERE run_id=?", (count, run_id))
            return count

        return await self._store.run_transaction(write)

    async def checkpoint(self, run_id: str, messages: list[ModelMessage]) -> None:
        encoded = json.dumps([asdict(m) for m in messages], ensure_ascii=False)

        def write(c: sqlite3.Connection) -> None:
            row = c.execute("SELECT * FROM run_journal WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["status"] != "active":
                raise ValueError("journal is not active")
            c.execute("UPDATE run_journal SET messages_json=? WHERE run_id=?", (encoded, run_id))
            # Only the newest assistant batch is registered. Older calls keep their observations.
            if messages and messages[-1].tool_calls:
                inserted = 0
                for index, call in enumerate(messages[-1].tool_calls):
                    existing = c.execute(
                        "SELECT * FROM run_journal_calls WHERE run_id=? AND call_id=?",
                        (run_id, call.call_id),
                    ).fetchone()
                    if existing is not None:
                        if (
                            existing["capability"] != call.name
                            or json.loads(existing["arguments_json"]) != call.arguments
                        ):
                            raise ValueError("conflicting tool call")
                        continue
                    inserted += 1
                    c.execute(
                        "INSERT INTO run_journal_calls(run_id,call_id,batch_index,call_index,"
                        "capability,arguments_json) VALUES (?,?,?,?,?,?)",
                        (
                            run_id,
                            call.call_id,
                            int(row["model_rounds"]),
                            index,
                            call.name,
                            json.dumps(call.arguments, ensure_ascii=False),
                        ),
                    )
                c.execute(
                    "UPDATE run_journal SET tool_calls=tool_calls+? WHERE run_id=?",
                    (inserted, run_id),
                )

        await self._store.run_transaction(write)

    async def bind_call(self, run_id: str, call_id: str, proposal_id: str) -> None:
        await self._store.run_transaction(
            lambda c: c.execute(
                "UPDATE run_journal_calls SET proposal_id=? WHERE run_id=? AND call_id=? "
                "AND (proposal_id IS NULL OR proposal_id=?)",
                (proposal_id, run_id, call_id, proposal_id),
            )
        )

    async def record_dispatch(self, run_id: str, call_id: str) -> None:
        def write(c: sqlite3.Connection) -> None:
            changed = c.execute(
                "UPDATE run_journal_calls SET dispatched=1 WHERE run_id=? AND call_id=? "
                "AND dispatched=0 AND observation_json IS NULL AND EXISTS "
                "(SELECT 1 FROM run_journal WHERE run_id=? AND status='active')",
                (run_id, call_id, run_id),
            ).rowcount
            if changed != 1:
                raise ValueError("dispatch intent is duplicate or fenced")
            # The real dispatch boundary: recorded before the handler runs, or it never runs.
            row = c.execute(
                "SELECT r.session_id, j.proposal_id FROM run_journal_calls j "
                "JOIN agent_runs r ON r.run_id=j.run_id WHERE j.run_id=? AND j.call_id=?",
                (run_id, call_id),
            ).fetchone()
            record_event(
                c,
                session_id=str(row["session_id"]),
                entity="tool" if row["proposal_id"] is not None else "run",
                entity_id=str(row["proposal_id"] or run_id),
                state="running",
                phase="dispatched",
            )

        await self._store.run_transaction(write)

    async def record_observation(self, run_id: str, call_id: str, observation: object) -> None:
        encoded = json.dumps(observation, ensure_ascii=False)

        def write(c: sqlite3.Connection) -> None:
            row = c.execute(
                "SELECT observation_json FROM run_journal_calls WHERE run_id=? AND call_id=?",
                (run_id, call_id),
            ).fetchone()
            if row is None:
                raise ValueError("unpaired tool observation")
            if row[0] is not None:
                if json.loads(row[0]) != observation:
                    raise ValueError("conflicting tool observation")
                return
            changed = c.execute(
                "UPDATE run_journal_calls SET observation_json=? WHERE run_id=? AND call_id=? "
                "AND EXISTS (SELECT 1 FROM run_journal WHERE run_id=? AND status='active')",
                (encoded, run_id, call_id, run_id),
            ).rowcount
            if not changed:
                raise ValueError("journal is fenced")

        await self._store.run_transaction(write)

    @staticmethod
    def _paired_messages(c: sqlite3.Connection, row: sqlite3.Row) -> list[dict[str, object]]:
        messages = cast(list[dict[str, object]], json.loads(row["messages_json"]))
        calls = {
            str(item["call_id"]): item
            for item in c.execute(
                "SELECT * FROM run_journal_calls WHERE run_id=?", (row["run_id"],)
            )
        }
        paired: list[dict[str, object]] = []
        for message in messages:
            if message["role"] == "tool":
                continue  # rebuild one ordered observation from canonical call rows
            paired.append(message)
            for call in cast(list[dict[str, object]], message.get("tool_calls", [])):
                call_id = str(call["call_id"])
                item = calls.get(call_id)
                if item is None:
                    raise ValueError("journal has an unregistered tool call")
                if item["observation_json"] is None:
                    observation: object = {
                        "error": "outcome_unknown" if item["dispatched"] else "not_dispatched",
                        "recovered": True,
                    }
                else:
                    observation = json.loads(item["observation_json"])
                paired.append(
                    {
                        "role": "tool",
                        "content": json.dumps(observation, ensure_ascii=False),
                        "tool_calls": [],
                        "tool_call_id": call_id,
                    }
                )
        return paired

    async def finish_journal(self, run_id: str, *, interrupted: bool = False) -> None:
        def write(c: sqlite3.Connection) -> None:
            row = c.execute("SELECT * FROM run_journal WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["status"] != "active":
                return
            # Close all missing pairs conservatively, even when terminal cancellation wins.
            c.execute(
                "UPDATE run_journal_calls SET observation_json="
                "CASE WHEN dispatched=1 THEN ? ELSE ? END "
                "WHERE run_id=? AND observation_json IS NULL",
                (
                    json.dumps({"error": "outcome_unknown", "recovered": True}),
                    json.dumps({"error": "not_dispatched", "recovered": True}),
                    run_id,
                ),
            )
            messages = self._paired_messages(c, row)
            c.execute(
                "UPDATE run_journal SET messages_json=?,status=? WHERE run_id=?",
                (
                    json.dumps(messages, ensure_ascii=False),
                    "interrupted" if interrupted else "terminal",
                    run_id,
                ),
            )

        await self._store.run_transaction(write)

    async def reconcile(self) -> int:
        """Read-only recovery of external effects: never invoke a handler or model."""

        def write(c: sqlite3.Connection) -> int:
            rows = c.execute(
                "SELECT j.* FROM run_journal j JOIN agent_runs r ON r.run_id=j.run_id "
                "WHERE j.status='active' OR r.state IN ('running','waiting_tool')"
            ).fetchall()
            fenced_proposals: set[str] = set()
            for row in rows:
                run_id = str(row["run_id"])
                calls = c.execute(
                    "SELECT * FROM run_journal_calls WHERE run_id=?", (run_id,)
                ).fetchall()
                for call in calls:
                    if call["proposal_id"] is not None:
                        proposals = c.execute(
                            "SELECT * FROM tool_proposals WHERE proposal_id=? AND session_id="
                            "(SELECT session_id FROM agent_runs WHERE run_id=?)",
                            (call["proposal_id"], run_id),
                        ).fetchall()
                    else:
                        # Only historical insert-before-bind gaps use session/provider identity.
                        proposals = c.execute(
                            "SELECT * FROM tool_proposals WHERE call_id=? AND session_id="
                            "(SELECT session_id FROM agent_runs WHERE run_id=?) "
                            "AND proposal_id NOT IN (SELECT proposal_id FROM run_journal_calls "
                            "WHERE proposal_id IS NOT NULL)",
                            (call["call_id"], run_id),
                        ).fetchall()
                    for proposal in proposals:
                        if proposal["capability"] != call["capability"] or json.loads(
                            proposal["arguments_json"]
                        ) != json.loads(call["arguments_json"]):
                            continue
                        if proposal["state"] == "running":
                            c.execute(
                                "UPDATE run_journal_calls SET dispatched=1 "
                                "WHERE run_id=? AND call_id=?",
                                (run_id, call["call_id"]),
                            )
                        fenced_proposals.add(str(proposal["proposal_id"]))
                c.execute(
                    "UPDATE run_journal_calls SET observation_json="
                    "CASE WHEN dispatched=1 THEN ? ELSE ? END "
                    "WHERE run_id=? AND observation_json IS NULL",
                    (
                        json.dumps({"error": "outcome_unknown", "recovered": True}),
                        json.dumps({"error": "not_dispatched", "recovered": True}),
                        run_id,
                    ),
                )
                messages = self._paired_messages(c, row)
                c.execute(
                    "UPDATE run_journal SET messages_json=?,status='interrupted' WHERE run_id=?",
                    (json.dumps(messages, ensure_ascii=False), run_id),
                )
                unknown = (
                    c.execute(
                        "SELECT 1 FROM run_journal_calls WHERE run_id=? AND dispatched=1 "
                        "AND json_extract(observation_json,'$.error')='outcome_unknown'",
                        (run_id,),
                    ).fetchone()
                    is not None
                )
                reason = "outcome_unknown" if unknown else "interrupted_restart"
                if c.execute(
                    "UPDATE agent_runs SET state='failed',error=?,current_proposal_id=NULL,"
                    "updated_at=? WHERE run_id=? AND state IN ('running','waiting_tool')",
                    (reason, datetime.now(UTC).isoformat(), run_id),
                ).rowcount:
                    record_event(
                        c,
                        session_id=str(
                            c.execute(
                                "SELECT session_id FROM agent_runs WHERE run_id=?", (run_id,)
                            ).fetchone()[0]
                        ),
                        entity="run",
                        entity_id=run_id,
                        state="failed",
                        phase=reason,
                    )
            for proposal_id in fenced_proposals:
                if c.execute(
                    "UPDATE tool_proposals SET state=CASE WHEN state='running' THEN 'failed' "
                    "ELSE 'denied' END,error='interrupted_restart' WHERE proposal_id=? "
                    "AND state IN ('pending','approved','running')",
                    (proposal_id,),
                ).rowcount:
                    fenced = c.execute(
                        "SELECT session_id, state FROM tool_proposals WHERE proposal_id=?",
                        (proposal_id,),
                    ).fetchone()
                    record_event(
                        c,
                        session_id=str(fenced[0]),
                        entity="tool",
                        entity_id=proposal_id,
                        state=str(fenced[1]),
                        phase="interrupted_restart",
                    )
            return len(rows)

        return await self._store.run_transaction(write)

    async def recent_runtime_status(
        self, session_id: str, *, privacy: str
    ) -> dict[str, object] | None:
        """One safe fact about the latest recorded dialogue; never restore failed intents."""
        if privacy not in {"local_only", "cloud_allowed"}:
            return None

        def read(c: sqlite3.Connection) -> dict[str, object] | None:
            row = c.execute(
                "SELECT CASE WHEN length(CAST(r.run_id AS BLOB))=36 THEN r.run_id END AS run_id, "
                "r.state, CASE WHEN length(CAST(r.error AS BLOB))<=64 THEN r.error END AS error, "
                "CASE WHEN length(CAST(r.updated_at AS BLOB))<=64 "
                "THEN r.updated_at END AS updated_at, "
                "(j.version=1 AND j.runtime_profile='candidate' AND j.privacy=? "
                "AND j.status IN ('terminal','interrupted') "
                "AND r.state IN ('failed','cancelled')) AS eligible, "
                "EXISTS(SELECT 1 FROM run_journal_calls calls WHERE calls.run_id=r.run_id "
                "AND calls.dispatched=1) AS tool_dispatch_recorded "
                "FROM agent_runs r LEFT JOIN run_journal j ON j.run_id=r.run_id "
                "WHERE r.session_id=? ORDER BY r.rowid DESC LIMIT 1",
                (privacy, session_id),
            ).fetchone()
            # Validate after selecting: do not resurrect an older eligible failure.
            if row is None or not row["eligible"] or row["run_id"] is None:
                return None
            try:
                if str(UUID(row["run_id"])) != row["run_id"] or row["updated_at"] is None:
                    return None
                updated = datetime.fromisoformat(row["updated_at"])
                if updated.tzinfo is None:
                    return None
                age = (datetime.now(UTC) - updated).total_seconds()
            except (ValueError, TypeError, OverflowError):
                return None
            if not 0 <= age <= 900:
                return None
            return {
                "source_run_id": str(row["run_id"]),
                "state": str(row["state"]),
                "error_class": row["error"] if row["error"] in _STATUS_ERROR_NAMES else "UNKNOWN",
                "tool_dispatch_recorded": bool(row["tool_dispatch_recorded"]),
                "root_cause": "UNKNOWN",
            }

        return await self._store.run_transaction(read)

    async def recent_session_messages(
        self,
        session_id: str,
        *,
        privacy: str,
        max_messages: int = 12,
        summary_enabled: bool = False,
    ) -> tuple[ModelMessage, ...]:
        """Restore bounded completed dialogue, never old prompts or executable intents."""
        if max_messages < 2:
            raise ValueError("session context requires room for a complete dialogue pair")

        def read(c: sqlite3.Connection) -> tuple[ModelMessage, ...]:
            cutoff = ""
            if summary_enabled:
                mutation = c.execute(
                    "SELECT MAX(changed_at) FROM memory_revisions WHERE revision > 1"
                ).fetchone()
                cutoff = str(mutation[0]) if mutation and mutation[0] else ""
            rows = c.execute(
                "SELECT j.messages_json,r.goal FROM run_journal j "
                "JOIN agent_runs r ON r.run_id=j.run_id "
                "WHERE r.session_id=? AND r.state='completed' AND j.status='terminal' "
                "AND j.version=1 AND j.runtime_profile='candidate' AND j.privacy=? "
                "AND r.created_at>=? "
                "ORDER BY r.created_at DESC,r.rowid DESC LIMIT ?",
                (session_id, privacy, cutoff, max_messages // 2),
            ).fetchall()
            restored: list[ModelMessage] = []
            for row in reversed(rows):
                messages = json.loads(row["messages_json"])
                if not isinstance(messages, list) or not all(
                    isinstance(m, dict) and isinstance(m.get("content"), str) for m in messages
                ):
                    raise ValueError("invalid canonical session dialogue")
                users = [m for m in messages if m.get("role") == "user"]
                if (
                    not users
                    or users[-1]["content"].strip() != row["goal"]
                    or not messages
                    or messages[-1].get("role") != "assistant"
                    or messages[-1].get("tool_calls")
                ):
                    raise ValueError("invalid canonical session dialogue")
                restored.extend(
                    (
                        ModelMessage("user", users[-1]["content"]),
                        ModelMessage("assistant", messages[-1]["content"]),
                    )
                )
            if summary_enabled:
                from siro.services.agent.summary import summarize_completed

                return summarize_completed(tuple(restored))
            return tuple(restored)

        return await self._store.run_transaction(read)

    async def readback(self, session_id: str) -> dict[str, object] | None:
        def read(c: sqlite3.Connection) -> dict[str, object] | None:
            run = c.execute(
                "SELECT * FROM agent_runs WHERE session_id=? ORDER BY updated_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if run is None:
                return None
            row = c.execute("SELECT * FROM run_journal WHERE run_id=?", (run["run_id"],)).fetchone()
            result: dict[str, object] = {
                "run_id": run["run_id"],
                "goal": run["goal"],
                "state": run["state"],
                "error": run["error"],
            }
            if row is None:
                return {**result, "recovery_status": "legacy_unrestorable"}
            calls = [
                dict(item)
                for item in c.execute(
                    "SELECT * FROM run_journal_calls WHERE run_id=? "
                    "ORDER BY batch_index,call_index",
                    (run["run_id"],),
                )
            ]
            return {
                **result,
                "recovery_status": row["status"],
                "runtime_version": row["version"],
                "runtime_profile": row["runtime_profile"],
                "backend": row["backend"],
                "privacy": row["privacy"],
                "epoch": row["epoch"],
                "model_rounds": row["model_rounds"],
                "max_model_rounds": row["max_model_rounds"],
                "tool_calls": row["tool_calls"],
                "messages": json.loads(row["messages_json"]),
                "calls": calls,
            }

        return await self._store.run_transaction(read)
