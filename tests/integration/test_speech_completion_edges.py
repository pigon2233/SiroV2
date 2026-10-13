from __future__ import annotations

import base64
import hashlib
import io
import json
import runpy
import sys
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from siro.services.audio.tts import QwenReferenceTTS, plan_speech
from siro.services.presentation.gateway import SessionTokens, create_app

ORIGIN = "http://127.0.0.1:8000"
COMPLETE = {
    "status": "complete",
    "eos_observed": True,
    "cap_reached": False,
    "generated_tokens": 3,
    "max_new_tokens": 512,
    "observer_calls": 1,
}


def fake_worker_adapter(
    tmp_path: Path, ready: dict[str, object], response: dict[str, object], *, lifecycle: bool
) -> QwenReferenceTTS:
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import json,sys\n"
        f"print({json.dumps(ready)!r},flush=True)\n"
        "for line in sys.stdin:\n"
        " r=json.loads(line)\n"
        " ident={k:r[k] for k in ('request_id','epoch') if k in r}\n"
        f" result=json.loads({json.dumps(response)!r})\n"
        " print(json.dumps({**ident,**result}),flush=True)\n"
    )
    return QwenReferenceTTS(
        Path(sys.executable),
        worker,
        tmp_path,
        worker,
        "synthetic",
        tmp_path / "cache",
        lifecycle=lifecycle,
    )


@pytest.mark.parametrize(
    "text",
    [
        "alpha beta gamma delta " * 12,
        "First sentence. Second sentence! " * 12,
        "repeated " * 60,
        "甲\u2003乙\t丙\u00a0丁 " * 40,
    ],
)
def test_plan_preserves_canonical_text_across_segment_separators(text: str) -> None:
    plan = plan_speech(text)
    segments = plan["segments"]
    assert isinstance(segments, list)
    assert len(segments) > 1
    assert "".join(segments) == plan["spoken_text"]
    assert all(0 < len(segment) <= 80 and segment.strip() for segment in segments)


@pytest.mark.asyncio
@pytest.mark.parametrize("lifecycle", [False, True])
async def test_explicit_null_completion_protocol_cannot_be_legacy_downgrade(
    tmp_path: Path, lifecycle: bool
) -> None:
    tts = fake_worker_adapter(
        tmp_path,
        {"ready": True, "completion_protocol": None},
        {"audio": base64.b64encode(b"unverified").decode()},
        lifecycle=lifecycle,
    )
    try:
        with pytest.raises(RuntimeError, match="failed to initialize"):
            await tts.render("synthetic")
    finally:
        await tts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("lifecycle", [False, True])
@pytest.mark.parametrize("malformed", ["empty_audio", "error_with_audio"])
async def test_protocol_completion_cannot_make_empty_or_failed_audio_successful(
    tmp_path: Path, lifecycle: bool, malformed: str
) -> None:
    response: dict[str, object] = {
        "completion": COMPLETE,
        "audio": base64.b64encode(b"synthetic audio").decode(),
    }
    if malformed == "empty_audio":
        response["audio"] = ""
    else:
        response["error"] = "QwenOutputIncomplete"
    tts = fake_worker_adapter(
        tmp_path, {"ready": True, "completion_protocol": 2}, response, lifecycle=lifecycle
    )
    try:
        with pytest.raises(RuntimeError):
            await tts.render("synthetic")
        if lifecycle:
            assert tts._process is None
    finally:
        await tts.close()


@pytest.mark.asyncio
async def test_deep_data_format_returns_validation_failure_without_audio_work() -> None:
    class Speech:
        calls = 0

        async def render(self, text: str, *, rate: float, pitch: float, energy: float) -> bytes:
            self.calls += 1
            raise AssertionError("invalid plans cannot generate audio")

    speech = Speech()
    tokens = SessionTokens()
    token, _ = tokens.issue()
    transport = httpx.ASGITransport(
        app=create_app(tokens=tokens, text_to_speech=speech), raise_app_exceptions=False
    )
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        result = await client.post(
            "/v1/audio/speech/plan",
            headers={"origin": ORIGIN, "authorization": f"Bearer {token}"},
            json={"text": "[" * 1500 + "0" + "]" * 1500},
        )
    assert result.status_code == 422
    assert speech.calls == 0


def test_worker_eos_proof_cannot_commit_zero_sample_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    worker_path = Path(__file__).parents[2] / "scripts/qwen_tts_worker.py"
    worker = runpy.run_path(str(worker_path))
    model_path = tmp_path / "model"
    model_path.mkdir()
    (model_path / "config.json").write_text('{"synthetic":true}')
    reference = tmp_path / "synthetic-reference.wav"
    reference.write_bytes(b"synthetic fixture, not private audio")
    cache = tmp_path / "cache"
    model = SimpleNamespace(
        create_voice_clone_prompt=lambda **kwargs: {"synthetic": True},
        _merge_generate_kwargs=lambda **kwargs: kwargs,
    )

    def write(output: io.BytesIO, samples: bytes, sample_rate: int, **kwargs: Any) -> None:
        assert samples == b""
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(samples)

    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace(write=write))
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False), bfloat16="synthetic"),
    )
    monkeypatch.setitem(
        sys.modules,
        "qwen_tts",
        SimpleNamespace(
            Qwen3TTSModel=SimpleNamespace(from_pretrained=lambda *args, **kwargs: model)
        ),
    )
    monkeypatch.setattr(
        sys, "argv", [str(worker_path), str(model_path), str(reference), "synthetic", str(cache)]
    )
    monkeypatch.setattr(
        sys, "stdin", io.StringIO('{"text":"synthetic","request_id":"empty","epoch":3}\n')
    )
    monkeypatch.setitem(worker["main"].__globals__, "version", lambda name: "synthetic")
    monkeypatch.setitem(
        worker["main"].__globals__, "observe_voice_clone", lambda *args: ([b""], 24000, COMPLETE)
    )
    assert worker["main"]() == 0
    ready, result = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert ready["completion_protocol"] == 2
    assert result["error"] == "QwenOutputIncomplete"
    assert "audio" not in result
    assert not list(cache.rglob("*.json"))


@pytest.mark.parametrize("samples", [b"", b"\x01\x00"])
def test_cache_cannot_reuse_zero_sample_pcm_wav(tmp_path: Path, samples: bytes) -> None:
    worker_path = Path(__file__).parents[2] / "scripts/qwen_tts_worker.py"
    worker = runpy.run_path(str(worker_path))
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(samples)
    audio = output.getvalue()
    cached = tmp_path / "synthetic-cache.json"
    cached.write_text(
        json.dumps(
            {
                "cache_version": worker["CACHE_VERSION"],
                "fingerprint": "synthetic-fingerprint",
                "text_sha256": "synthetic-text-digest",
                "audio_sha256": hashlib.sha256(audio).hexdigest(),
                "audio": base64.b64encode(audio).decode(),
                "completion": COMPLETE,
            }
        )
    )
    result = worker["read_cache"](cached, "synthetic-text-digest", "synthetic-fingerprint")
    if not samples:
        assert len(audio) == 44
        assert result is None
    else:
        assert result == (audio, COMPLETE)
