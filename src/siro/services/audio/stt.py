"""Speech recognition ports and the Groq Whisper adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: str | None
    final: bool


class SpeechToText(Protocol):
    async def transcribe(self, wav: bytes, *, language: str | None = None) -> Transcript: ...


class GroqWhisper:
    # The gateway refuses cloud recognizers while the cloud switch is off.
    is_cloud = True

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "whisper-large-v3-turbo",
        base_url: str = "https://api.groq.com/openai/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._url = f"{base_url.rstrip('/')}/audio/transcriptions"
        self._timeout = timeout_seconds

    async def transcribe(self, wav: bytes, *, language: str | None = None) -> Transcript:
        data = {"model": self._model, "response_format": "verbose_json"}
        if language:
            data["language"] = language
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                data=data,
                files={"file": ("utterance.wav", wav, "audio/wav")},
            )
        response.raise_for_status()
        payload = response.json()
        return Transcript(
            text=str(payload.get("text", "")).strip(),
            language=str(payload["language"]) if payload.get("language") else language,
            final=True,
        )


class MockSpeechToText:
    def __init__(self, text: str = "hello", language: str = "en") -> None:
        self.text = text
        self.language = language
        self.calls = 0

    async def transcribe(self, wav: bytes, *, language: str | None = None) -> Transcript:
        del wav
        self.calls += 1
        return Transcript(self.text, language or self.language, True)
