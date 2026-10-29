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
        # last is not in the text
        return ["我下週三面試", "我的密碼是abc", "我的薪資是五萬", "我愛吃蘋果"]

    auto = AutonomousMemory(service, nominate)
    src = event("我下週三面試，我的密碼是abc，我的薪資是五萬，今天好熱")  # noqa: RUF001
    saved, confirm = await auto.consider("siro", src)
    assert [m.text for m in saved] == ["我下週三面試"]
    assert saved[0].source_event_ids == (src.event_id,)
    # D80 D7: credentials are dropped outright; other sensitive details become a keep card.
    assert confirm == ["我的薪資是五萬"]
    kept = await auto.keep_confirmed("siro", src, "我的薪資是五萬")
    assert kept.source_event_ids == (src.event_id,)
    with pytest.raises(PermissionError):
        await auto.keep_confirmed("siro", src, "我的密碼是abc")
    with pytest.raises(PermissionError):
        await auto.keep_confirmed("siro", src, "我的薪資是十萬")  # not the owner's words
    assert await auto.undo(kept.memory_id)
    assert await auto.undo(saved[0].memory_id)
    assert not await service.browse("siro")
    with pytest.raises(PermissionError):
        await auto.consider("siro", event("x", "tool.result"))
    none, _ = await auto.consider("siro", event("不要記 我下週三面試"))
    assert none == []


def test_nomination_prompt_and_parser() -> None:
    from siro.core.memory_autonomy import memory_nomination_prompt, parse_nominations

    assert "我愛貓" in memory_nomination_prompt("我愛貓")
    assert parse_nominations('x {"memories": ["我愛貓", 3]} y') == ["我愛貓"]
    assert parse_nominations("not json") == []
    assert parse_nominations('{"memories": "oops"}') == []


@pytest.mark.asyncio
async def test_confirm_card_is_answered_once_and_discard_writes_nothing(tmp_path: Path) -> None:
    """D80 D7: the chat keep/discard card replaces "say 請記住 to save"."""
    from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
    from siro.adapters.models.mock import MockModel
    from siro.ports.models import Privacy
    from siro.services.presentation.gateway import GatewayHub
    from siro.services.presentation.integrated import IntegratedCompanion

    companion = IntegratedCompanion(
        tmp_path,
        MockModel(),
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
    )
    await companion._ensure_core()
    src = event("我的薪資是五萬")
    companion._pending_memories["a"] = (src, "我的薪資是五萬", datetime.now(UTC))
    companion._pending_memories["b"] = (src, "我的薪資是五萬", datetime.now(UTC))
    assert await companion.confirm_memory("a", False) == {"status": "discarded"}
    assert await companion.confirm_memory("a", True) == {"status": "expired"}
    kept = await companion.confirm_memory("b", True)
    assert kept["status"] == "kept" and kept["text"] == "我的薪資是五萬"
    assert await companion.confirm_memory("unknown", True) == {"status": "expired"}
