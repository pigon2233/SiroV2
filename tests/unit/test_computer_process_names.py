"""Exact normalization vectors and entry/foreground privacy contracts. No native input."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from siro.services.computer_use.bridge import BridgeResult, ComputerBridge
from siro.services.computer_use.intent import names_program
from siro.services.computer_use.interface import Decision, VerifyResult
from siro.services.computer_use.loop import DecisionLoop
from siro.services.computer_use.perception import Observation, sanitize
from siro.services.computer_use.process_names import NORMALIZE_ENV, process_in, process_key
from siro.services.computer_use.safety import ControlGate

VECTORS = json.loads(
    (Path(__file__).parents[1] / "fixtures/computer-process-names.json").read_text()
)
ON = {NORMALIZE_ENV: "1"}


@pytest.mark.parametrize("left,right,match", VECTORS)
def test_exact_canonical_vectors(left: str, right: str, match: bool) -> None:
    assert process_in(left, [right], ON) is match


def test_default_off_and_no_empty_authorization() -> None:
    assert not process_in("Slay the Spire 2.exe", ["slaythespire2.exe"], {})
    assert process_in("game.exe", ["game.exe"], {})
    assert not process_in("---", ["___"], ON)
    assert not process_in("game.exe", [], ON)
    assert process_key("game.exe.exe") == "gameexe"


@pytest.mark.parametrize("process", ["Bit Warden.exe", "1 Password.exe", "Kee-Pass-XC.exe"])
def test_normalization_cannot_evade_privacy(process: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(NORMALIZE_ENV, "1")
    obs = sanitize(
        {
            "title": "app",
            "process": process,
            "screen": [100, 100],
            "image_png_b64": "AAA",
            "image_size": [100, 100],
        },
        seq=1,
        now=0,
    )
    assert obs.blocked_reason == "blocked_process" and obs.image_png_b64 is None


def test_entry_goal_only_matches_exact_letters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(NORMALIZE_ENV, "1")
    assert names_program("slaythespire2", "play Slay the Spire 2 now")
    assert not names_program("slaythespire2", "play slay the spire 2helper")
    assert not names_program("slaythespire2", "play slay the spire 3")
    assert not names_program("game.exe", "play game")
    assert names_program("game.exe", "play game exe")
    loop = DecisionLoop(
        ComputerBridge(ControlGate(enabled=False)),
        None,  # type: ignore[arg-type]
        allowed=frozenset({"notepad.exe", "slaythespire2.exe"}),
    )
    assert loop._focus_target("play Slay the Spire 2") == "slaythespire2.exe"


def test_backend_focus_flag_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class Probe(ComputerBridge):
        async def _request(
            self, op: str, payload: dict[str, object], timeout: float, error: str
        ) -> BridgeResult:
            assert payload == {"process": "slaythespire2.exe", "normalize_process_names": True}
            return BridgeResult(True)

    monkeypatch.setenv(NORMALIZE_ENV, "1")
    assert asyncio.run(Probe(ControlGate(enabled=True)).focus("slaythespire2.exe")).ok


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="Windows PowerShell unavailable")
def test_native_pure_vectors_from_wsl() -> None:
    script = Path(__file__).parents[2] / "desktop-win/process-names.test.ps1"
    win = subprocess.check_output(["wslpath", "-w", str(script)], text=True).strip()
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", win],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "vectors passed: 19" in result.stdout


def test_actual_entry_allows_only_normalized_exact_process(monkeypatch: pytest.MonkeyPatch) -> None:
    class ReadOnlyBridge(ComputerBridge):
        async def observe(self) -> tuple[Observation | None, str]:
            return sanitize(
                {"title": "Game", "process": "Slay the Spire 2.exe", "screen": [100, 100]},
                seq=1,
                now=0,
            ), ""

    class WaitOnly:
        calls = 0

        async def decide(self, *args: object, **kw: object) -> Decision:
            self.calls += 1
            return Decision("wait")

        async def verify(self, *args: object) -> VerifyResult:
            raise AssertionError("wait must not verify")

    for value, expected, calls in (("0", "window_not_allowed", 0), ("1", "step_limit", 1)):
        monkeypatch.setenv(NORMALIZE_ENV, value)
        gate = ControlGate(enabled=False)
        script = WaitOnly()
        controller = DecisionLoop(
            ReadOnlyBridge(gate),
            script,
            allowed=frozenset({"slaythespire2.exe"}),
            max_steps=1,
            focus=False,
            wait=0,
            clock=lambda: 0,
        )
        assert asyncio.run(controller.run("play Slay the Spire 2")).reason == expected
        assert script.calls == calls and not gate.enabled
