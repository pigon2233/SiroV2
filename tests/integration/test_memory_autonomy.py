from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from siro.contracts.events import Priority, UserTextEvent, UserTextPayload
from siro.contracts.events import Privacy as EventPrivacy
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import MemoryService
from siro.core.memory_autonomy import AutonomousMemory
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository


def event(text: str, source: str = "siro.presentation") -> UserTextEvent:
    now = datetime.now(UTC)
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source=source,
        occurred_at=now,
        received_at=now,
        trace_id="t",
        session_id="A",
        turn_id="x",
        sequence=0,
        priority=Priority.INTERACTIVE,
        privacy=EventPrivacy.LOCAL_ONLY,
        payload=UserTextPayload(text=text, language="zh"),
    )


@pytest.mark.asyncio
async def test_autonomous_write_is_screened_sourced_and_undoable(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "s.db")
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="t",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        now=datetime.now(UTC),
    )
    service = MemoryService(SQLiteMemoryRepository(store))

    async def nominate(_: str) -> list[str]:
        return ["我下週三面試", "我的密碼是abc", "我愛吃蘋果"]  # last is not in the text

    auto = AutonomousMemory(service, nominate)
    src = event("我下週三面試，我的密碼是abc，今天好熱")
    saved, confirm = await auto.consider("siro", src)
    assert [m.text for m in saved] == ["我下週三面試"]
    assert saved[0].source_event_ids == (src.event_id,)
    assert confirm == ["我的密碼是abc"]
    assert await auto.undo(saved[0].memory_id)
    assert not await service.browse("siro")
    with pytest.raises(PermissionError):
        await auto.consider("siro", event("x", "tool.result"))
    none, _ = await auto.consider("siro", event("不要記 我下週三面試"))
    assert none == []
