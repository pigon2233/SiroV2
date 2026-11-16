from __future__ import annotations

import importlib.util
import io
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from siro.services.computer_use.decision import Decision
from siro.services.computer_use.safety import InputAction


@pytest.fixture
def probe(monkeypatch: pytest.MonkeyPatch) -> Any:
    scripts = Path(__file__).parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "undertale_wait_probe", scripts / "compare_undertale_wait.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summary_never_contains_private_reason_or_unknown_key(probe: Any) -> None:
    private = "private-user-game-content"
    decision = Decision(
        "act", InputAction("key", key=private), reason=private, seen=private, confidence=0.8
    )
    output = json.dumps(probe.summarize(decision))
    assert private not in output
    assert json.loads(output)["key"] == "other"


@pytest.mark.asyncio
async def test_changed_frame_never_reaches_model(
    probe: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = tmp_path / "computer.env"
    config.write_text(
        "SIRO_COMPUTER_CLOUD_SCREEN=1\nSIRO_COMPUTER_ALLOWED_PROCESSES=undertale.exe\n"
    )
    monkeypatch.setattr(probe, "CONFIG", config)
    monkeypatch.setattr(probe.tempfile, "gettempdir", lambda: "/dev/shm")
    monkeypatch.setattr(probe.sys, "stdin", io.StringIO('{"same":false}\n'))
    calls = []

    def decider(**kwargs: object) -> None:
        calls.append(True)

    monkeypatch.setattr(probe, "ClaudeVisionDecider", decider)
    await probe.main()
    result = json.loads(capsys.readouterr().out)
    assert result["error_code"] == "frames_not_identical"
    assert result["input_sent"] is False
    assert calls == []


@pytest.mark.asyncio
async def test_simulated_histories_and_model_text_are_bounded(
    probe: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = tmp_path / "computer.env"
    config.write_text(
        "SIRO_COMPUTER_CLOUD_SCREEN=1\nSIRO_COMPUTER_ALLOWED_PROCESSES=undertale.exe\n"
    )
    monkeypatch.setattr(probe, "CONFIG", config)
    monkeypatch.setattr(probe.tempfile, "gettempdir", lambda: "/dev/shm")
    monkeypatch.setattr(
        probe.sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "same": True,
                    "width": 64,
                    "height": 64,
                    "image": "AAAA",
                }
            )
            + "\n"
        ),
    )
    observed = []
    private = "private-game-line"

    class FakeDecider:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def decide(self, goal: str, history: Sequence[Any], obs: object) -> Decision:
            observed.append([(step.action, step.screen_changed) for step in history])
            return Decision(
                "act", InputAction("key", key=private), reason=private, seen=private, confidence=0.8
            )

    monkeypatch.setattr(probe, "ClaudeVisionDecider", FakeDecider)
    await probe.main()
    output = capsys.readouterr().out
    result = json.loads(output)
    assert private not in output
    assert result["input_sent"] is False
    assert observed == [
        [("(wait)", None)],
        [("(wait)", False)],
        [("(wait)", None)] * 3,
        [("(wait)", False)] * 3,
    ]
    assert [case["key"] for case in result["cases"]] == ["other"] * 4
