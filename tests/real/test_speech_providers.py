from __future__ import annotations

import os

import httpx
import pytest

from siro.services.audio.stt import GroqWhisper
from siro.services.audio.tts import GroqOrpheus

pytestmark = pytest.mark.real_provider


@pytest.mark.asyncio
async def test_groq_whisper_transcribes_openai_public_fixture() -> None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        pytest.skip("set GROQ_API_KEY for the opt-in Groq speech test")
    fixture = httpx.get(
        "https://raw.githubusercontent.com/openai/whisper/main/tests/jfk.flac", timeout=30.0
    )
    fixture.raise_for_status()
    transcript = await GroqWhisper(api_key).transcribe(fixture.content, language="en")
    normalized = transcript.text.lower()
    assert "fellow americans" in normalized and "your country" in normalized


@pytest.mark.asyncio
async def test_groq_tts_audio_can_be_transcribed_by_groq_stt() -> None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        pytest.skip("set GROQ_API_KEY for the opt-in Groq speech test")
    if os.environ.get("SIRO_TEST_GROQ_TTS_TERMS_ACCEPTED") != "1":
        pytest.skip("accept the Orpheus model terms, then opt in explicitly")
    tts = GroqOrpheus(api_key)
    audio = b"".join(
        [chunk async for chunk in tts.synthesize("Hello Siro, this is a speech test.")]
    )
    assert audio[:4] == b"RIFF"
    transcript = await GroqWhisper(api_key).transcribe(audio, language="en")
    normalized = transcript.text.lower()
    assert "hello" in normalized and "speech" in normalized
