"""SQLite device registry and location graph."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from siro.core.devices import DeviceAvailability, DeviceDescriptor, DeviceRecord
from siro.persistence.sqlite import SQLiteStore


class SQLiteDeviceRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def upsert(self, descriptor: DeviceDescriptor) -> None:
        def write(connection: sqlite3.Connection) -> None:
            connection.execute(
                "INSERT INTO devices(device_id, adapter_id, descriptor_json, availability) "
                "VALUES (?, ?, ?, 'unknown') ON CONFLICT(device_id) DO UPDATE SET "
                "adapter_id=excluded.adapter_id, descriptor_json=excluded.descriptor_json",
                (descriptor.device_id, descriptor.adapter, descriptor.model_dump_json()),
            )
            connection.execute(
                "DELETE FROM entity_edges WHERE from_id = ? AND relation = 'located_in'",
                (descriptor.device_id,),
            )
            if descriptor.location is not None:
                connection.execute(
                    "INSERT INTO entity_edges(from_id, relation, to_id) "
                    "VALUES (?, 'located_in', ?)",
                    (descriptor.device_id, descriptor.location),
                )

        await self._store.run_transaction(write)

    async def get(self, device_id: str) -> DeviceRecord | None:
        records = await self._read("WHERE d.device_id = ?", (device_id,))
        return records[0] if records else None

    async def list(self) -> tuple[DeviceRecord, ...]:
        return await self._read("ORDER BY d.device_id", ())

    async def set_availability(
        self, device_id: str, availability: DeviceAvailability, seen_at: datetime
    ) -> None:
        def write(connection: sqlite3.Connection) -> None:
            changed = connection.execute(
                "UPDATE devices SET availability = ?, last_seen = ? WHERE device_id = ?",
                (availability.value, seen_at.isoformat(), device_id),
            ).rowcount
            if not changed:
                raise KeyError(device_id)

        await self._store.run_transaction(write)

    async def in_location(self, location: str) -> tuple[DeviceRecord, ...]:
        return await self._read(
            "JOIN entity_edges e ON e.from_id=d.device_id "
            "WHERE e.relation='located_in' AND e.to_id=? ORDER BY d.device_id",
            (location,),
        )

    async def _read(self, clause: str, parameters: tuple[object, ...]) -> tuple[DeviceRecord, ...]:
        def read(connection: sqlite3.Connection) -> tuple[DeviceRecord, ...]:
            rows = connection.execute(
                "SELECT d.descriptor_json, d.availability, d.last_seen FROM devices d " + clause,
                parameters,
            )
            return tuple(
                DeviceRecord(
                    descriptor=DeviceDescriptor.model_validate_json(row["descriptor_json"]),
                    availability=DeviceAvailability(row["availability"]),
                    last_seen=datetime.fromisoformat(row["last_seen"])
                    if row["last_seen"]
                    else None,
                )
                for row in rows
            )

        return await self._store.run_transaction(read)
