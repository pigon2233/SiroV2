"""SQLite WAL persistence with atomic outbox/inbox operations."""

from __future__ import annotations

import asyncio
import hashlib
import os
import sqlite3
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import TypeVar

from siro.contracts.events import Event
from siro.ports.persistence import Transaction

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str
    checksum: str


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    event_id: str
    subject: str
    payload: bytes
    state: str
    attempts: int
    last_error: str | None = None


class MigrationError(RuntimeError):
    pass


def load_migrations() -> tuple[Migration, ...]:
    """Load ordered SQL migrations bundled with the package."""

    directory = files("siro.persistence").joinpath("migrations")
    migrations: list[Migration] = []
    for resource in sorted(directory.iterdir(), key=lambda item: item.name):
        if not resource.name.endswith(".sql"):
            continue
        version_text, _, label = resource.name.partition("_")
        sql = resource.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=int(version_text),
                name=label.removesuffix(".sql"),
                sql=sql,
                checksum=hashlib.sha256(sql.encode()).hexdigest(),
            )
        )
    versions = [migration.version for migration in migrations]
    if versions != list(range(1, len(migrations) + 1)):
        raise MigrationError(f"migration versions must be contiguous from 1: {versions}")
    return tuple(migrations)


def apply_migrations(
    connection: sqlite3.Connection,
    migrations: Sequence[Migration],
) -> None:
    """Apply migrations atomically and reject modified applied migrations."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {
        int(row[0]): (str(row[1]), str(row[2]))
        for row in connection.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        )
    }
    for migration in migrations:
        existing = applied.get(migration.version)
        if existing is not None:
            if existing != (migration.name, migration.checksum):
                raise MigrationError(f"applied migration {migration.version} was modified")
            continue
        try:
            connection.execute("BEGIN IMMEDIATE")
            for statement in _split_statements(migration.sql):
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    migration.version,
                    migration.name,
                    migration.checksum,
                    datetime.now(UTC).isoformat(),
                ),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()


def _split_statements(sql: str) -> list[str]:
    """Split migration SQL; migrations intentionally avoid triggers and semicolons in strings."""

    return [statement.strip() for statement in sql.split(";") if statement.strip()]


class SQLiteStore:
    """One-writer SQLite store whose blocking work runs outside the event loop."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._writer_lock = asyncio.Lock()

    async def initialize(self) -> None:
        async with self._writer_lock:
            await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            apply_migrations(connection, load_migrations())

    def _connect(self, path: Path | None = None) -> sqlite3.Connection:
        connection = sqlite3.connect(path or self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if path is None or path == self.path:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    async def run_transaction(self, work: Transaction[T]) -> T:
        async with self._writer_lock:
            return await asyncio.to_thread(self._run_transaction_sync, work)

    def _run_transaction_sync(self, work: Transaction[T]) -> T:
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                result = work(connection)
            except Exception:
                connection.rollback()
                raise
            connection.commit()
            return result

    async def append_event_with_outbox(
        self,
        event: Event,
        *,
        subject: str,
        payload: bytes,
    ) -> bool:
        """Persist a domain event and its outgoing delivery in one transaction."""

        def write(connection: sqlite3.Connection) -> bool:
            event_id = str(event.event_id)
            inserted = connection.execute(
                "INSERT OR IGNORE INTO events"
                "(event_id, type, envelope_json, received_at, trace_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    event_id,
                    event.type,
                    event.model_dump_json(),
                    event.received_at.isoformat(),
                    event.trace_id,
                ),
            ).rowcount
            if not inserted:
                return False
            connection.execute(
                "INSERT INTO outbox(event_id, subject, payload, state, attempts) "
                "VALUES (?, ?, ?, 'pending', 0)",
                (event_id, subject, payload),
            )
            return True

        return await self.run_transaction(write)

    async def pending_outbox(self, *, limit: int = 100) -> list[OutboxRecord]:
        if limit < 1 or limit > 1000:
            raise ValueError("outbox limit must be between 1 and 1000")

        def read() -> list[OutboxRecord]:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT event_id, subject, payload, state, attempts, last_error FROM outbox "
                    "WHERE state = 'pending' ORDER BY rowid LIMIT ?",
                    (limit,),
                )
                return [
                    OutboxRecord(
                        event_id=str(row["event_id"]),
                        subject=str(row["subject"]),
                        payload=bytes(row["payload"]),
                        state=str(row["state"]),
                        attempts=int(row["attempts"]),
                        last_error=row["last_error"],
                    )
                    for row in rows
                ]

        return await asyncio.to_thread(read)

    async def mark_outbox_sent(self, event_id: str) -> bool:
        def update(connection: sqlite3.Connection) -> bool:
            return bool(
                connection.execute(
                    "UPDATE outbox SET state = 'sent', sent_at = ? "
                    "WHERE event_id = ? AND state = 'pending'",
                    (datetime.now(UTC).isoformat(), event_id),
                ).rowcount
            )

        return await self.run_transaction(update)

    async def mark_outbox_failed(
        self, event_id: str, error: str, *, max_attempts: int = 5
    ) -> str | None:
        """Record a delivery failure and quarantine after the bounded retry budget."""

        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")

        def update(connection: sqlite3.Connection) -> str | None:
            row = connection.execute(
                "SELECT attempts FROM outbox WHERE event_id = ? AND state = 'pending'",
                (event_id,),
            ).fetchone()
            if row is None:
                return None
            attempts = int(row["attempts"]) + 1
            state = "quarantined" if attempts >= max_attempts else "pending"
            connection.execute(
                "UPDATE outbox SET attempts = ?, state = ?, last_error = ?, updated_at = ? "
                "WHERE event_id = ? AND state = 'pending'",
                (
                    attempts,
                    state,
                    error[:1024],
                    datetime.now(UTC).isoformat(),
                    event_id,
                ),
            )
            return state

        return await self.run_transaction(update)

    async def quarantined_outbox(self, *, limit: int = 100) -> list[OutboxRecord]:
        if not 1 <= limit <= 1000:
            raise ValueError("quarantine limit must be between 1 and 1000")

        def read() -> list[OutboxRecord]:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT event_id, subject, payload, state, attempts, last_error "
                    "FROM outbox WHERE state = 'quarantined' ORDER BY rowid LIMIT ?",
                    (limit,),
                )
                return [
                    OutboxRecord(
                        event_id=str(row["event_id"]),
                        subject=str(row["subject"]),
                        payload=bytes(row["payload"]),
                        state=str(row["state"]),
                        attempts=int(row["attempts"]),
                        last_error=row["last_error"],
                    )
                    for row in rows
                ]

        return await asyncio.to_thread(read)

    async def process_once(
        self,
        consumer_id: str,
        event_id: str,
        work: Transaction[T],
    ) -> tuple[bool, T | None]:
        """Run consumer work once; failure rolls back both work and inbox marker."""

        def process(connection: sqlite3.Connection) -> tuple[bool, T | None]:
            inserted = connection.execute(
                "INSERT OR IGNORE INTO inbox(consumer_id, event_id, processed_at) VALUES (?, ?, ?)",
                (consumer_id, event_id, datetime.now(UTC).isoformat()),
            ).rowcount
            if not inserted:
                return False, None
            return True, work(connection)

        return await self.run_transaction(process)

    async def integrity_check(self) -> str:
        def check() -> str:
            with self._connect() as connection:
                row = connection.execute("PRAGMA integrity_check").fetchone()
                return str(row[0]) if row is not None else "missing result"

        return await asyncio.to_thread(check)

    async def backup_to(self, destination: Path) -> None:
        async with self._writer_lock:
            await asyncio.to_thread(self._backup_sync, destination)

    def _backup_sync(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            with self._connect() as source, self._connect(temporary) as target:
                source.backup(target)
                result = target.execute("PRAGMA integrity_check").fetchone()
                if result is None or result[0] != "ok":
                    raise sqlite3.DatabaseError("backup integrity check failed")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    async def restore_from(self, source: Path) -> None:
        async with self._writer_lock:
            await asyncio.to_thread(self._restore_sync, source)

    def _restore_sync(self, source: Path) -> None:
        if not source.is_file():
            raise FileNotFoundError(source)
        with self._connect(source) as backup:
            result = backup.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise sqlite3.DatabaseError("source backup integrity check failed")
            with self._connect() as target:
                backup.backup(target)
        with self._connect() as restored:
            apply_migrations(restored, load_migrations())
