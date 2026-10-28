"""Bounded, offline CPU speech recognition in a cancellable owned worker."""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import wave
from collections.abc import Coroutine
from contextlib import suppress
from pathlib import Path
from typing import Any, TypeVar

from siro.services.audio.idle import IdleRetirer, idle_seconds
from siro.services.audio.stt import Transcript

_T = TypeVar("_T")
_idle_seconds = idle_seconds


class LocalWhisper:
    """Owns one persistent recognizer process; the model loads once, not per utterance."""

    def __init__(
        self,
        model_directory: Path,
        *,
        timeout_seconds: float = 45,
        startup_timeout_seconds: float = 60,
        idle_seconds: float | None = None,
    ) -> None:
        directory = model_directory.resolve()
        required = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")
        if not directory.is_dir() or not all((directory / name).is_file() for name in required):
            raise ValueError("complete local model directory is required")
        if not 0 < timeout_seconds <= 120:
            raise ValueError("local speech timeout must be between 0 and 120 seconds")
        self._directory = directory
        self._timeout = timeout_seconds
        self._startup_timeout = startup_timeout_seconds
        self._lock = asyncio.Lock()
        self._process: asyncio.subprocess.Process | None = None
        self._idle = IdleRetirer(_idle_seconds(idle_seconds), self._retire_if_idle)

    async def _retire_if_idle(self) -> None:
        if self._lock.locked():
            return
        async with self._lock:
            await self._retire()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    async def warm(self) -> None:
        """Load the model ahead of the first utterance; failures surface on use."""
        if self._lock.locked():
            return
        async with self._lock:
            with suppress(Exception):
                await self._owned(self._ensure_worker(), self._startup_timeout)
                self._idle.touch()

    async def close(self) -> None:
        self._idle.cancel()
        async with self._lock:
            await self._retire()

    async def transcribe(self, wav: bytes, *, language: str | None = None) -> Transcript:
        self._validate_audio(wav)
        if language is not None and (
            not language.isascii() or not language.isalpha() or len(language) > 8
        ):
            raise ValueError("invalid speech language")
        if self._lock.locked():
            raise RuntimeError("local speech worker is busy")
        async with self._lock:
            process = await self._owned(self._ensure_worker(), self._startup_timeout)
            result = await self._owned(self._exchange(process, wav, language), self._timeout)
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("text"), str)
                or len(result["text"]) > 20_000
                or not isinstance(result.get("language"), str)
            ):
                raise ValueError("invalid local speech response")
            self._idle.touch()
            return Transcript(result["text"].strip(), result["language"], True)

    async def _owned(self, work: Coroutine[Any, Any, _T], timeout: float) -> _T:
        """Run one worker exchange; cancellation or timeout retires the worker it used."""
        task = asyncio.ensure_future(work)
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await asyncio.shield(self._retire())
            raise

    async def _ensure_worker(self) -> asyncio.subprocess.Process:
        if self._process is not None and self._process.returncode is None:
            return self._process
        environment = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        self._process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-m",
            "siro.services.audio.whisper_worker",
            str(self._directory),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=environment,
        )
        if await self._read_line(self._process) != {"ready": True}:
            raise ValueError("invalid local speech response")
        return self._process

    async def _exchange(
        self, process: asyncio.subprocess.Process, wav: bytes, language: str | None
    ) -> object:
        assert process.stdin is not None
        process.stdin.write(json.dumps({"bytes": len(wav), "language": language}).encode() + b"\n")
        process.stdin.write(wav)
        await process.stdin.drain()
        return await self._read_line(process)

    @staticmethod
    async def _read_line(process: asyncio.subprocess.Process) -> object:
        assert process.stdout is not None
        line = await process.stdout.readline()
        if not line or len(line) > 128 * 1024:
            raise ValueError("invalid local speech response")
        try:
            return json.loads(line)
        except (ValueError, UnicodeError):
            raise ValueError("invalid local speech response") from None

    async def _retire(self) -> None:
        process, self._process = self._process, None
        if process is None or process.returncode is not None:
            return
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 1)
        except TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()

    @staticmethod
    def _validate_audio(audio: bytes) -> None:
        valid = False
        if 0 < len(audio) <= 3 * 1024 * 1024:
            try:
                with wave.open(io.BytesIO(audio), "rb") as wav:
                    valid = (
                        wav.getnchannels() == 1
                        and wav.getsampwidth() == 2
                        and 8000 <= wav.getframerate() <= 48000
                        and 0 < wav.getnframes() <= wav.getframerate() * 30
                        and len(wav.readframes(wav.getnframes())) == wav.getnframes() * 2
                    )
            except (ValueError, EOFError, wave.Error):
                pass
        if not valid:
            raise ValueError("speech input requires a mono PCM16 WAV of at most 30 seconds")
