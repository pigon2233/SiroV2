from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.routine import RoutineWatcher

TZ = ZoneInfo("Asia/Taipei")


async def _put(store: SQLiteStore, prop: str, value: str, at: datetime) -> None:
    def write(c) -> None:  # type: ignore[no-untyped-def]
        c.execute(
            "INSERT INTO world_observations(observation_id, entity_id, property, value_json, "
            "confidence, observed_at, expires_at, source_id) VALUES (?,?,?,?,1,?,NULL,'t')",
            (str(uuid4()), "node", prop, value, at.astimezone(UTC).isoformat()),
        )

    await store.run_transaction(write)


@pytest.mark.asyncio
async def test_watcher_reads_history_and_respects_cooldown(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    today = datetime(2026, 5, 20, tzinfo=TZ)
    for day in range(1, 8):
        base = today - timedelta(days=day)
        for i in range(32):
            await _put(store, "motion", "true", base + timedelta(hours=8, minutes=30 * i))
    now = today + timedelta(hours=15)
    await _put(store, "motion", "true", now - timedelta(hours=4))
    await _put(store, "illuminance", "90", now - timedelta(minutes=1))
    watcher = RoutineWatcher(store)
    found = await watcher.check(now.astimezone(UTC))
    assert found is not None and found["trigger"] == "unexpected_absence"
    assert await watcher.check((now + timedelta(minutes=10)).astimezone(UTC)) is None
