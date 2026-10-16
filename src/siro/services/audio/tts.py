"""Sentence buffering, Groq speech synthesis, playback acknowledgement and lip sync."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import io
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

import edge_tts
import httpx
import numpy as np
import soundfile as sf  # type: ignore[import-untyped]
from misaki import zh  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from kokoro_onnx import Kokoro

_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s*")  # noqa: RUF001
_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_MARKDOWN_LINK = re.compile(r"\[([^]]+)]\([^)]*\)")
_RAW_URL = re.compile(r"https?://\S+")
_MARKDOWN_MARKS = re.compile(r"[*_#>`~]+")


def prepare_spoken_text(text: str) -> str:
    """Turn a display response into a short, pronounceable Mandarin performance script."""
    spoken = _CODE_BLOCK.sub("程式碼內容先不念。", text)
    spoken = _MARKDOWN_LINK.sub(r"\1", spoken)
    spoken = _RAW_URL.sub("連結", spoken)
    spoken = _MARKDOWN_MARKS.sub("", spoken)
    spoken = re.sub(r"\bSIRO\b", "希洛", spoken, flags=re.IGNORECASE)
    spoken = re.sub(r"\n\s*[-+•]\s*", "；", spoken)  # noqa: RUF001
    spoken = re.sub(r"\n+", "。", spoken)
    spoken = re.sub(r"[ \t]+", " ", spoken)
    spoken = re.sub(r"。{2,}", "。", spoken)
    return spoken.strip(" 。") + ("。" if spoken.strip(" 。") else "")


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


def plan_speech(text: str) -> dict[str, object]:
    """Prepare a bounded, complete reading script; no inference or audio ownership."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, (dict, list)):
        raise ValueError("這段內容是資料格式,沒有可朗讀的對話。")
    spoken = re.sub(r"\s+", " ", prepare_spoken_text(text)).strip()
    if not spoken:
        raise ValueError("沒有可朗讀的內容。")
    if len(spoken) > 8000:
        raise OverflowError("全文超過一次朗讀的8,000字上限;文字已保留,請選較短段落。")
    first_end = min(24, len(spoken))
    if len(spoken) > first_end:
        prefix = spoken[:first_end]
        sentences = list(re.finditer(r"[.!?。！？]", prefix))  # noqa: RUF001
        pauses = list(re.finditer(r"[,，;；:：、]", prefix))  # noqa: RUF001
        pauses = [match for match in pauses if match.end() >= 8]
        if sentences:
            first_end = sentences[-1].end()
        elif pauses:
            first_end = pauses[-1].end()
        elif " " in prefix:
            first_end = prefix.rfind(" ")
    segments = [spoken[:first_end]]
    cursor = first_end
    # Reserve one character for the normalized separator at a segment boundary.
    for piece in speech_segments(spoken[first_end:], max_chars=79):
        start = spoken.index(piece, cursor)
        separator = spoken[cursor:start]
        if len(segments) > 1 and len(segments[-1]) + len(separator) + len(piece) <= 80:
            segments[-1] += separator + piece
        else:
            segments.append(separator + piece)
        cursor = start + len(piece)
    if len(segments) > 128:
        raise OverflowError("全文超過一次朗讀的128段上限;文字已保留,請選較短段落。")
    return {
        "segments": segments,
        "spoken_text": spoken,
        "version": "sentence-v2-first24-rest80",
        "max_chars": 80,
        "max_segments": 128,
        "max_total_chars": 8000,
        "deadline_seconds": 1200,
    }


class TextToSpeech(Protocol):
    def synthesize(self, text: str) -> AsyncIterator[bytes]: ...


class EdgeNeuralTTS:
    """Natural Taiwanese Mandarin speech rendered by Microsoft Edge's online service."""

    def __init__(self, voice: str = "zh-TW-HsiaoChenNeural") -> None:
        self.voice = voice

    async def render(
        self, text: str, *, rate: float = 1.0, pitch: float = 0.0, energy: float = 0.5
    ) -> bytes:
        rate_percent = round((max(0.5, min(2.0, rate)) - 1.0) * 100)
        pitch_hz = round(max(-1.0, min(1.0, pitch)) * 35)
        volume_percent = round((max(0.0, min(1.0, energy)) - 0.5) * 80)
        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=f"{rate_percent:+d}%",
            pitch=f"{pitch_hz:+d}Hz",
            volume=f"{volume_percent:+d}%",
        )
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        if not chunks:
            raise RuntimeError("TTS returned no audio")
        return b"".join(chunks)


