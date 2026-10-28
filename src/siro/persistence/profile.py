"""Read owner chat messages that profile extraction has not seen yet."""

from __future__ import annotations

import sqlite3

from siro.contracts.events import UserTextEvent
from siro.persistence.sqlite import SQLiteStore


class SQLiteProfileSource:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def unseen_user_events(self, limit: int = 200) -> list[UserTextEvent]:
        """Newest owner messages that are not yet the source of any memory, oldest first."""

        def read(connection: sqlite3.Connection) -> list[UserTextEvent]:
            rows = connection.execute(
                "SELECT e.envelope_json FROM events e WHERE e.type = 'conversation.user_text.v1' "
                "AND NOT EXISTS "
                "(SELECT 1 FROM memory_sources s WHERE s.source_event_id = e.event_id) "
                "ORDER BY e.received_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                UserTextEvent.model_validate_json(row["envelope_json"]) for row in reversed(rows)
            ]

        return await self._store.run_transaction(read)
