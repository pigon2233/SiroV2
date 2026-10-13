from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from siro.core.memory import Memory, MemoryService
from siro.services.agent.organization import MemoryOrganizer


class Sources:
    def __init__(self) -> None:
        self.items = [Memory(uuid4(), "siro", "tea", (uuid4(),), datetime.now(UTC))]

    async def browse(self, *args: object, **kwargs: object) -> list[Memory]:
        return self.items


@pytest.mark.asyncio
async def test_single_owner_preemption_stale_view_and_bounded_reaping() -> None:
    from dataclasses import replace
    from typing import cast

    sources = Sources()
    busy = True
    organizer = MemoryOrganizer(
        cast(MemoryService, sources), lambda: busy, idle_seconds=0, poll_seconds=0.005
    )
    await organizer.start()
    owner = organizer._task
    await organizer.start()
    assert organizer._task is owner
    try:
        for _ in range(100):
            organizer.request()
        await asyncio.sleep(0.02)
        assert not (await organizer.snapshot())["groups"]
        busy = False
        organizer.request()
        for _ in range(100):
            if organizer.state == "ready":
                break
            await asyncio.sleep(0.005)
        report = await organizer.snapshot()
        assert len(report["groups"]) == 1  # type: ignore[arg-type]
        assert organizer._work is None
        sources.items = [replace(sources.items[0], text="coffee", revision=2)]
        assert not (await organizer.snapshot())["groups"]
        organizer.request()
        await asyncio.sleep(0.02)
        assert "coffee" in str((await organizer.snapshot())["groups"])
        sources.items = []
        assert not (await organizer.snapshot())["groups"]
        await organizer.configure(False)
        organizer.request()
        await asyncio.sleep(0.01)
        assert (await organizer.snapshot())["state"] == "disabled"
    finally:
        await organizer.close()
    assert organizer._task is None and organizer._work is None


@pytest.mark.asyncio
async def test_foreground_interrupts_active_read_and_seven_day_owner_stays_bounded() -> None:
    from typing import cast

    class SlowSources(Sources):
        def __init__(self) -> None:
            super().__init__()
            self.entered = asyncio.Event()
            self.slow = True

        async def browse(self, *args: object, **kwargs: object) -> list[Memory]:
            self.entered.set()
            if self.slow:
                await asyncio.Future()
            return self.items

    sources = SlowSources()
    now = 0.0
    organizer = MemoryOrganizer(
        cast(MemoryService, sources),
        lambda: False,
        idle_seconds=15,
        poll_seconds=0.005,
        clock=lambda: now,
    )
    await organizer.start()
    try:
        organizer.request()
        await asyncio.wait_for(sources.entered.wait(), 1)
        await asyncio.wait_for(organizer.foreground(), 0.5)
        assert organizer._work is None and organizer.state == "foreground"
        sources.slow = False
        for day in range(1, 8):
            now = day * 86400.0
            for _ in range(100):
                organizer.request()
            for _ in range(100):
                if organizer.state == "ready":
                    break
                await asyncio.sleep(0.005)
            report = await organizer.snapshot()
            assert len(report["groups"]) == 1  # type: ignore[arg-type]
            assert organizer._work is None
            await organizer.foreground()
    finally:
        await organizer.close()
    assert organizer._task is None and organizer._work is None
