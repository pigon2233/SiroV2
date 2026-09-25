from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.adapters.models.mock import MockModel
from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.companion import CompanionCore
from siro.core.conversation import ConversationEngine, TurnState
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryService
from siro.persistence.conversation import SQLiteConversationRepository
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.body import BodyConnection, EmotionIntent, SpeechIntent

pytestmark = pytest.mark.asyncio


class KilledRenderer:
    async def send_json(self, data: object) -> None:
        del data
        raise ConnectionError("renderer killed")

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        del code, reason


class HealthyRenderer:
    def __init__(self) -> None:
        self.messages: list[object] = []

    async def send_json(self, data: object) -> None:
        self.messages.append(data)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        del code, reason


async def make_core(path: Path) -> tuple[CompanionCore, MemoryService]:
    store = SQLiteStore(path)
    await store.initialize()
    identities = SQLiteIdentityRepository(store)
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
    memory = MemoryService(SQLiteMemoryRepository(store))
    core = CompanionCore(
        identities,
        memory,
        ConversationEngine(MockModel(("文字核心仍然可用",)), SQLiteConversationRepository(store)),
    )
    return core, memory


async def test_killed_renderer_does_not_stop_core_and_reconnects(tmp_path: Path) -> None:
    core, memory = await make_core(tmp_path / "siro.db")
    now = datetime.now(UTC)
    source = UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="owner",
        occurred_at=now,
        received_at=now,
        trace_id="a07",
        session_id="a07",
        turn_id="memory-source",
        sequence=1,
        priority=Priority.INTERACTIVE,
        privacy=Privacy.LOCAL_ONLY,
        payload=UserTextPayload(text="renderer failure drill", language="en"),
    )
    remembered = Memory(uuid4(), "siro", "renderer failure drill", (source.event_id,), now)
    await memory.remember(remembered, source)

    transport = WebSocketBodyTransport()
    body = MinimalWebBodyAdapter(transport)
    await transport.attach(KilledRenderer())
    assert await body.set_emotion(EmotionIntent("surprised"))
    await asyncio.sleep(0)
    assert (await body.status()).connection is BodyConnection.OFFLINE

    result = await core.respond("a07", "siro", "身體斷線後請繼續")
    assert result.state is TurnState.COMPLETED
    assert result.text == "文字核心仍然可用"
    assert await memory.recall("siro", "renderer failure") == [remembered]

    renderer = HealthyRenderer()
    await transport.attach(renderer)
    assert await body.speak(SpeechIntent("speech-2", result.text, result.generation_id))
    await asyncio.sleep(0)
    assert renderer.messages == [
        {
            "v": 1,
            "type": "body.speech",
            "intent_id": "speech-2",
            "generation_id": result.generation_id,
            "text": "文字核心仍然可用",
        }
    ]
    await transport.detach()
