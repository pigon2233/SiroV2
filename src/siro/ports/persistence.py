"""Persistence ports owned by the SIRO core."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypeVar

from siro.contracts.events import Event

T = TypeVar("T")
Transaction = Callable[[sqlite3.Connection], T]


class Persistence(Protocol):
    async def initialize(self) -> None: ...

    async def run_transaction(self, work: Transaction[T]) -> T: ...

    async def append_event_with_outbox(
        self, event: Event, *, subject: str, payload: bytes
    ) -> bool: ...

    async def process_once(
        self,
        consumer_id: str,
        event_id: str,
        work: Transaction[T],
    ) -> tuple[bool, T | None]: ...

    async def backup_to(self, destination: Path) -> None: ...

    async def restore_from(self, source: Path) -> None: ...
