from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from siro.contracts.events import Priority, UserTextEvent, UserTextPayload
from siro.contracts.events import Privacy as EventPrivacy
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import MemoryService
from siro.core.profile import ProfileService
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.profile import SQLiteProfileSource
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository


@dataclass
class Reply:
    text: str


class Completer:
    def __init__(self, text: str) -> None:
        self.text, self.prompts = text, []

    async def complete(self, role: str, prompt: str) -> Reply:
        self.prompts.append(prompt)
        return Reply(self.text)


def event(text: str, privacy: EventPrivacy = EventPrivacy.CLOUD_ALLOWED) -> UserTextEvent:
    now = datetime.now(UTC)
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="siro.presentation",
        occurred_at=now,
        received_at=now,
        trace_id="synthetic",
        session_id="A",
        turn_id="t",
        sequence=0,
        priority=Priority.INTERACTIVE,
        privacy=privacy,
        payload=UserTextPayload(text=text, language="zh"),
    )


@pytest.mark.asyncio
async def test_profile_links_entries_to_original_text(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="test",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        now=datetime.now(UTC),
    )
    memory = MemoryService(SQLiteMemoryRepository(store))
    likes, secret, local = (
        event("我平常喜歡喝無糖綠茶"),
        event("我的密碼是 abc"),
        event("我習慣晚上寫程式", EventPrivacy.LOCAL_ONLY),
    )
    for item in (likes, secret, local):
        await store.record_event(item)
    answer = (
        '{"entries":['
        '{"index":0,"category":"preference","text":"喜歡無糖綠茶","quote":"喜歡喝無糖綠茶"},'
        '{"index":1,"category":"preference","text":"密碼 abc","quote":"密碼是 abc"},'
        '{"index":0,"category":"habit","text":"編造","quote":"不在原文"}]}'
    )
    completer = Completer(answer)
    service = ProfileService(memory, completer)
    pending = await SQLiteProfileSource(store).unseen_user_events()
    assert len(pending) == 3
    created = await service.build(pending)
    assert [(e.category, e.text, e.source_event_id) for e in created] == [
        ("preference", "喜歡無糖綠茶", likes.event_id)
    ]
    assert "我習慣晚上寫程式" not in completer.prompts[0]  # local-only never reaches cloud
    again = await service.build(pending)
    assert again == []
    listed = await service.entries()
    assert [(e.quote, e.source_event_id) for e in listed] == [("喜歡喝無糖綠茶", likes.event_id)]
    remaining = await SQLiteProfileSource(store).unseen_user_events()
    assert {e.event_id for e in remaining} == {secret.event_id, local.event_id}
