"""Read-only activity monitor: a projection over runs, proposals and the run journal.

It never dispatches, retries or replays anything. States are derived from the durable
owners; `activity_events` only orders changes for cursor-based incremental reads.
Targets are redacted here: no query strings, credentials, typed values or argv details.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import PurePosixPath
from typing import cast
from urllib.parse import urlsplit

from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.self_activity import SELF_SESSION

MAX_PAGE = 100
DEFAULT_SNAPSHOT = 50
MAX_REASON = 200
MAX_PATH = 200
_CANCEL_ERRORS = {"ExecutionCancelled", "interrupted_restart"}
ACTIVE_STATES = frozenset({"proposed", "queued", "running", "paused", "cancelling"})


def redact_url(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parts = urlsplit(raw)
        port = parts.port
    except ValueError:
        return {"url": None, "invalid": True}
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return {"url": f"{parts.scheme}:" if parts.scheme else None, "redacted": True}
    host = parts.hostname + (f":{port}" if port is not None else "")
    view: dict[str, object] = {"url": f"{parts.scheme}://{host}{parts.path[:MAX_PATH]}"}
    if parts.query or parts.fragment or parts.username or parts.password:
        view["redacted"] = True
    return view


def _json(raw: object) -> object:
    return json.loads(raw) if isinstance(raw, str) else None


def describe_tool(capability: str, arguments: object, observation: object) -> dict[str, object]:
    """Redacted target plus honest network coverage for one tool call."""
    args = arguments if isinstance(arguments, dict) else {}
    seen = observation if isinstance(observation, dict) else {}
    if capability == "browser.navigate+read":
        requested = redact_url(args.get("url"))
        final = redact_url(seen.get("url"))
        redirected: object = "unknown"
        if requested is not None and final is not None:
            redirected = requested.get("url") != final.get("url")
        return {
            "target": requested,
            "network": {
                "coverage": "browser_adapter",
                "requests": [
                    {
                        "kind": "navigation",
                        "requested": requested,
                        "final": final,
                        "redirected": redirected,
                        "status": "unknown",
                        "subresources": "some_denied"
                        if seen.get("load_status") == "partial"
                        else "not_recorded",
                    }
                ],
                "gaps": ["http_status_not_captured", "subresource_requests_not_listed"],
            },
        }
    if capability.startswith("browser."):
        return {
            "target": redact_url(seen.get("url")),
            "network": {
                "coverage": "browser_adapter",
                "requests": [],
                "gaps": ["page_interaction_requests_not_listed"],
            },
        }
    if capability == "computer.execute":
        argv = args.get("argv")
        program = None
        if isinstance(argv, list) and argv and isinstance(argv[0], str):
            program = {"program": PurePosixPath(argv[0]).name, "argument_count": len(argv) - 1}
        return {
            "target": program,
            "network": {
                "coverage": "unobserved",
                "requests": [],
                "gaps": ["subprocess_network_not_monitored"],
            },
        }
    return {
        "target": None,
        "network": {"coverage": "unobserved", "requests": [], "gaps": ["tool_not_instrumented"]},
    }


def tool_state(raw: str, error: object, dispatched: object) -> str:
    """Contract view states; cancellation without a reliable readback stays unknown."""
    if raw == "pending":
        return "proposed"
    if raw == "approved":
        return "queued"
    if raw in {"running", "completed"}:
        return raw
    if raw == "denied":
        return "cancelled"
    if raw == "failed" and error in _CANCEL_ERRORS:
        return "cancelled" if dispatched == 0 else "unknown"
    return "failed" if raw == "failed" else "unknown"


def run_state(raw: str, error: object) -> str:
    if raw in {"running", "waiting_tool"}:
        return "running"
    if raw == "failed" and error == "outcome_unknown":
        return "unknown"
    return raw if raw in {"completed", "failed", "cancelled"} else "unknown"


class ActivityMonitor:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def snapshot(self, *, limit: int = DEFAULT_SNAPSHOT) -> dict[str, object]:
        size = max(1, min(limit, MAX_PAGE))

        def read(c: sqlite3.Connection) -> dict[str, object]:
            cursor, floor = _bounds(c)
            runs = c.execute(
                "SELECT * FROM agent_runs ORDER BY updated_at DESC LIMIT ?", (size + 1,)
            ).fetchall()
            standalone = c.execute(
                "SELECT * FROM tool_proposals WHERE proposal_id NOT IN ("
                "SELECT proposal_id FROM run_journal_calls WHERE proposal_id IS NOT NULL) "
                "ORDER BY updated_at DESC LIMIT ?",
                (size + 1,),
            ).fetchall()
            items = [_run_view(c, row) for row in runs]
            items += [_standalone_view(c, row) for row in standalone]
            items.sort(key=lambda item: str(item["updated_at"]), reverse=True)
            return {
                "status": "ok",
                "cursor": cursor,
                "retained_from": floor,
                "activities": items[:size],
                "truncated": len(items) > size,
            }

        return await self._store.run_transaction(read)

    async def changes(self, *, after: int, limit: int = MAX_PAGE) -> dict[str, object]:
        size = max(1, min(limit, MAX_PAGE))

        def read(c: sqlite3.Connection) -> dict[str, object]:
            cursor, floor = _bounds(c)
            # Pruned rows or a reset store mean the client must take a new snapshot.
            gap = after > cursor or (after > 0 and floor is not None and after < floor - 1)
            rows = c.execute(
                "SELECT * FROM activity_events WHERE seq > ? ORDER BY seq LIMIT ?",
                (after, size + 1),
            ).fetchall()
            page = rows[:size]
            events: list[dict[str, object]] = []
            touched: dict[str, dict[str, object]] = {}
            for row in page:
                activity_id, view = _activity_for(c, str(row["entity"]), str(row["entity_id"]))
                events.append(
                    {
                        "seq": row["seq"],
                        "session_id": row["session_id"],
                        "entity": row["entity"],
                        "entity_id": row["entity_id"],
                        "activity_id": activity_id,
                        "raw_state": row["state"],
                        "phase": row["phase"],
                        "recorded_at": row["recorded_at"],
                    }
                )
                if view is not None:
                    touched[activity_id] = view
            return {
                "status": "ok",
                "after": after,
                "cursor": int(page[-1]["seq"]) if page else (cursor if gap else after),
                "has_more": len(rows) > size,
                "gap": gap,
                "events": events,
                "activities": touched,
            }

        return await self._store.run_transaction(read)

    async def get(self, activity_id: str) -> dict[str, object] | None:
        """One activity by its id: a run id first, then a standalone proposal id."""

        def read(c: sqlite3.Connection) -> dict[str, object] | None:
            run = c.execute("SELECT * FROM agent_runs WHERE run_id=?", (activity_id,)).fetchone()
            if run is not None:
                return _run_view(c, run)
            found, view = _activity_for(c, "tool", activity_id)
            return view if found == activity_id else None

        return await self._store.run_transaction(read)


def _bounds(c: sqlite3.Connection) -> tuple[int, int | None]:
    row = c.execute("SELECT MAX(seq), MIN(seq) FROM activity_events").fetchone()
    return int(row[0] or 0), None if row[1] is None else int(row[1])


def _tool_view(row: sqlite3.Row, journal: sqlite3.Row | None) -> dict[str, object]:
    dispatched = None if journal is None else int(journal["dispatched"])
    observation = _json(row["observation_json"])
    if observation is None and journal is not None:
        observation = _json(journal["observation_json"])
    described = describe_tool(str(row["capability"]), _json(row["arguments_json"]), observation)
    return {
        "proposal_id": row["proposal_id"],
        "capability": row["capability"],
        "risk": row["risk"],
        "state": tool_state(str(row["state"]), row["error"], dispatched),
        "raw_state": row["state"],
        "error": row["error"],
        "dispatched": None if dispatched is None else bool(dispatched),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        **described,
    }


def _run_view(c: sqlite3.Connection, run: sqlite3.Row) -> dict[str, object]:
    calls = c.execute(
        "SELECT j.*, p.proposal_id AS bound FROM run_journal_calls j "
        "JOIN tool_proposals p ON p.proposal_id=j.proposal_id WHERE j.run_id=? "
        "ORDER BY j.batch_index, j.call_index",
        (run["run_id"],),
    ).fetchall()
    tools = []
    for call in calls:
        proposal = c.execute(
            "SELECT * FROM tool_proposals WHERE proposal_id=?", (call["bound"],)
        ).fetchone()
        tools.append(_tool_view(proposal, call))
    goal = str(run["goal"])
    coverage = sorted({cast(dict[str, str], tool["network"])["coverage"] for tool in tools})
    journal = c.execute(
        "SELECT status FROM run_journal WHERE run_id=?", (run["run_id"],)
    ).fetchone()
    return {
        "activity_id": run["run_id"],
        "kind": "agent_run",
        # SIRO's own runs use one reserved session; everything else was asked for by the owner.
        "origin": "self_interest" if run["session_id"] == SELF_SESSION else "owner_request",
        "session_id": run["session_id"],
        "reason": goal[:MAX_REASON],
        "reason_truncated": len(goal) > MAX_REASON,
        "state": run_state(str(run["state"]), run["error"]),
        "raw_state": run["state"],
        "error": run["error"],
        "created_at": run["created_at"],
        "updated_at": run["updated_at"],
        "tools": tools,
        "coverage": {
            "tools": "journal" if journal is not None else "legacy_unjournaled",
            "network": coverage or ["none_recorded"],
        },
    }


def _standalone_view(c: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    tool = _tool_view(row, None)
    return {
        "activity_id": row["proposal_id"],
        "kind": "tool",
        "origin": "owner_request",
        "session_id": row["session_id"],
        "reason": None,
        "reason_truncated": False,
        "state": tool["state"],
        "raw_state": row["state"],
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "tools": [tool],
        "coverage": {
            "tools": "proposal_only",
            "network": [cast(dict[str, str], tool["network"])["coverage"]],
        },
    }


def _activity_for(
    c: sqlite3.Connection, entity: str, entity_id: str
) -> tuple[str, dict[str, object] | None]:
    if entity == "run":
        run = c.execute("SELECT * FROM agent_runs WHERE run_id=?", (entity_id,)).fetchone()
        return entity_id, None if run is None else _run_view(c, run)
    owner = c.execute(
        "SELECT r.* FROM run_journal_calls j JOIN agent_runs r ON r.run_id=j.run_id "
        "WHERE j.proposal_id=?",
        (entity_id,),
    ).fetchone()
    if owner is not None:
        return str(owner["run_id"]), _run_view(c, owner)
    row = c.execute("SELECT * FROM tool_proposals WHERE proposal_id=?", (entity_id,)).fetchone()
    return entity_id, None if row is None else _standalone_view(c, row)
