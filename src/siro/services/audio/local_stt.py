"""Bounded, offline CPU speech recognition in a cancellable owned worker."""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import wave
from contextlib import suppress
from pathlib import Path

from siro.services.audio.stt import Transcript


class LocalWhisper:
    def __init__(self, model_directory: Path, *, timeout_seconds: float = 45) -> None:
        directory = model_directory.resolve()
        required = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")
        if not directory.is_dir() or not all((directory / name).is_file() for name in required):
            raise ValueError("complete local model directory is required")
        if not 0 < timeout_seconds <= 120:
            raise ValueError("local speech timeout must be between 0 and 120 seconds")
        self._directory = directory
        self._timeout = timeout_seconds
        self._lock = asyncio.Lock()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    async def transcribe(self, wav: bytes, *, language: str | None = None) -> Transcript:
        self._validate_audio(wav)
        if language is not None and (
            not language.isascii() or not language.isalpha() or len(language) > 8
        ):
            raise ValueError("invalid speech language")
        if self._lock.locked():
            raise RuntimeError("local speech worker is busy")
        async with self._lock:
            environment = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
            environment.pop("PYTHONPATH", None)
            environment.pop("PYTHONHOME", None)
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                "-m",
                "siro.services.audio.whisper_worker",
                str(self._directory),
                language or "auto",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=environment,
            )
            communication = asyncio.create_task(process.communicate(wav))
            try:
                stdout, _ = await asyncio.wait_for(
                    asyncio.shield(communication), timeout=self._timeout
                )
            except BaseException:
                try:
                    if process.returncode is None:
                        with suppress(ProcessLookupError):
                            process.terminate()
                        try:
                            await asyncio.wait_for(process.wait(), 1)
                        except TimeoutError:
                            process.kill()
                            await process.wait()
                finally:
                    await asyncio.gather(communication, return_exceptions=True)
                raise
            if process.returncode != 0 or len(stdout) > 128 * 1024:
                raise ValueError("invalid local speech response")
            try:
                result = json.loads(stdout)
            except (ValueError, UnicodeError):
                result = None
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("text"), str)
                or len(result["text"]) > 20_000
                or not isinstance(result.get("language"), str)
            ):
                raise ValueError("invalid local speech response")
            return Transcript(result["text"].strip(), result["language"], True)

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
