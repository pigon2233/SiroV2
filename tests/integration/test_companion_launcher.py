from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

import pytest


def launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    spec = importlib.util.spec_from_file_location(
        "companion_launcher", Path(__file__).resolve().parents[2] / "scripts/launch_companion.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "scripts/launch_companion.py"))
    for key in tuple(os.environ):
        if key.startswith("SIRO_"):
            monkeypatch.delenv(key)
    return module


def test_product_launcher_never_silently_starts_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = launcher(tmp_path, monkeypatch)
    called: list[object] = []
    monkeypatch.setattr(module.os, "execv", lambda *args: called.append(args))
    with pytest.raises(SystemExit, match="尚未設定對話模型"):
        module.main()
    assert not called


def test_launcher_rejects_unsupported_native_budget_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = launcher(tmp_path, monkeypatch)
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic-local")
    with pytest.raises(SystemExit, match="尚無已驗證的 token"):
        module.main()


def test_launcher_loads_only_model_settings_without_overriding_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = launcher(tmp_path, monkeypatch)
    (tmp_path / ".env.local").write_text(
        '# synthetic configuration\nSIRO_OPENAI_MODEL="openai/gpt-oss-20b"\n'
        'SIRO_OPENAI_API_KEY="synthetic-not-a-real-key"\n'  # pragma: allowlist secret
        'SIRO_OPENAI_BASE_URL="https://api.groq.com/openai"\n'
        'SIRO_DATA_DIR="should-not-load"\n'
        "SIRO_CONTEXT_TOKEN_BUDGET_ENABLED=0\n"
        "SIRO_MODEL_ROUTER=1\n"
    )
    monkeypatch.setenv("SIRO_OPENAI_API_KEY", "synthetic-shell-setting")  # pragma: allowlist secret
    binary = tmp_path / "target/debug/siro-runtime"
    binary.parent.mkdir(parents=True)
    binary.touch()
    renderer = tmp_path / "renderer"
    renderer.mkdir()
    (renderer / "index.html").write_text("synthetic licensed renderer fixture")
    monkeypatch.setenv("SIRO_LIVE2D_DIST", str(renderer))
    calls: list[object] = []
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(module.os, "execv", lambda *a: calls.append(a))
    module.main()
    assert (
        os.environ["SIRO_OPENAI_API_KEY"] == "synthetic-shell-setting"  # pragma: allowlist secret
    )  # pragma: allowlist secret
    assert os.environ["SIRO_OPENAI_MODEL"] == "openai/gpt-oss-20b"
    assert "SIRO_DATA_DIR" not in os.environ
    assert "SIRO_CONTEXT_TOKEN_BUDGET_ENABLED" not in os.environ
    assert os.environ["SIRO_MODEL_ROUTER"] == "1"
    assert os.environ["SIRO_RUNTIME_PROFILE"] == "candidate"
    assert len(calls) == 2  # pinned tokenizer provisioning then the actual gateway process
    assert "synthetic-shell-setting" not in capsys.readouterr().out


def _ready_launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    module = launcher(tmp_path, monkeypatch)
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic-local")
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    binary = tmp_path / "target/debug/siro-runtime"
    binary.parent.mkdir(parents=True)
    binary.touch()
    return module


def test_candidate_variant_selects_the_preview_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _ready_launcher(tmp_path, monkeypatch)
    monkeypatch.setenv("SIRO_VRM_VARIANT", "candidate")
    renderer = tmp_path / "models/vrm-renderer"
    renderer.mkdir(parents=True)
    (renderer / "index.html").write_text("synthetic renderer", encoding="utf-8")
    manifest = tmp_path / ".siro-data/vroid/candidate-registered/asset-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    daily = tmp_path / "config/body-assets/siro-vrm/asset-manifest.json"
    daily.parent.mkdir(parents=True)
    daily.write_text("{}", encoding="utf-8")
    calls: list[object] = []
    monkeypatch.setattr(module.os, "execv", lambda *args: calls.append(args))
    module.main()
    assert os.environ["SIRO_VRM_MODEL_MANIFEST"] == str(manifest)
    assert os.environ["SIRO_VRM_DIST"] == str(renderer)
    assert calls


def test_candidate_variant_does_not_fall_through_to_the_daily_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _ready_launcher(tmp_path, monkeypatch)
    monkeypatch.setenv("SIRO_VRM_VARIANT", "candidate")
    calls: list[object] = []
    monkeypatch.setattr(module.os, "execv", lambda *args: calls.append(args))
    with pytest.raises(SystemExit, match="找不到候選 VRM"):
        module.main()
    assert calls == []


def test_unknown_vrm_variant_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _ready_launcher(tmp_path, monkeypatch)
    monkeypatch.setenv("SIRO_VRM_VARIANT", "other")
    with pytest.raises(SystemExit, match="只接受 candidate"):
        module.main()
