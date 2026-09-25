"""Energy VAD and deterministic utterance endpointing."""

from __future__ import annotations

import io
import math
import struct
import wave
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from siro.services.audio.stt import SpeechToText, Transcript


class InputResult(StrEnum):
    LISTENING = "listening"
    SPEECH_STARTED = "speech_started"
    FINAL = "final"
    SILENCE_TIMEOUT = "silence_timeout"
    MAX_DURATION = "max_duration"
    DEVICE_DISCONNECTED = "device_disconnected"


@dataclass(frozen=True, slots=True)
class InputEvent:
    result: InputResult
    transcript: Transcript | None = None


class EnergyVad:
    def __init__(self, *, threshold: float = 500.0) -> None:
        self.threshold = threshold

    def is_speech(self, pcm_s16le: bytes) -> bool:
        if not pcm_s16le or len(pcm_s16le) % 2:
            return False
        count = len(pcm_s16le) // 2
        samples = struct.unpack(f"<{count}h", pcm_s16le)
        rms = math.sqrt(sum(sample * sample for sample in samples) / count)
        return rms >= self.threshold


def pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()


class InputEndpoint:
    """Accumulates one utterance and emits at most one user turn."""

    def __init__(
        self,
        stt: SpeechToText,
        on_user_turn: Callable[[Transcript], Awaitable[None]],
        on_partial: Callable[[Transcript], Awaitable[None]] | None = None,
        *,
        sample_rate: int = 16_000,
        silence_ms: int = 600,
        initial_silence_ms: int = 3_000,
        max_duration_ms: int = 30_000,
        partial_every_ms: int = 1_000,
        vad: EnergyVad | None = None,
    ) -> None:
        self._stt = stt
        self._on_user_turn = on_user_turn
        self._on_partial = on_partial
        self._sample_rate = sample_rate
        self._silence_frames = silence_ms // 20
        self._initial_frames = initial_silence_ms // 20
        self._max_frames = max_duration_ms // 20
        self._partial_frames = max(1, partial_every_ms // 20)
        self._vad = vad or EnergyVad()
        self._frames: list[bytes] = []
        self._silence = 0
        self._started = False
        self._finished = False

    async def push(self, pcm: bytes, *, language: str | None = None) -> InputEvent:
        if self._finished:
            raise RuntimeError("utterance already finished")
        self._frames.append(pcm)
        speech = self._vad.is_speech(pcm)
        if speech:
            self._started = True
            self._silence = 0
            if len(self._frames) == 1:
                return InputEvent(InputResult.SPEECH_STARTED)
        else:
            self._silence += 1
        if not self._started and len(self._frames) >= self._initial_frames:
            self._finished = True
            return InputEvent(InputResult.SILENCE_TIMEOUT)
        if len(self._frames) >= self._max_frames:
            return await self._finish(InputResult.MAX_DURATION, language)
        if self._started and self._silence >= self._silence_frames:
            return await self._finish(InputResult.FINAL, language)
        if (
            self._started
            and self._on_partial is not None
            and len(self._frames) % self._partial_frames == 0
        ):
            partial = await self._stt.transcribe(
                pcm_to_wav(b"".join(self._frames), self._sample_rate), language=language
            )
            await self._on_partial(Transcript(partial.text, partial.language, False))
        return InputEvent(InputResult.SPEECH_STARTED if self._started else InputResult.LISTENING)

    def disconnect(self) -> InputEvent:
        self._finished = True
        return InputEvent(InputResult.DEVICE_DISCONNECTED)

    async def _finish(self, result: InputResult, language: str | None) -> InputEvent:
        self._finished = True
        transcript = await self._stt.transcribe(
            pcm_to_wav(b"".join(self._frames), self._sample_rate), language=language
        )
        if transcript.text:
            await self._on_user_turn(transcript)
        return InputEvent(result, transcript)
