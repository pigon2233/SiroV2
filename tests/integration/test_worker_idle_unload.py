"""Idle workers are retired to free model memory and respawn on next use."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from siro.services.audio.idle import DEFAULT_IDLE_SECONDS, idle_seconds
from siro.services.audio.local_stt import LocalWhisper
from siro.services.audio.tts import QwenReferenceTTS
from tests.integration.test_local_whisper import FakeWorker, wav
from tests.integration.test_qwen_lifecycle import WORKER


def test_idle_seconds_default_env_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIRO_WORKER_IDLE_SECONDS", raising=False)
    assert idle_seconds() == DEFAULT_IDLE_SECONDS == 600
    monkeypatch.setenv("SIRO_WORKER_IDLE_SECONDS", "0")
    assert idle_seconds() == 0
    monkeypatch.setenv("SIRO_WORKER_IDLE_SECONDS", "30")
    assert idle_seconds() == 30
    assert idle_seconds(5) == 5
    for bad in ("soon", "-1", "90000"):
        monkeypatch.setenv("SIRO_WORKER_IDLE_SECONDS", bad)
        with pytest.raises(ValueError):
            idle_seconds()


@pytest.mark.asyncio
async def test_whisper_is_retired_when_idle_and_reloaded_on_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "m"
    model.mkdir()
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt"):
        (model / name).write_text("x")
    reply = json.dumps({"text": "好", "language": "zh"}).encode()
    workers: list[FakeWorker] = []

    async def spawn(*args: Any, **kwargs: Any) -> FakeWorker:
        workers.append(FakeWorker([reply]))
        return workers[-1]

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    adapter = LocalWhisper(model, idle_seconds=0.1)
    await adapter.transcribe(wav(), language="zh")
    assert workers[0].returncode is None
    await asyncio.sleep(0.4)
    assert workers[0].returncode is not None
    await adapter.transcribe(wav(), language="zh")
    assert len(workers) == 2
    await adapter.close()


@pytest.mark.asyncio
async def test_whisper_zero_never_retires(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model = tmp_path / "m"
    model.mkdir()
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt"):
        (model / name).write_text("x")
    worker = FakeWorker([json.dumps({"text": "好", "language": "zh"}).encode()])

    async def spawn(*args: Any, **kwargs: Any) -> FakeWorker:
        return worker

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    adapter = LocalWhisper(model, idle_seconds=0)
    await adapter.transcribe(wav(), language="zh")
    await asyncio.sleep(0.3)
    assert worker.returncode is None
    await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("lifecycle", [True, False])
async def test_qwen_is_retired_when_idle_and_respawns(tmp_path: Path, lifecycle: bool) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text(WORKER)
    model = tmp_path / "normal"
    model.mkdir()
    reference = tmp_path / "ref.wav"
    reference.touch()
    tts = QwenReferenceTTS(
        Path(sys.executable),
        worker,
        model,
        reference,
        "synthetic",
        tmp_path / "cache",
        startup_timeout=5,
        render_timeout=5,
        lifecycle=lifecycle,
        idle_seconds=0.2,
    )
    try:
        await tts.render("你好")
        first = tts._process
        assert first is not None and first.returncode is None
        await asyncio.sleep(0.8)
        assert first.returncode is not None and tts._process is None
        assert await tts.render("再見")
        assert tts._process is not None and tts._process is not first
    finally:
        await tts.close()
