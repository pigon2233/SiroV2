from __future__ import annotations

import asyncio

import pytest

from siro.services.audio.session import AudioSession
from siro.services.audio.tts import SpeechPlayback, SpeechState


@pytest.mark.asyncio
async def test_barge_in_cancels_player_tts_and_llm() -> None:
    canceled: list[str] = []

    async def cancel(name: str) -> None:
        canceled.append(name)

    session = AudioSession()
    playback = SpeechPlayback("speech-1", "Speaking")
    generation = await session.begin(
        playback,
        lambda: cancel("player"),
        lambda: cancel("tts"),
        lambda: cancel("llm"),
    )
    await session.barge_in()
    assert playback.state == SpeechState.CANCELED
    assert canceled == ["player", "tts", "llm"]
    assert not await session.accept_audio(generation, b"late audio")


@pytest.mark.asyncio
async def test_one_hundred_cancel_completion_races_never_revive_old_audio() -> None:
    session = AudioSession()
    for index in range(100):
        playback = SpeechPlayback(f"speech-{index}", "response")
        generation = await session.begin(playback)
        results = await asyncio.gather(
            session.barge_in(), session.accept_audio(generation, b"completed concurrently")
        )
        assert results[1] is False or playback.state != SpeechState.CANCELED
        assert playback.state == SpeechState.CANCELED
        assert not await session.accept_audio(generation, b"late")


@pytest.mark.asyncio
async def test_reconnect_does_not_replay_pre_disconnect_speech() -> None:
    session = AudioSession()
    generation = await session.begin(SpeechPlayback("old", "old speech"))
    await session.reconnect()
    assert not await session.accept_audio(generation, b"old buffered frame")
