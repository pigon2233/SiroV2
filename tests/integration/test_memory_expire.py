"""D80 P2c: invalidation keeps the memory, hides it from prompt-time recall, can be reopened."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryService
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository


def event(text: str, when: datetime) -> UserTextEvent:
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="siro.presentation",
        occurred_at=when,
        received_at=when,
        trace_id="expire",
        session_id="browser",
        turn_id="t",
        sequence=0,
        priority=Priority.INTERACTIVE,
        privacy=Privacy.LOCAL_ONLY,
        payload=UserTextPayload(text=text, language="zh-TW"),
    )


@pytest.mark.asyncio
async def test_expire_hides_from_recall_keeps_revision_and_reopens(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="persistent companion",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        now=datetime.now(UTC),
    )
    service = MemoryService(SQLiteMemoryRepository(store))
    when = datetime.now(UTC) - timedelta(minutes=5)
    source = event("主人喜歡無糖綠茶", when)
    memory = Memory(uuid4(), "siro", "主人喜歡無糖綠茶", (source.event_id,), when)
    await service.remember(memory, source)
    assert [m.memory_id for m in await service.recall("siro", "綠茶", as_of=datetime.now(UTC))] == [
        memory.memory_id
    ]

    expired = await service.expire(memory.memory_id, datetime.now(UTC), reason="curation: test")
    assert expired is not None and expired.valid_to is not None and expired.revision == 2
    assert await service.recall("siro", "綠茶", as_of=datetime.now(UTC)) == []
    assert [r.reason for r in await service.revisions(memory.memory_id)][-1] == "curation: test"

    reopened = await service.expire(memory.memory_id, None, reason="owner undid curation")
    assert reopened is not None and reopened.valid_to is None
    assert [m.memory_id for m in await service.recall("siro", "綠茶", as_of=datetime.now(UTC))] == [
        memory.memory_id
    ]
    assert await service.expire(uuid4(), None, reason="missing") is None
