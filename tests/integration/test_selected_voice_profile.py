from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from siro.services.audio.tts import QwenVoiceProfile


def profile(tmp_path: Path, **changes: object) -> Path:
    reference = tmp_path / "B.wav"
    reference.touch()
    value = {
        "version": 1,
        "voice_id": "siro-sweet-b-v1",
        "reference_wav": str(reference),
        "reference_text": "你好。這是合成聲線。",
    } | changes
    path = tmp_path / "voice.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_load_selected_reference_preserves_its_actual_text(tmp_path: Path) -> None:
    selected = QwenVoiceProfile.load(profile(tmp_path))
    assert selected.voice_id == "siro-sweet-b-v1"
    assert selected.reference_text == "你好。這是合成聲線。"
    assert selected.reference_wav == tmp_path / "B.wav"


@pytest.mark.parametrize(
    "changes",
    [
        {"version": True},
        {"version": 2},
        {"voice_id": "../escape"},
        {"voice_id": ""},
        {"reference_text": ""},
        {"reference_text": "x" * 501},
        {"reference_text": "line\nExec=bad"},
        {"reference_wav": "relative.wav"},
        {"reference_wav": "/missing/synthetic.wav"},
        {"unexpected": "field"},
    ],
)
def test_invalid_explicit_profile_is_rejected(tmp_path: Path, changes: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="invalid Qwen voice profile"):
        QwenVoiceProfile.load(profile(tmp_path, **changes))


def test_profile_size_and_invalid_json_are_bounded(tmp_path: Path) -> None:
    path = tmp_path / "voice.json"
    for content in (b"x" * 16385, b"{", b"[]", b"\xff"):
        path.write_bytes(content)
        with pytest.raises(ValueError, match="invalid Qwen voice profile"):
            QwenVoiceProfile.load(path)


@pytest.mark.parametrize("assets", [True, False])
def test_main_selected_voice_is_owned_or_fails_without_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, assets: bool
) -> None:
    import uvicorn

    from siro.services.presentation import gateway

    for name in list(os.environ):
        if name.startswith("SIRO_") or name == "GROQ_API_KEY":
            monkeypatch.delenv(name)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_QWEN_VOICE_PROFILE", str(profile(tmp_path)))
    captured = []
    if assets:
        (tmp_path / "qwen-tts-venv/bin").mkdir(parents=True)
        (tmp_path / "qwen-tts-venv/bin/python").symlink_to(sys.executable)
        (tmp_path / "models/qwen3-tts-0.6b-base").mkdir(parents=True)

    class CaptureQwen:
        def __init__(self, *args: object, **kwargs: object) -> None:
            captured.append((args, kwargs))

    monkeypatch.setattr(gateway, "QwenReferenceTTS", CaptureQwen)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)
    if not assets:
        with pytest.raises(ValueError, match="configured Qwen voice assets are unavailable"):
            gateway.main()
        assert captured == []
        return
    gateway.main()
    assert len(captured) == 1
    args, kwargs = captured[0]
    assert args[3:5] == (tmp_path / "B.wav", "你好。這是合成聲線。")
    assert args[5] == tmp_path / "tts-cache/siro-sweet-b-v1"
    assert kwargs["lifecycle"] is True
