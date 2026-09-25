"""Source-aware current world state and observation history."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WorldObservation(_FrozenModel):
    observation_id: UUID
    entity_id: str = Field(min_length=1, max_length=128)
    property: str = Field(min_length=1, max_length=128)
    value: object
    confidence: float = Field(ge=0, le=1)
    observed_at: datetime
    expires_at: datetime | None = None
    source_id: str = Field(min_length=1, max_length=256)

    @field_validator("observed_at", "expires_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("world timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def expiry_follows_observation(self) -> WorldObservation:
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")
        return self


class WorldStatus(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"


class WorldValue(_FrozenModel):
    status: WorldStatus
    reason: Literal["missing", "expired", "current"]
    observation: WorldObservation | None


class WorldRepository(Protocol):
    async def record(self, observation: WorldObservation) -> bool: ...

    async def current(self, entity_id: str, property_name: str) -> WorldObservation | None: ...


class WorldModel:
    def __init__(self, repository: WorldRepository) -> None:
        self._repository = repository

    async def observe(self, observation: WorldObservation) -> bool:
        """Record history; return whether this observation became current."""

        return await self._repository.record(observation)

    async def current(
        self,
        entity_id: str,
        property_name: str,
        *,
        now: datetime,
    ) -> WorldValue:
        observation = await self._repository.current(entity_id, property_name)
        if observation is None:
            return WorldValue(status=WorldStatus.UNKNOWN, reason="missing", observation=None)
        if observation.expires_at is not None and now >= observation.expires_at:
            return WorldValue(
                status=WorldStatus.UNKNOWN,
                reason="expired",
                observation=observation,
            )
        return WorldValue(status=WorldStatus.KNOWN, reason="current", observation=observation)
