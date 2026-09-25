from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from siro.core.identity import (
    IdentityService,
    ImmutableCore,
    OwnerAuthorization,
    TraitState,
)
from siro.core.world import WorldModel, WorldObservation, WorldStatus
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository, SQLiteWorldRepository


def core(name: str = "SIRO") -> ImmutableCore:
    return ImmutableCore(
        name=name,
        baseline_identity="A persistent digital companion",
        core_values=("care", "honesty"),
        creator_relationship="Created with and cared for by the owner",
    )


@pytest.mark.asyncio
async def test_identity_survives_restart_and_traits_are_versioned(tmp_path: Path) -> None:
    path = tmp_path / "siro.sqlite3"
    now = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)
    first_store = SQLiteStore(path)
    await first_store.initialize()
    first = IdentityService(SQLiteIdentityRepository(first_store))
    await first.create("siro", core(), now=now, source_ids=("setup",))
    updated = await first.update_traits(
        "siro",
        TraitState(values={"curiosity": 0.7}),
        now=now + timedelta(minutes=1),
        source_ids=("event-1", "event-2", "event-3"),
    )

    restarted_store = SQLiteStore(path)
    await restarted_store.initialize()
    restarted = IdentityService(SQLiteIdentityRepository(restarted_store))
    loaded = await restarted.get("siro")

    assert loaded == updated
    assert loaded is not None
    assert loaded.revision == 2
    assert loaded.traits.values == {"curiosity": 0.7}


@pytest.mark.asyncio
async def test_immutable_core_requires_owner_authorization(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()
    service = IdentityService(SQLiteIdentityRepository(store))
    now = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)
    await service.create("siro", core(), now=now)

    with pytest.raises(PermissionError, match="owner authorization"):
        await service.update_core(
            "siro", core("Other"), authorization=None, now=now, source_ids=("owner",)
        )

    updated = await service.update_core(
        "siro",
        core("Siro"),
        authorization=OwnerAuthorization.OWNER_EDIT,
        now=now + timedelta(minutes=1),
        source_ids=("owner",),
    )
    assert updated.core.name == "Siro"
    assert updated.revision == 2


@pytest.mark.asyncio
async def test_world_rejects_old_current_but_keeps_latest_source(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()
    world = WorldModel(SQLiteWorldRepository(store))
    now = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)
    newest = observation(2, value=26, observed_at=now, source_id="sensor.bedroom")
    older = observation(
        1,
        value=21,
        observed_at=now - timedelta(minutes=1),
        source_id="sensor.stale",
    )

    assert await world.observe(newest)
    assert not await world.observe(older)
    current = await world.current("bedroom", "temperature", now=now)

    assert current.status is WorldStatus.KNOWN
    assert current.observation is not None
    assert current.observation.value == 26
    assert current.observation.source_id == "sensor.bedroom"


@pytest.mark.asyncio
async def test_expired_or_missing_world_value_is_unknown(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()
    world = WorldModel(SQLiteWorldRepository(store))
    now = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)
    await world.observe(
        observation(
            1,
            value=True,
            observed_at=now,
            source_id="sensor.presence",
            expires_at=now + timedelta(seconds=30),
            property_name="presence",
        )
    )

    expired = await world.current("bedroom", "presence", now=now + timedelta(seconds=30))
    missing = await world.current("bedroom", "door", now=now)

    assert expired.status is WorldStatus.UNKNOWN
    assert expired.reason == "expired"
    assert expired.observation is not None
    assert missing.status is WorldStatus.UNKNOWN
    assert missing.reason == "missing"
    assert missing.observation is None


def observation(
    number: int,
    *,
    value: object,
    observed_at: datetime,
    source_id: str,
    expires_at: datetime | None = None,
    property_name: str = "temperature",
) -> WorldObservation:
    return WorldObservation(
        observation_id=UUID(int=number),
        entity_id="bedroom",
        property=property_name,
        value=value,
        confidence=0.9,
        observed_at=observed_at,
        expires_at=expires_at,
        source_id=source_id,
    )
