"""Presentation-only body boundary.

The body receives disposable presentation intents. It never owns identity,
conversation, or memory state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class BodyConnection(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class SpeechIntent:
    intent_id: str
    text: str
    generation_id: str
    rate: float = 1.0
    pitch: float = 0.0
    energy: float = 0.5

    def __post_init__(self) -> None:
        if not self.intent_id or not self.generation_id:
            raise ValueError("speech intent and generation ids cannot be empty")
        if not self.text:
            raise ValueError("speech text cannot be empty")
        if not 0.5 <= self.rate <= 2.0:
            raise ValueError("speech rate must be between 0.5 and 2")
        if not -1.0 <= self.pitch <= 1.0:
            raise ValueError("speech pitch must be between -1 and 1")
        if not 0.0 <= self.energy <= 1.0:
            raise ValueError("speech energy must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class EmotionIntent:
    name: str
    intensity: float = 1.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("emotion name cannot be empty")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError("emotion intensity must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class BodyStatus:
    connection: BodyConnection
    renderer: str


class BodyAdapter(Protocol):
    async def speak(self, intent: SpeechIntent) -> bool: ...

    async def set_emotion(self, intent: EmotionIntent) -> bool: ...

    async def cancel(self, generation_id: str, reason: str = "cancelled") -> bool: ...

    async def status(self) -> BodyStatus: ...
