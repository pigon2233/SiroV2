"""SIRO_CHAT_ROUTE=groq: chat that needs a local_only memory stays on the local model.

Synthetic memories and fake providers only; no network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.adapters.models.router import ChatRoute, ModelRouter, RouteProvider
from siro.contracts.events import Priority, UserTextEvent, UserTextPayload
from siro.contracts.events import Privacy as EventPrivacy
from siro.core.memory import Memory, MemoryKind
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion


class Capture:
    def __init__(self, name: str) -> None:
        self.name = name
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        yield ModelChunk("text", "好")
        yield ModelChunk("finished")


def _text(request: ModelRequest) -> str:
    return request.prompt + "\n".join(message.content for message in request.messages)


async def _companion(
    tmp_path: Path, route: ChatRoute
) -> tuple[IntegratedCompanion, Capture, Capture]:
    local, groq = Capture("ollama:synthetic"), Capture("groq:synthetic")
    router = ModelRouter(
        (
            RouteProvider("local", "ollama:synthetic", local),
            RouteProvider("groq", "groq:synthetic", groq),
        ),
        chat_route=route,
    )
    controller = IntegratedCompanion(
        tmp_path,
        router,
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.CLOUD_ALLOWED,
    )
    controller.turn_privacy_for = router.turn_privacy
    controller.chat_turn_to_groq = router.chat_turn_to_groq
    await controller._ensure_core()
    repo = SQLiteMemoryRepository(SQLiteStore(tmp_path / "siro.db"))
    for text, privacy in (
        ("主人喜歡 bluetea", EventPrivacy.LOCAL_ONLY),
        ("主人喜歡 greentea", EventPrivacy.CLOUD_ALLOWED),
    ):
        now = datetime.now(UTC)
        event = UserTextEvent(
            event_id=uuid4(),
            type="conversation.user_text.v1",
            source="synthetic",
            occurred_at=now,
            received_at=now,
            trace_id="synthetic",
            session_id="synthetic",
            turn_id=str(uuid4()),
            sequence=1,
            priority=Priority.INTERACTIVE,
            privacy=privacy,
            payload=UserTextPayload(text=text, language="zh"),
        )
        await repo.add(
            Memory(uuid4(), "siro", text, (event.event_id,), now, kind=MemoryKind.EPISODIC),
            event,
        )
    return controller, local, groq


@pytest.fixture(autouse=True)
def _quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_AUTO_MEMORY", "0")
    monkeypatch.setenv("SIRO_AUTO_PLAN_ENABLED", "0")


@pytest.mark.asyncio
async def test_local_only_memory_keeps_chat_local_and_out_of_groq(tmp_path: Path) -> None:
    controller, local, groq = await _companion(tmp_path, "groq")

    assert await controller._privacy_for_turn("你記得 bluetea 嗎") is Privacy.LOCAL_ONLY
    assert await controller._privacy_for_turn("你記得 greentea 嗎") is Privacy.CLOUD_ALLOWED
    assert await controller._privacy_for_turn("今天天氣好嗎") is Privacy.CLOUD_ALLOWED
    # Sensitive text stays local whatever the memories say.
    assert await controller._privacy_for_turn("我的密碼是 greentea") is Privacy.LOCAL_ONLY

    await controller.respond("owner", "你記得 bluetea 嗎")
    assert groq.requests == []
    assert local.requests and "bluetea" in _text(local.requests[-1])
    assert local.requests[-1].privacy is Privacy.LOCAL_ONLY

    await controller.respond("owner", "你記得 greentea 嗎")
    assert len(groq.requests) == 1
    sent = _text(groq.requests[0])
    assert "主人喜歡 greentea" in sent
    assert "主人喜歡 bluetea" not in sent


@pytest.mark.asyncio
async def test_failed_memory_check_keeps_chat_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _local, _groq = await _companion(tmp_path, "groq")
    service = controller._memory_service
    assert service is not None

    async def broken(*_args: object, **_kwargs: object) -> list[Memory]:
        raise RuntimeError("synthetic store failure")

    monkeypatch.setattr(service, "recall_context", broken)
    assert await controller._privacy_for_turn("今天天氣好嗎") is Privacy.LOCAL_ONLY


@pytest.mark.asyncio
async def test_local_chat_route_is_unchanged(tmp_path: Path) -> None:
    controller, local, groq = await _companion(tmp_path, "local")
    assert await controller._privacy_for_turn("你記得 greentea 嗎") is Privacy.LOCAL_ONLY
    await controller.respond("owner", "今天天氣好嗎")
    assert groq.requests == [] and local.requests
