"""Generation-safe playback and barge-in coordination."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from siro.services.audio.tts import SpeechPlayback

CancelHook = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class AudioSession:
    generation: int = 0
    active: SpeechPlayback | None = None
    _hooks: list[CancelHook] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def begin(self, playback: SpeechPlayback, *cancel_hooks: CancelHook) -> int:
        async with self._lock:
            await self._cancel_locked()
            self.generation += 1
            self.active = playback
            self._hooks = list(cancel_hooks)
            return self.generation

    async def barge_in(self) -> int:
        async with self._lock:
            await self._cancel_locked()
            self.generation += 1
            return self.generation

    async def accept_audio(self, generation: int, chunk: bytes) -> bool:
        del chunk
        async with self._lock:
            return self.active is not None and generation == self.generation

    async def reconnect(self) -> int:
        """Reconnect starts empty; pre-disconnect speech can never replay."""
        return await self.barge_in()

    async def _cancel_locked(self) -> None:
        if self.active is not None:
            self.active.cancel()
        hooks, self._hooks = self._hooks, []
        self.active = None
        for hook in hooks:
            await hook()