_SIRO_VOICE_WEIGHTS = {
    "zf_xiaobei": 1.0,
}


class KokoroLocalTTS:
    """CPU-only local Mandarin synthesis with lazy model loading."""

    def __init__(
        self,
        model_path: str,
        voices_path: str,
        voice_weights: dict[str, float] | None = None,
    ) -> None:
        self._model_path = model_path
        self._voices_path = voices_path
        self._voice_weights = voice_weights or _SIRO_VOICE_WEIGHTS
        if not self._voice_weights or abs(sum(self._voice_weights.values()) - 1.0) > 1e-6:
            raise ValueError("voice weights must sum to 1")
        self._model: Kokoro | None = None
        self._g2p: object | None = None
        self._voice: np.ndarray | None = None

    async def render(
        self, text: str, *, rate: float = 1.0, pitch: float = 0.0, energy: float = 0.5
    ) -> bytes:
        del pitch
        return await asyncio.to_thread(self._render_sync, prepare_spoken_text(text), rate, energy)

    def _render_sync(self, text: str, rate: float, energy: float) -> bytes:
        if self._model is None:
            from kokoro_onnx import Kokoro

            self._model = Kokoro(self._model_path, self._voices_path)
            self._g2p = zh.ZHG2P(version="1.0")
            self._voice = sum(
                (
                    weight * self._model.get_voice_style(name)
                    for name, weight in self._voice_weights.items()
                ),
                np.zeros_like(self._model.get_voice_style(next(iter(self._voice_weights)))),
            )
        assert self._g2p is not None
        assert self._voice is not None
        phonemes, _ = self._g2p(text)  # type: ignore[operator]
        samples, sample_rate = self._model.create(
            phonemes,
            voice=self._voice,
            speed=max(0.65, min(1.35, rate)),
            is_phonemes=True,
        )
        samples *= max(0.25, min(1.0, 0.5 + energy * 0.5))
        output = io.BytesIO()
        sf.write(output, samples, sample_rate, format="WAV", subtype="PCM_16")
        return output.getvalue()


