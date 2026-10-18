from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from siro.adapters.models.mock import MockModel, OfflineDemoModel
from siro.adapters.runtime import LocalRuntimeClient
from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.companion import CompanionCore
from siro.core.conversation import ConversationEngine, TurnState
from siro.core.identity import IdentityService, IdentityState, ImmutableCore
from siro.core.memory import Memory, MemoryService, WorkingMemory, assemble_prompt
from siro.persistence.conversation import SQLiteConversationRepository
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.runtime import RuntimeUnavailable


def source_event() -> UserTextEvent:
    now = datetime.now(UTC)
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="test",
        occurred_at=now,
        received_at=now,
        trace_id="memory-test",
        session_id="shared-event",
        turn_id="turn-1",
        sequence=1,
        priority=Priority.INTERACTIVE,
        privacy=Privacy.LOCAL_ONLY,
        payload=UserTextPayload(text="我們一起完成了第一個版本", language="zh-TW"),
    )


async def initialize(path: Path) -> tuple[SQLiteStore, SQLiteIdentityRepository]:
    store = SQLiteStore(path)
    await store.initialize()
    identities = SQLiteIdentityRepository(store)
    if await identities.get("siro") is None:
        await IdentityService(identities).create(
            "siro",
            ImmutableCore(
                name="SIRO",
                baseline_identity="persistent companion",
                core_values=("honesty",),
                creator_relationship="owner",
            ),
            now=datetime.now(UTC),
        )
    return store, identities


@pytest.mark.asyncio
async def test_memory_survives_three_restarts_with_source(tmp_path: Path) -> None:
    path = tmp_path / "siro.db"
    event = source_event()
    store, _ = await initialize(path)
    service = MemoryService(SQLiteMemoryRepository(store))
    memory = Memory(uuid4(), "siro", "一起完成第一個版本", (event.event_id,), datetime.now(UTC))
    await service.remember(memory, event)

    for _ in range(3):
        restarted, _ = await initialize(path)
        found = await MemoryService(SQLiteMemoryRepository(restarted)).recall("siro", "第一個版本")
        assert found == [memory]
        assert found[0].source_event_ids == (event.event_id,)


@pytest.mark.asyncio
async def test_adapter_swap_keeps_identity_and_unknown_has_no_fake_source(
    tmp_path: Path,
) -> None:
    store, identities = await initialize(tmp_path / "siro.db")
    before = await identities.get("siro")
    assert before is not None
    memory = MemoryService(SQLiteMemoryRepository(store))
    first = CompanionCore(
        identities,
        memory,
        ConversationEngine(MockModel(("one",)), SQLiteConversationRepository(store)),
    )
    assert (await first.respond("one", "siro", "hello")).state is TurnState.COMPLETED
    second = CompanionCore(
        identities,
        memory,
        ConversationEngine(OfflineDemoModel(), SQLiteConversationRepository(store)),
    )
    result = await second.respond("two", "siro", "你記得不存在的事嗎")
    after = await identities.get("siro")
    assert after is not None and after.identity_id == before.identity_id
    assert "不知道" in result.text
    assert "NO_SOURCE" in assemble_prompt(after, "missing", ())
    assert "do not claim the owner has saved nothing" in assemble_prompt(after, "missing", ())
    assert "cloud" not in assemble_prompt(after, "missing", ()).split("Verified memories:")[1]


def test_working_memory_is_session_scoped_and_bounded() -> None:
    memory = WorkingMemory(max_messages=2)
    memory.append("one", "user", "first")
    memory.append("one", "assistant", "second")
    memory.append("one", "user", "third")
    memory.append("two", "user", "private")

    assert [message.text for message in memory.recent("one")] == ["second", "third"]
    assert [message.text for message in memory.recent("two")] == ["private"]


def test_prompt_sets_short_default_and_respects_explicit_detail_request() -> None:
    now = datetime.now(UTC)
    identity = IdentityState(
        identity_id="siro",
        core=ImmutableCore(
            name="SIRO",
            baseline_identity="persistent companion",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        created_at=now,
        updated_at=now,
    )

    prompt = assemble_prompt(identity, "你好", ())

    assert "one to three short sentences" in prompt
    assert "within 120 Chinese characters" in prompt
    assert "when the owner asks for it or the task needs it" in prompt
    assert "Do not pad, repeat, or announce that you will continue" in prompt


@pytest.mark.asyncio
async def test_runtime_offline_does_not_disable_core_conversation(tmp_path: Path) -> None:
    runtime = LocalRuntimeClient(tmp_path / "absent-runtime.sock", timeout_seconds=0.1)
    with pytest.raises(RuntimeUnavailable):
        await runtime.health()

    store, identities = await initialize(tmp_path / "siro.db")
    core = CompanionCore(
        identities,
        MemoryService(SQLiteMemoryRepository(store)),
        ConversationEngine(MockModel(("我還在。",)), SQLiteConversationRepository(store)),
    )
    result = await core.respond("offline-runtime", "siro", "你還在嗎?")
    assert result.state is TurnState.COMPLETED
    assert result.text == "我還在。"
