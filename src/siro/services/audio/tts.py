"""Sentence buffering, Groq speech synthesis, playback acknowledgement and lip sync."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import httpx

_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s*")  # noqa: RUF001


def speech_segments(text: str, *, max_chars: int = 180) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, (dict, list)):
        return []
    pieces = [piece.strip() for piece in _BOUNDARY.split(stripped) if piece.strip()]
    output: list[str] = []
    for piece in pieces:
        while len(piece) > max_chars:
            split = piece.rfind(" ", 0, max_chars + 1)
            split = split if split > 0 else max_chars
            output.append(piece[:split].strip())
            piece = piece[split:].strip()
        if piece:
            output.append(piece)
    return output


class TextToSpeech(Protocol):
    def synthesize(self, text: str) -> AsyncIterator[bytes]: ...


class GroqOrpheus:
    supported_languages = frozenset({"en", "ar-SA"})

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "canopylabs/orpheus-v1-english",
        voice: str = "austin",
        base_url: str = "https://api.groq.com/openai/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._url = f"{base_url.rstrip('/')}/audio/speech"

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        async with (
            httpx.AsyncClient(timeout=30.0) as client,
            client.stream(
                "POST",
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "voice": self._voice,
                    "input": text,
                    "response_format": "wav",
                    "sample_rate": 24_000,
                },
            ) as response,
        ):
            response.raise_for_status()
            async for chunk in response.aiter_bytes(4096):
                if chunk:
                    yield chunk


class SpeechState(StrEnum):
    QUEUED = "queued"
    PLAYING = "playing"
    FINISHED = "finished"
    CANCELED = "canceled"
    TEXT_FALLBACK = "text_fallback"


@dataclass(slots=True)
class SpeechPlayback:
    speech_id: str
    subtitle: str
    state: SpeechState = SpeechState.QUEUED
    played_samples: int = 0

    def acknowledge(self, sample_offset: int, *, final: bool = False) -> None:
        if self.state in {SpeechState.CANCELED, SpeechState.TEXT_FALLBACK}:
            return
        if sample_offset < self.played_samples:
            raise ValueError("playback acknowledgement moved backwards")
        self.played_samples = sample_offset
        self.state = SpeechState.FINISHED if final else SpeechState.PLAYING

    @property
    def mouth_open(self) -> float:
        return 0.0 if self.state != SpeechState.PLAYING else 0.65

    def cancel(self) -> None:
        self.state = SpeechState.CANCELED


async def synthesize_or_fallback(
    tts: TextToSpeech, playback: SpeechPlayback
) -> AsyncIterator[bytes]:
    try:
        for segment in speech_segments(playback.subtitle):
            async for chunk in tts.synthesize(segment):
                if playback.state == SpeechState.CANCELED:
                    return
                yield chunk
    except (httpx.HTTPError, TimeoutError):
        playback.state = SpeechState.TEXT_FALLBACK
