"""Read-only event replay that cannot dispatch runtime side effects."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Awaitable, Callable

from siro.contracts.events import Event, validate_event_json
from siro.persistence.sqlite import SQLiteStore

ReplayProjector = Callable[[Event], Awaitable[None]]


class ReplaySideEffectError(RuntimeError):
    pass


class ReplayRuntime:
    async def dispatch(self, _capability: str, _arguments: dict[str, object]) -> None:
        raise ReplaySideEffectError("runtime side effects are disabled during replay")


class ReplayRunner:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def run(self, projector: ReplayProjector) -> int:
        def read() -> list[bytes]:
            with sqlite3.connect(self._store.path) as connection:
                return [
                    str(row[0]).encode()
                    for row in connection.execute(
                        "SELECT envelope_json FROM events ORDER BY received_at, event_id"
                    )
                ]

        payloads = await asyncio.to_thread(read)
        for payload in payloads:
            await projector(validate_event_json(payload))
        return len(payloads)
