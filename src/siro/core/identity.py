"""Persistent identity state independent from any language model."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ImmutableCore(_FrozenModel):
    name: str = Field(min_length=1, max_length=80)
    baseline_identity: str = Field(min_length=1, max_length=4000)
    core_values: tuple[str, ...] = Field(min_length=1, max_length=32)
    creator_relationship: str = Field(min_length=1, max_length=1000)

    @field_validator("core_values")
    @classmethod
    def unique_nonempty_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("core values cannot be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("core values must be unique")
        return normalized


class TraitState(_FrozenModel):
    values: dict[str, float] = Field(default_factory=dict)

    @field_validator("values")
    @classmethod
    def validate_traits(cls, values: dict[str, float]) -> dict[str, float]:
        if len(values) > 64:
            raise ValueError("at most 64 traits are supported")
        for name, value in values.items():
            if not name or len(name) > 80:
                raise ValueError("trait names must contain 1-80 characters")
            if not 0 <= value <= 1:
                raise ValueError("trait values must be between 0 and 1")
        return values


class IdentityState(_FrozenModel):
    identity_id: str = Field(min_length=1, max_length=128)
    core: ImmutableCore
    traits: TraitState = TraitState()
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("identity timestamps must include a timezone")
        return value


class OwnerAuthorization(StrEnum):
    """Temporary T05 authorization marker; Runtime grants replace it in T21."""

    OWNER_EDIT = "owner_edit"


class IdentityRepository(Protocol):
    async def create(self, state: IdentityState, *, source_ids: Sequence[str]) -> None: ...

    async def get(self, identity_id: str) -> IdentityState | None: ...

    async def save(
        self,
        state: IdentityState,
        *,
        expected_revision: int,
        patch: dict[str, object],
        source_ids: Sequence[str],
    ) -> None: ...


class IdentityService:
    def __init__(self, repository: IdentityRepository) -> None:
        self._repository = repository

    async def create(
        self,
        identity_id: str,
        core: ImmutableCore,
        *,
        traits: TraitState | None = None,
        now: datetime,
        source_ids: Sequence[str] = (),
    ) -> IdentityState:
        state = IdentityState(
            identity_id=identity_id,
            core=core,
            traits=traits or TraitState(),
            created_at=now,
            updated_at=now,
        )
        await self._repository.create(state, source_ids=source_ids)
        return state

    async def get(self, identity_id: str) -> IdentityState | None:
        return await self._repository.get(identity_id)

    async def update_core(
        self,
        identity_id: str,
        core: ImmutableCore,
        *,
        authorization: OwnerAuthorization | None,
        now: datetime,
        source_ids: Sequence[str],
    ) -> IdentityState:
        if authorization is not OwnerAuthorization.OWNER_EDIT:
            raise PermissionError("immutable core changes require explicit owner authorization")
        current = await self._required(identity_id)
        updated = current.model_copy(
            update={"core": core, "revision": current.revision + 1, "updated_at": now}
        )
        await self._repository.save(
            updated,
            expected_revision=current.revision,
            patch={"core": core.model_dump(mode="json")},
            source_ids=source_ids,
        )
        return updated

    async def update_traits(
        self,
        identity_id: str,
        traits: TraitState,
        *,
        now: datetime,
        source_ids: Sequence[str],
    ) -> IdentityState:
        if not source_ids:
            raise ValueError("trait changes require evidence source ids")
        current = await self._required(identity_id)
        updated = current.model_copy(
            update={"traits": traits, "revision": current.revision + 1, "updated_at": now}
        )
        await self._repository.save(
            updated,
            expected_revision=current.revision,
            patch={"traits": traits.model_dump(mode="json")},
            source_ids=source_ids,
        )
        return updated

    async def _required(self, identity_id: str) -> IdentityState:
        state = await self._repository.get(identity_id)
        if state is None:
            raise KeyError(identity_id)
        return state
