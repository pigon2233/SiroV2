from __future__ import annotations

import asyncio

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.ports.body import BodyConnection, EmotionIntent, SpeechIntent

pytestmark = pytest.mark.asyncio


class RecordingTransport:
    def __init__(self, connected: bool = True) -> None:
        self.connected = connected
        self.messages: list[dict[str, object]] = []

    async def send(self, message: dict[str, object]) -> None:
        self.messages.append(message)


class RecordingSocket:
    def __init__(self) -> None:
        self.messages: list[object] = []
        self.closed = False

    async def send_json(self, data: object) -> None:
        self.messages.append(data)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        del code, reason
        self.closed = True


async def test_minimal_body_maps_speech_emotion_and_cancel() -> None:
    transport = RecordingTransport()
    body = MinimalWebBodyAdapter(transport)

    assert await body.speak(SpeechIntent("s1", "你好", "g1"))
    assert await body.set_emotion(EmotionIntent("happy", 0.75))
    assert await body.cancel("g1", "user")

    assert [message["type"] for message in transport.messages] == [
        "body.speech",
        "body.emotion",
        "body.cancel",
    ]
    assert transport.messages[0]["text"] == "你好"
    assert transport.messages[1]["intensity"] == 0.75
    assert transport.messages[2]["reason"] == "user"


async def test_minimal_body_fails_closed_while_offline() -> None:
    transport = RecordingTransport(connected=False)
    body = MinimalWebBodyAdapter(transport)

    assert not await body.speak(SpeechIntent("s1", "still alive", "g1"))
    assert not await body.set_emotion(EmotionIntent("neutral"))
    assert not await body.cancel("g1")
    assert (await body.status()).connection is BodyConnection.OFFLINE
    assert transport.messages == []


async def test_renderer_transport_reconnect_drops_old_session_queue() -> None:
    transport = WebSocketBodyTransport()
    first, second = RecordingSocket(), RecordingSocket()
    await transport.attach(first)
    await transport.send({"type": "body.emotion", "name": "happy"})
    await asyncio.sleep(0)
    assert first.messages

    await transport.attach(second)
    assert first.closed
    await transport.send({"type": "body.emotion", "name": "neutral"})
    await asyncio.sleep(0)
    assert second.messages == [{"type": "body.emotion", "name": "neutral"}]
    await transport.detach()
    assert not transport.connected
