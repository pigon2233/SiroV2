"""Minimal renderer adapter over a small, versioned message boundary."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Protocol
from uuid import uuid4

from siro.adapters.body.visual_pack import VisualPack
from siro.ports.body import BodyConnection, BodyStatus, EmotionIntent, SpeechIntent

# Rough speaking-pose lifetime; the parent page owns audio and reports no end-of-playback here.
SPEAKING_SECONDS_PER_CHAR = 0.22
SPEAKING_MIN_SECONDS = 2.0
SPEAKING_MAX_SECONDS = 30.0


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
        self._activity: dict[str, object] | None = None

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
        if self._activity is not None:
            # Same ids, so a renderer that kept running keeps its phase; nothing one-shot replays.
            self._queue.put_nowait(dict(self._activity))

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

    def remember_activity(self, message: dict[str, object] | None) -> None:
        self._activity = None if message is None else dict(message)

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

    def __init__(
        self, transport: BodyTransport, *, activity_pack: VisualPack | None = None
    ) -> None:
        self._transport = transport
        self._activity_pack = activity_pack
        self._activity: tuple[str, str] | None = None

    async def speak(self, intent: SpeechIntent) -> bool:
        sent = await self._send(
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
        if sent:
            seconds = len(intent.text) * SPEAKING_SECONDS_PER_CHAR
            await self.set_activity(
                "speaking_pose",
                generation_id=intent.generation_id,
                ttl_seconds=min(SPEAKING_MAX_SECONDS, max(SPEAKING_MIN_SECONDS, seconds)),
            )
        return sent

    async def set_activity(
        self, activity: str, *, generation_id: str, ttl_seconds: float | None = None
    ) -> bool:
        """Send a presentation-only activity cue; disabled or unsupported cues are dropped."""
        pack = self._activity_pack
        if pack is None or activity not in pack.activities or not generation_id:
            return False
        if ttl_seconds is not None and not 0 < ttl_seconds <= 120:
            raise ValueError("activity ttl must be within (0, 120] seconds")
        message: dict[str, object] = {
            "v": 1,
            "type": "body.activity",
            "op": "start",
            "instance_id": str(uuid4()),
            "generation_id": generation_id,
            "activity": activity,
            "pack_version": pack.version,
        }
        if ttl_seconds is not None:
            message["ttl_s"] = ttl_seconds
        durable = ttl_seconds is None and pack.activities[activity].loop
        if isinstance(self._transport, WebSocketBodyTransport):
            self._transport.remember_activity(message if durable else None)
        self._activity = (str(message["instance_id"]), generation_id)
        return await self._send(message)

    async def stop_activity(self) -> bool:
        """Stop the activity this adapter last started; the renderer rests in idle afterwards."""
        current, self._activity = self._activity, None
        if current is None or self._activity_pack is None:
            return False
        if isinstance(self._transport, WebSocketBodyTransport):
            self._transport.remember_activity(None)
        instance_id, generation_id = current
        return await self._send(
            {
                "v": 1,
                "type": "body.activity",
                "op": "stop",
                "instance_id": instance_id,
                "generation_id": generation_id,
                "pack_version": self._activity_pack.version,
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
