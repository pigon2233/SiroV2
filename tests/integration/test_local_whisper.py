from __future__ import annotations

import asyncio
import io
import json
import wave
from pathlib import Path
from typing import Any

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from siro.services.audio.local_stt import LocalWhisper
from siro.services.audio.stt import Transcript
from siro.services.presentation.gateway import GatewayState, create_app


def wav(*, seconds: int = 1, channels: int = 1, width: int = 2) -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setparams((channels, width, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0" * seconds * 16000 * channels * width)
    return stream.getvalue()


@pytest.fixture
def model(tmp_path: Path) -> Path:
    directory = tmp_path / "local-whisper"
    directory.mkdir()
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt"):
        (directory / name).write_text("synthetic model marker")
    return directory


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"not wav", b"", wav(seconds=31), wav(channels=2)])
async def test_invalid_capture_never_starts_a_worker(
    model: Path, monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    async def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("invalid capture must not start inference")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(ValueError, match="WAV"):
        await LocalWhisper(model).transcribe(body)


def test_missing_local_model_is_not_downloaded(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="local model"):
        LocalWhisper(tmp_path / "missing")


@pytest.mark.asyncio
async def test_worker_is_offline_and_receives_audio_only_in_stdin(
    model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: dict[str, Any] = {}

    class Worker:
        returncode = 0

        async def communicate(self, audio: bytes) -> tuple[bytes, bytes]:
            received["audio"] = audio
            return json.dumps({"text": "合成辨識", "language": "zh"}).encode(), b""

    async def spawn(*args: Any, **kwargs: Any) -> Worker:
        received.update(argv=args, options=kwargs)
        return Worker()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    audio = wav()
    transcript = await LocalWhisper(model).transcribe(audio, language="zh")
    assert transcript.text == "合成辨識" and transcript.final
    assert received["audio"] == audio
    assert received["argv"][1:4] == ("-I", "-m", "siro.services.audio.whisper_worker")
    assert str(model) in received["argv"]
    assert all("合成" not in str(argument) for argument in received["argv"])
    assert received["options"]["env"]["HF_HUB_OFFLINE"] == "1"
    assert received["options"]["env"]["TRANSFORMERS_OFFLINE"] == "1"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_cancel_or_timeout_joins_real_owned_worker(
    model: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    original = asyncio.create_subprocess_exec
    started = asyncio.Event()
    owned: list[asyncio.subprocess.Process] = []

    async def sleeping_worker(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        process = await original(
            args[0], "-c", "import sys,time; sys.stdin.buffer.read(); time.sleep(60)", **kwargs
        )
        owned.append(process)
        started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", sleeping_worker)
    adapter = LocalWhisper(model, timeout_seconds=0.1 if mode == "timeout" else 10)
    task = asyncio.create_task(adapter.transcribe(wav()))
    await asyncio.wait_for(started.wait(), 2)
    if mode == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
    else:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(task, 3)
    assert owned[0].returncode is not None
    assert not adapter.busy


@pytest.mark.asyncio
async def test_concurrent_capture_is_rejected_without_another_worker(
    model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    class Worker:
        returncode = 0

        async def communicate(self, audio: bytes) -> tuple[bytes, bytes]:
            await release.wait()
            return b'{"text":"","language":"zh"}', b""

    async def spawn(*args: Any, **kwargs: Any) -> Worker:
        nonlocal calls
        calls += 1
        started.set()
        return Worker()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    adapter = LocalWhisper(model)
    first = asyncio.create_task(adapter.transcribe(wav()))
    await started.wait()
    try:
        with pytest.raises(RuntimeError, match="busy"):
            await adapter.transcribe(wav())
    finally:
        release.set()
        await first
    assert calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [b"raw output", b'{"text":45}', b'{"error":"private"}'])
async def test_bad_worker_response_has_no_provider_payload(
    model: Path, monkeypatch: pytest.MonkeyPatch, result: bytes
) -> None:
    class Worker:
        returncode = 0

        async def communicate(self, audio: bytes) -> tuple[bytes, bytes]:
            return result, b"private diagnostic"

    async def spawn(*args: Any, **kwargs: Any) -> Worker:
        return Worker()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(ValueError, match="invalid local speech response") as failure:
        await LocalWhisper(model).transcribe(wav())
    assert "private" not in str(failure.value)


@pytest.mark.parametrize("reason", ["disconnect", "microphone_off"])
def test_transcription_stops_on_disconnect_or_microphone_revoke(
    monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    state = GatewayState()
    state.kill_switches["microphone"] = True
    observation = {"started": False, "cancelled": False}

    class Recognizer:
        async def transcribe(self, audio: bytes, *, language: str | None = None) -> Transcript:
            observation["started"] = True
            try:
                await asyncio.sleep(0.2)
                return Transcript("synthetic must not be submitted", "zh", True)
            except asyncio.CancelledError:
                observation["cancelled"] = True
                raise

    async def disconnected(request: Request) -> bool:
        if reason == "microphone_off" and observation["started"]:
            state.kill_switches["microphone"] = False
        return reason == "disconnect" and observation["started"]

    monkeypatch.setattr(Request, "is_disconnected", disconnected)
    origin = "http://127.0.0.1:8000"
    with TestClient(
        create_app(allowed_origins={origin}, state=state, speech_to_text=Recognizer())
    ) as client:
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        response = client.post(
            "/v1/audio/transcriptions",
            headers={"origin": origin, "authorization": "Bearer " + token},
            content=b"synthetic WAV handled by fake recognizer",
        )
    assert response.status_code == (499 if reason == "disconnect" else 403)
    assert observation["cancelled"]
    assert "synthetic must not" not in response.text
