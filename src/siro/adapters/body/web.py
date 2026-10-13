"""Minimal renderer adapter over a small, versioned message boundary."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Protocol

from siro.ports.body import BodyConnection, BodyStatus, EmotionIntent, SpeechIntent


class BodyTransport(Protocol):
    @property
    def connected(self) -> bool: ...

    async def send(self, message: dict[str, object]) -> None: ...


class JsonBodySocket(Protocol):
    async def send_json(self, data: object) -> None: ...

    async def close(self, code: int = 1000, reason: str | None = None) -> None: ...


class WebSocketBodyTransport:
    """Single-owner, bounded renderer transport with isolated writer failure."""

    def __init__(self, *, capacity: int = 64) -> None:
        if capacity < 1:
            raise ValueError("body queue capacity must be positive")
        self._capacity = capacity
        self._socket: JsonBodySocket | None = None
        self._queue: asyncio.Queue[dict[str, object]] | None = None
        self._writer: asyncio.Task[None] | None = None
        self._emotion: dict[str, object] | None = None

    @property
    def connected(self) -> bool:
        return self._socket is not None and self._writer is not None and not self._writer.done()

    async def attach(self, socket: JsonBodySocket) -> None:
        await self.detach(reason="renderer replaced")
        self._socket = socket
        self._queue = asyncio.Queue(self._capacity)
        self._writer = asyncio.create_task(self._write_loop(socket), name="body-renderer-writer")
        if self._emotion is not None:
            self._queue.put_nowait(dict(self._emotion))

    async def detach(
        self, *, reason: str = "renderer disconnected", socket: JsonBodySocket | None = None
    ) -> None:
        if socket is not None and socket is not self._socket:
            return
        socket, writer = self._socket, self._writer
        self._socket = None
        self._queue = None
        self._writer = None
        if writer is not None and writer is not asyncio.current_task():
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)
        if socket is not None:
            with contextlib.suppress(Exception):
                await socket.close(reason=reason)

    def remember_emotion(self, message: dict[str, object]) -> None:
        if message.get("type") == "body.emotion":
            self._emotion = dict(message)

    async def send(self, message: dict[str, object]) -> None:
        self.remember_emotion(message)
        queue = self._queue
        if not self.connected or queue is None:
            raise ConnectionError("body renderer is offline")
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull as error:
            await self.detach(reason="body queue capacity exceeded")
            raise ConnectionError("body renderer queue is full") from error

    async def _write_loop(self, socket: JsonBodySocket) -> None:
        try:
            while True:
                queue = self._queue
                if queue is None:
                    return
                await socket.send_json(await queue.get())
        except Exception:
            if self._socket is socket:
                self._socket = None
                self._queue = None
                self._writer = None


class MinimalWebBodyAdapter:
    """Maps Core body intents to renderer messages without retaining domain state."""

    name = "minimal-web-v1"

    def __init__(self, transport: BodyTransport) -> None:
        self._transport = transport

    async def speak(self, intent: SpeechIntent) -> bool:
        return await self._send(
            {
                "v": 1,
                "type": "body.speech",
                "intent_id": intent.intent_id,
                "generation_id": intent.generation_id,
                "text": intent.text,
                "prosody": {
                    "rate": intent.rate,
                    "pitch": intent.pitch,
                    "energy": intent.energy,
                },
            }
        )

    async def set_emotion(self, intent: EmotionIntent) -> bool:
        message: dict[str, object] = {
            "v": 1,
            "type": "body.emotion",
            "name": intent.name,
            "intensity": intent.intensity,
        }
        if isinstance(self._transport, WebSocketBodyTransport):
            self._transport.remember_emotion(message)
        return await self._send(message)

    async def cancel(self, generation_id: str, reason: str = "cancelled") -> bool:
        if not generation_id:
            raise ValueError("generation id cannot be empty")
        return await self._send(
            {
                "v": 1,
                "type": "body.cancel",
                "generation_id": generation_id,
                "reason": reason,
            }
        )

    async def status(self) -> BodyStatus:
        connection = BodyConnection.ONLINE if self._transport.connected else BodyConnection.OFFLINE
        return BodyStatus(connection=connection, renderer=self.name)

    async def _send(self, message: dict[str, object]) -> bool:
        if not self._transport.connected:
            return False
        try:
            await self._transport.send(message)
        except (ConnectionError, OSError):
            return False
        return True
