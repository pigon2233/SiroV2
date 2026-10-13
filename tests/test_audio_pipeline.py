from __future__ import annotations

import struct
from collections.abc import AsyncIterator

import pytest

from siro.services.audio.input import EnergyVad, InputEndpoint, InputResult
from siro.services.audio.stt import MockSpeechToText, Transcript
from siro.services.audio.tts import (
    SpeechPlayback,
    SpeechState,
    prepare_spoken_text,
    speech_segments,
    synthesize_or_fallback,
)


def test_display_text_becomes_a_pronounceable_performance_script() -> None:
    assert (
        prepare_spoken_text(
            "**SIRO**：請看[說明](https://example.com)。\n- 第一件事\n- 第二件事"  # noqa: RUF001
        )
        == "希洛：請看說明。；第一件事；第二件事。"  # noqa: RUF001
    )


def frame(amplitude: int, samples: int = 320) -> bytes:
    return struct.pack(f"<{samples}h", *([amplitude] * samples))


def assert_state(playback: SpeechPlayback, expected: SpeechState) -> None:
    assert playback.state == expected


@pytest.mark.asyncio
async def test_vad_partial_final_and_one_user_turn() -> None:
    turns: list[Transcript] = []
    partials: list[Transcript] = []

    async def turn(transcript: Transcript) -> None:
        turns.append(transcript)

    async def partial(transcript: Transcript) -> None:
        partials.append(transcript)

    stt = MockSpeechToText("hello siro")
    endpoint = InputEndpoint(
        stt,
        turn,
        partial,
        silence_ms=40,
        partial_every_ms=40,
        max_duration_ms=400,
    )
    assert (await endpoint.push(frame(2_000))).result == InputResult.SPEECH_STARTED
    await endpoint.push(frame(2_000))
    await endpoint.push(frame(0))
    result = await endpoint.push(frame(0))
    assert result.result == InputResult.FINAL
    assert result.transcript == Transcript("hello siro", "en", True)
    assert partials == [Transcript("hello siro", "en", False)]
    assert turns == [Transcript("hello siro", "en", True)]
    assert stt.calls == 2
    with pytest.raises(RuntimeError, match="finished"):
        await endpoint.push(frame(2_000))


@pytest.mark.asyncio
async def test_input_has_deterministic_silence_long_noise_and_disconnect_results() -> None:
    async def turn(transcript: Transcript) -> None:
        del transcript

    silent = InputEndpoint(MockSpeechToText(), turn, initial_silence_ms=40)
    await silent.push(frame(0))
    assert (await silent.push(frame(0))).result == InputResult.SILENCE_TIMEOUT

    long = InputEndpoint(MockSpeechToText(), turn, max_duration_ms=40, silence_ms=100)
    await long.push(frame(1_500))
    assert (await long.push(frame(1_500))).result == InputResult.MAX_DURATION

    noise = InputEndpoint(
        MockSpeechToText(), turn, initial_silence_ms=40, vad=EnergyVad(threshold=1_000)
    )
    await noise.push(frame(200))
    assert (await noise.push(frame(200))).result == InputResult.SILENCE_TIMEOUT

    disconnected = InputEndpoint(MockSpeechToText(), turn)
    assert disconnected.disconnect().result == InputResult.DEVICE_DISCONNECTED


class ChunkTts:
    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        yield text.encode()


@pytest.mark.asyncio
async def test_tts_segments_omit_tool_json_and_finish_only_after_playback_ack() -> None:
    assert speech_segments('{"tool": "filesystem.read"}') == []
    playback = SpeechPlayback("speech-1", "Hello. How are you?")
    chunks = [chunk async for chunk in synthesize_or_fallback(ChunkTts(), playback)]
    assert chunks == [b"Hello.", b"How are you?"]
    assert_state(playback, SpeechState.QUEUED)
    assert playback.mouth_open == 0.0
    playback.acknowledge(480)
    assert_state(playback, SpeechState.PLAYING)
    assert playback.mouth_open > 0
    playback.acknowledge(960, final=True)
    assert_state(playback, SpeechState.FINISHED)
    assert playback.mouth_open == 0


@pytest.mark.asyncio
async def test_cancel_prevents_old_speech_from_reappearing() -> None:
    playback = SpeechPlayback("speech-old", "Old response.")
    playback.cancel()
    assert [chunk async for chunk in synthesize_or_fallback(ChunkTts(), playback)] == []
    playback.acknowledge(999, final=True)
    assert playback.state == SpeechState.CANCELED