class QwenReferenceTTS:
    """Persistent isolated Qwen worker cloning a user-selected reference voice."""

    def __init__(
        self,
        python: Path,
        worker: Path,
        model: Path,
        reference_wav: Path,
        reference_text: str,
        cache_dir: Path,
        *,
        startup_timeout: float = 120,
        render_timeout: float = 900,
        lifecycle: bool = False,
        max_pending: int = 8,
    ) -> None:
        required = (python, worker, model, reference_wav)
        if any(not path.exists() for path in required):
            raise FileNotFoundError(next(path for path in required if not path.exists()))
        self._command = (
            str(python),
            str(worker),
            str(model),
            str(reference_wav),
            reference_text,
            str(cache_dir),
        )
        self._startup_timeout = startup_timeout
        self._render_timeout = render_timeout
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._lifecycle = lifecycle
        if max_pending < 1:
            raise ValueError("Qwen max_pending must be positive")
        self._max_pending = max_pending
        self._pending = 0
        self._closed = False
        self._epoch = 0
        self._poisoned = False
        self._active: asyncio.Task[object] | None = None
        self._completion_protocol = 0

    async def render(
        self, text: str, *, rate: float = 1.0, pitch: float = 0.0, energy: float = 0.5
    ) -> bytes:
        del rate, pitch, energy
        if self._lifecycle:
            return await self._render_owned(prepare_spoken_text(text))
        spoken = prepare_spoken_text(text)
        async with self._lock:
            process = await self._ensure_worker()
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write((json.dumps({"text": spoken}) + "\n").encode())
            await process.stdin.drain()
            response = await self._read_json(process, self._render_timeout)
            return self._decode_audio(response)

    def _accept_ready(self, response: dict[str, object]) -> None:
        protocol = response.get("completion_protocol")
        if response.get("ready") is not True or (
            "completion_protocol" in response and (type(protocol) is not int or protocol != 2)
        ):
            raise RuntimeError("Qwen TTS worker failed to initialize")
        self._completion_protocol = 2 if protocol == 2 else 0

    def _decode_audio(self, response: dict[str, object]) -> bytes:
        if "error" in response:
            raise RuntimeError("Qwen render failed")
        if self._completion_protocol == 2:
            completion = response.get("completion")
            if not isinstance(completion, dict):
                raise RuntimeError("Qwen audio completion is unverified")
            count, limit = completion.get("generated_tokens"), completion.get("max_new_tokens")
            if (
                completion.get("status") != "complete"
                or completion.get("eos_observed") is not True
                or completion.get("cap_reached") is not False
                or type(count) is not int
                or type(limit) is not int
                or not 0 < count < limit
                or type(completion.get("observer_calls")) is not int
                or completion.get("observer_calls") != 1
            ):
                raise RuntimeError("Qwen audio completion is unverified")
        audio = response.get("audio")
        if not isinstance(audio, str) or not audio:
            raise RuntimeError("Qwen render failed")
        decoded = base64.b64decode(audio, validate=True)
        if not decoded:
            raise RuntimeError("Qwen render failed")
        return decoded

    async def _ensure_worker(self) -> asyncio.subprocess.Process:
        if self._process is not None and self._process.returncode is None:
            return self._process
        process = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=16 * 1024 * 1024,
        )
        assert process.stdout is not None
        if self._lifecycle:
            self._process = process  # own even a failed startup
        response = await self._read_json(process, self._startup_timeout)
        try:
            self._accept_ready(response)
        except RuntimeError:
            process.kill()
            await process.wait()
            raise
        self._process = process
        return process

    async def _read_json(
        self, process: asyncio.subprocess.Process, timeout: float
    ) -> dict[str, object]:
        assert process.stdout is not None
        stdout = process.stdout

        async def read() -> dict[str, object]:
            while True:
                line = await stdout.readline()
                if not line:
                    if not self._lifecycle:
                        self._process = None
                    raise RuntimeError("Qwen TTS worker stopped without a response")
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    return value

        return await asyncio.wait_for(read(), timeout)

    @property
    def lifecycle_enabled(self) -> bool:
        return self._lifecycle

    async def _retire(self) -> None:
        process = self._process
        if process is None:
            self._poisoned = False
            self._completion_protocol = 0
            return
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
        try:
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError as error:
            raise RuntimeError("Qwen worker cleanup failed") from error
        self._process = None
        self._poisoned = False
        self._completion_protocol = 0

    async def _cleanup(self) -> None:
        cleanup = asyncio.create_task(self._retire())
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                continue  # keep ownership during repeated cancellation
        await cleanup

    async def _render_owned(self, spoken: str) -> bytes:
        if self._closed:
            raise RuntimeError("Qwen worker is closed")
        if self._pending >= self._max_pending:
            raise RuntimeError("Qwen render queue is full")
        self._pending += 1
        try:
            async with self._lock:
                if self._closed:
                    raise RuntimeError("Qwen worker is closed")
                self._active = asyncio.current_task()
                try:
                    # A cancelled spawn must still transfer ownership before cleanup.
                    if (
                        self._poisoned
                        or self._process is None
                        or self._process.returncode is not None
                    ):
                        await self._cleanup()
                        self._epoch += 1
                        spawn = asyncio.create_task(
                            asyncio.create_subprocess_exec(
                                *self._command,
                                stdin=asyncio.subprocess.PIPE,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.DEVNULL,
                                limit=16 * 1024 * 1024,
                            )
                        )
                        try:
                            self._process = await asyncio.shield(spawn)
                        except asyncio.CancelledError:
                            while not spawn.done():
                                try:
                                    await asyncio.shield(spawn)
                                except asyncio.CancelledError:
                                    continue
                            self._process = spawn.result()
                            raise
                        response = await self._read_json(self._process, self._startup_timeout)
                        self._accept_ready(response)
                    process = self._process
                    assert process is not None and process.stdin is not None
                    request_id = str(uuid4())
                    stdin = process.stdin

                    async def exchange() -> bytes:
                        stdin.write(
                            (
                                json.dumps(
                                    {"text": spoken, "request_id": request_id, "epoch": self._epoch}
                                )
                                + "\n"
                            ).encode()
                        )
                        await stdin.drain()
                        response = await self._read_json(process, self._render_timeout)
                        if (
                            response.get("request_id") != request_id
                            or response.get("epoch") != self._epoch
                        ):
                            raise RuntimeError("Qwen response identity mismatch")
                        return self._decode_audio(response)

                    return await asyncio.wait_for(exchange(), self._render_timeout)
                except BaseException:
                    self._poisoned = True
                    await self._cleanup()
                    raise
                finally:
                    self._active = None
        finally:
            self._pending -= 1

    async def close(self) -> None:
        self._closed = True
        active = self._active
        if active is not None and active is not asyncio.current_task():
            active.cancel()
        async with self._lock:
            await self._cleanup()


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
