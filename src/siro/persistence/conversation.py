"""SQLite conversation state repository."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from siro.core.conversation import TurnResult
from siro.persistence.sqlite import SQLiteStore


class SQLiteConversationRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def start_turn(
        self, session_id: str, identity_id: str, turn_id: str, generation_id: str, user_text: str
    ) -> None:
        def write(connection: sqlite3.Connection) -> None:
            now = datetime.now(UTC).isoformat()
            connection.execute(
                "INSERT OR IGNORE INTO conversations(session_id, identity_id, created_at, status) "
                "VALUES (?, ?, ?, 'active')",
                (session_id, identity_id, now),
            )
            connection.execute(
                "UPDATE conversations SET status = 'active' WHERE session_id = ?",
                (session_id,),
            )
            connection.execute(
                "INSERT INTO turns(turn_id, session_id, generation_id, state) VALUES (?, ?, ?, ?)",
                (turn_id, session_id, generation_id, "responding"),
            )
            connection.execute(
                "INSERT INTO messages(turn_id, role, text, sequence) VALUES (?, 'user', ?, 0)",
                (turn_id, user_text),
            )

        await self._store.run_transaction(write)

    async def finish_turn(self, result: TurnResult) -> None:
        def write(connection: sqlite3.Connection) -> None:
            connection.execute(
                "UPDATE turns SET state = ?, ended_at = ?, revision = revision + 1 "
                "WHERE turn_id = ? AND state = 'responding'",
                (result.state, datetime.now(UTC).isoformat(), result.turn_id),
            )
            if result.text:
                connection.execute(
                    "INSERT INTO messages(turn_id, role, text, sequence) "
                    "VALUES (?, 'assistant', ?, 1)",
                    (result.turn_id, result.text),
                )

        await self._store.run_transaction(write)
