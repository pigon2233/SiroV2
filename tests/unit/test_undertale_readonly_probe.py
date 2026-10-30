from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

from siro.services.computer_use.decision import Decision
from siro.services.computer_use.safety import InputAction

_path = Path(__file__).parents[2] / "scripts" / "verify_undertale_readonly.py"
_spec = importlib.util.spec_from_file_location("undertale_readonly_probe", _path)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            "SIRO_COMPUTER_CLOUD_SCREEN=0\nSIRO_COMPUTER_ALLOWED_PROCESSES=undertale.exe\n",
            "cloud_screen_not_authorized",
        ),
        (
            "SIRO_COMPUTER_CLOUD_SCREEN=1\nSIRO_COMPUTER_ALLOWED_PROCESSES=other.exe\n",
            "game_not_allowlisted",
        ),
    ],
)
async def test_denied_configuration_never_calls_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    config: str,
    error: str,
) -> None:
    path = tmp_path / "computer.env"
    path.write_text(config)
    monkeypatch.setattr(_module, "CONFIG", path)
    monkeypatch.setattr(_module.tempfile, "gettempdir", lambda: "/dev/shm")

    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("model was called")

    monkeypatch.setattr(_module, "ClaudeVisionDecider", denied)
    await _module.main()
    result = json.loads(capsys.readouterr().out)
    assert result["input_sent"] is False and result["error_code"] == error


@pytest.mark.asyncio
async def test_probe_only_returns_nonprivate_decision_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "computer.env"
    path.write_text("SIRO_COMPUTER_CLOUD_SCREEN=1\nSIRO_COMPUTER_ALLOWED_PROCESSES=undertale.exe\n")
    monkeypatch.setattr(_module, "CONFIG", path)
    monkeypatch.setattr(_module.tempfile, "gettempdir", lambda: "/dev/shm")
    monkeypatch.setattr(
        _module.sys,
        "stdin",
        io.StringIO(json.dumps({"width": 64, "height": 64, "image": "AAAA"}) + "\n"),
    )
    private = "PRIVATE-GAME-TEXT"

    class FakeDecider:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def decide(self, goal: str, history: object, obs: object) -> Decision:
            return Decision(
                "act", InputAction("key", key=private), reason=private, confidence=0.9, seen=private
            )

    monkeypatch.setattr(_module, "ClaudeVisionDecider", FakeDecider)
    await _module.main()
    output = capsys.readouterr().out
    assert private not in output
    result = json.loads(output)
    assert result["input_sent"] is False and result["key"] == "other"
