"""Ordered change feed for the activity monitor.

Rows are appended inside the same transaction as the run/proposal state change they
describe, so a failed audit write also fails that change: no tool starts unrecorded.
The feed only orders changes; current state is always read from the owning tables.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Literal

# Design targets from the companion CONTRACTS, not measured limits.
MAX_EVENTS = 10_000
RETENTION = timedelta(days=7)

Entity = Literal["run", "tool"]


def record_event(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    entity: Entity,
    entity_id: str,
    state: str,
    phase: str | None = None,
) -> int:
    cursor = connection.execute(
        "INSERT INTO activity_events(session_id, entity, entity_id, state, phase, recorded_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, entity, entity_id, state, phase, datetime.now(UTC).isoformat()),
    )
    sequence = int(cursor.lastrowid or 0)
    if sequence % 100 == 0:
        prune(connection)
    return sequence


def prune(connection: sqlite3.Connection, *, now: datetime | None = None) -> int:
    """Drop old feed rows; the runs and proposals they point at are kept by their owners."""
    cutoff = ((now or datetime.now(UTC)) - RETENTION).isoformat()
    removed = connection.execute(
        "DELETE FROM activity_events WHERE recorded_at < ? "
        "OR seq <= (SELECT MAX(seq) FROM activity_events) - ?",
        (cutoff, MAX_EVENTS),
    ).rowcount
    return int(removed)
