"""Sensor-node health: SIRO notices when a node has been silent for a while, and when it is back.

Reads device availability and `last_seen` (the node republishes state every ~10 s, so a silent
node goes stale after its TTL). Only says *when* a trigger may reach her; she decides what to say.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from siro.core.devices import DeviceAvailability, DeviceRecord
from siro.persistence.devices import SQLiteDeviceRepository

OFFLINE_AFTER = timedelta(minutes=10)
REPEAT_AFTER = timedelta(hours=3)


class NodeHealthWatcher:
    def __init__(
        self,
        repository: SQLiteDeviceRepository,
        *,
        offline_after: timedelta = OFFLINE_AFTER,
        repeat_after: timedelta = REPEAT_AFTER,
        groups: dict[str, str] | None = None,
    ) -> None:
        self._repository = repository
        # device_id -> group key: one physical node reachable over several transports (MQTT
        # with HTTP fallback) counts as alive while any of its devices is.
        self._groups = groups or {}
        self._offline_after = offline_after
        self._repeat_after = repeat_after
        self._down_since: dict[str, datetime] = {}
        self._raised: dict[str, datetime] = {}

    async def check(self, now: datetime | None = None) -> list[dict[str, object]]:
        now = now or datetime.now(UTC)
        facts: list[dict[str, object]] = []
        latest: dict[str, DeviceRecord] = {}
        for item in await self._repository.list():
            key = self._groups.get(item.descriptor.device_id, item.descriptor.device_id)
            held = latest.get(key)
            if held is None or (
                item.last_seen is not None
                and (held.last_seen is None or item.last_seen > held.last_seen)
            ):
                latest[key] = item
        for record in latest.values():
            device_id = record.descriptor.device_id
            if record.last_seen is None:
                continue  # never heard from: nothing to lose yet
            ttl = timedelta(milliseconds=record.descriptor.availability_ttl_ms)
            online = (
                record.availability is DeviceAvailability.ONLINE and now < record.last_seen + ttl
            )
            if online:
                down = self._down_since.pop(device_id, None)
                if self._raised.pop(device_id, None) is not None and down is not None:
                    facts.append(
                        {
                            "trigger": "node_back",
                            "device": device_id,
                            "down_minutes": int((now - down).total_seconds() // 60),
                        }
                    )
                continue
            down = self._down_since.setdefault(device_id, min(now, record.last_seen + ttl))
            raised = self._raised.get(device_id)
            if now - down >= self._offline_after and (
                raised is None or now - raised >= self._repeat_after
            ):
                self._raised[device_id] = now
                facts.append(
                    {
                        "trigger": "node_offline",
                        "device": device_id,
                        "down_minutes": int((now - down).total_seconds() // 60),
                    }
                )
        return facts
