"""Transport-neutral device descriptors, registry and conservative room projection."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from siro.contracts.events import Privacy
from siro.core.world import WorldModel, WorldObservation, WorldStatus


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DeviceProperty(FrozenModel):
    type: Literal["boolean", "number", "string", "object"]
    readable: bool = True
    unit: str | None = Field(default=None, max_length=32)


class DeviceAction(FrozenModel):
    input_schema: str = Field(min_length=1, max_length=128)


class DeviceDescriptor(FrozenModel):
    device_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:-]+$")
    adapter: str = Field(min_length=1, max_length=128)
    location: str | None = Field(default=None, min_length=1, max_length=128)
    properties: dict[str, DeviceProperty]
    actions: dict[str, DeviceAction]
    events: tuple[str, ...] = ()
    availability_ttl_ms: int = Field(gt=0, le=86_400_000)
    privacy: Privacy


class DeviceAvailability(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"
    STALE = "stale"


class DeviceRecord(FrozenModel):
    descriptor: DeviceDescriptor
    availability: DeviceAvailability
    last_seen: datetime | None


class PresenceProjection(FrozenModel):
    status: WorldStatus
    present: bool | None
    source_device_ids: tuple[str, ...]


class DeviceRepository(Protocol):
    async def upsert(self, descriptor: DeviceDescriptor) -> None: ...

    async def get(self, device_id: str) -> DeviceRecord | None: ...

    async def list(self) -> tuple[DeviceRecord, ...]: ...

    async def set_availability(
        self, device_id: str, availability: DeviceAvailability, seen_at: datetime
    ) -> None: ...

    async def in_location(self, location: str) -> tuple[DeviceRecord, ...]: ...


class DeviceRegistry:
    def __init__(self, repository: DeviceRepository, world: WorldModel) -> None:
        self._repository = repository
        self._world = world

    async def register(self, descriptor: DeviceDescriptor) -> None:
        await self._repository.upsert(descriptor)

    async def set_availability(
        self, device_id: str, availability: DeviceAvailability, *, observed_at: datetime
    ) -> None:
        if await self._repository.get(device_id) is None:
            raise KeyError(device_id)
        await self._repository.set_availability(device_id, availability, observed_at)

    async def available(self, device_id: str, *, now: datetime) -> DeviceRecord | None:
        record = await self._repository.get(device_id)
        if record is None or record.last_seen is None:
            return record
        expires = record.last_seen + timedelta(milliseconds=record.descriptor.availability_ttl_ms)
        if record.availability is DeviceAvailability.ONLINE and now >= expires:
            return record.model_copy(update={"availability": DeviceAvailability.STALE})
        return record

    async def devices_for_action(self, action: str, *, now: datetime) -> tuple[DeviceRecord, ...]:
        output: list[DeviceRecord] = []
        for record in await self._repository.list():
            current = await self.available(record.descriptor.device_id, now=now)
            if (
                current is not None
                and current.availability is DeviceAvailability.ONLINE
                and action in current.descriptor.actions
            ):
                output.append(current)
        return tuple(output)

    async def record_property(
        self,
        device_id: str,
        property_name: str,
        value: object,
        *,
        observed_at: datetime,
        confidence: float = 1.0,
    ) -> bool:
        record = await self._repository.get(device_id)
        if record is None:
            raise KeyError(device_id)
        spec = record.descriptor.properties.get(property_name)
        if spec is None or not spec.readable:
            raise ValueError("device property is not declared readable")
        await self._repository.set_availability(device_id, DeviceAvailability.ONLINE, observed_at)
        return await self._world.observe(
            WorldObservation(
                observation_id=uuid4(),
                entity_id=device_id,
                property=property_name,
                value=value,
                confidence=confidence,
                observed_at=observed_at,
                expires_at=observed_at
                + timedelta(milliseconds=record.descriptor.availability_ttl_ms),
                source_id=f"device:{device_id}:{record.descriptor.adapter}",
            )
        )

    async def room_presence(self, location: str, *, now: datetime) -> PresenceProjection:
        valid: list[tuple[str, bool]] = []
        for record in await self._repository.in_location(location):
            if "presence" not in record.descriptor.properties:
                continue
            current = await self.available(record.descriptor.device_id, now=now)
            if current is None or current.availability is not DeviceAvailability.ONLINE:
                continue
            value = await self._world.current(record.descriptor.device_id, "presence", now=now)
            if (
                value.status is WorldStatus.KNOWN
                and value.observation is not None
                and isinstance(value.observation.value, bool)
            ):
                valid.append((record.descriptor.device_id, value.observation.value))
        if not valid:
            return PresenceProjection(
                status=WorldStatus.UNKNOWN, present=None, source_device_ids=()
            )
        return PresenceProjection(
            status=WorldStatus.KNOWN,
            present=any(value for _, value in valid),
            source_device_ids=tuple(device_id for device_id, _ in valid),
        )
