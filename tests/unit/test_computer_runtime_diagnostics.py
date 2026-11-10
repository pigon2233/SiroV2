"""Deployment/source preflight is read-only and independently default off."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import DecisionError, OllamaVisionDecider, make_decider
from siro.services.computer_use.http import TOKEN_HEADER, ComputerRuns, build_router
from siro.services.computer_use.runtime_info import RUNTIME_ENV, runtime_info
from siro.services.computer_use.safety import ControlGate

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
import computer_runtime_check as preflight


def test_identity_default_off_and_actual_loaded_root() -> None:
    brain = make_decider({})
    assert runtime_info(brain, {}) is None
    info = runtime_info(brain, {RUNTIME_ENV: "1"})
    assert info is not None
    assert info["pid"] == os.getpid()
    assert Path(info["source_root"]) == Path(__file__).parents[2]
    assert info["decider_chain"] == ["OllamaVisionDecider"]
    assert all("token" not in key.lower() for key in info)
    assert preflight.validate({"runtime": info}, Path(__file__).parents[2]) == ""


@pytest.mark.parametrize("status", [{}, None, {"runtime": {}}, {"runtime": {"version": 2}}])
def test_missing_old_server_identity_fails_closed(status: Any) -> None:
    assert preflight.validate(status, Path("/expected")).startswith("backend_checkout_unverified")


def test_wrong_checkout_and_mixed_module_rejected() -> None:
    status = {
        "runtime": {
            "version": 1,
            "source_root": "/old-worktree",
            "decision_module": "/old-worktree/src/siro/services/computer_use/decision.py",
        }
    }
    assert preflight.validate(status, Path("/main")).startswith("backend_checkout_mismatch")
    status["runtime"]["source_root"] = "/main"
    assert preflight.validate(status, Path("/main")).startswith("backend_checkout_mismatch")


def test_checkout_flag_default_off_and_last_config_wins(tmp_path: Path) -> None:
    config = tmp_path / "computer.env"
    config.write_text(
        "SIRO_COMPUTER_TOKEN=not-for-output\n"
        "SIRO_COMPUTER_REQUIRE_CHECKOUT=0\n"
        'export SIRO_COMPUTER_REQUIRE_CHECKOUT="1"\n'
    )
    assert not preflight.enabled({}, None)
    assert preflight.enabled({}, config)
    assert not preflight.enabled({preflight.CHECK_ENV: "0"}, config)


def test_unsupported_backend_strict_flag_does_not_silently_switch() -> None:
    assert isinstance(
        make_decider({"SIRO_COMPUTER_DECIDER": "ollama-grounded"}), OllamaVisionDecider
    )
    with pytest.raises(DecisionError, match="unsupported_decider"):
        make_decider(
            {"SIRO_COMPUTER_DECIDER": "ollama-grounded", "SIRO_COMPUTER_STRICT_BACKEND": "1"}
        )
    assert isinstance(
        make_decider({"SIRO_COMPUTER_DECIDER": "ollama", "SIRO_COMPUTER_STRICT_BACKEND": "1"}),
        OllamaVisionDecider,
    )


def test_runtime_info_still_requires_http_auth_and_cannot_enable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "1")
    bridge = ComputerBridge(ControlGate(enabled=False))
    runs = ComputerRuns(bridge, make_decider({}))
    app = FastAPI()
    app.include_router(build_router("t" * 40, runs))
    with TestClient(app, client=("127.0.0.1", 5000)) as client:
        assert client.get("/v1/computer/status").status_code == 401
        status = client.get("/v1/computer/status", headers={TOKEN_HEADER: "t" * 40}).json()
        assert status["runtime"]["pid"] == os.getpid() and not status["enabled"]
    assert not bridge.gate.enabled


def test_play_client_old_server_is_rejected_before_run(tmp_path: Path) -> None:
    """Fake HTTP only: the shell client must stop after GET status, no POST/input."""
    home = tmp_path / "user"
    config = home / "siro-computer" / "computer.env"
    config.parent.mkdir(parents=True)
    config.write_text("SIRO_COMPUTER_TOKEN=unit\nSIRO_COMPUTER_REQUIRE_CHECKOUT=1\n")
    commands = tmp_path / "bin"
    commands.mkdir()
    call_log = tmp_path / "requests.txt"
    stubs = {
        "cmd.exe": "#!/bin/sh\nprintf user\n",
        "wslpath": f'#!/bin/sh\nprintf "%s" "{home}"\n',
        "curl": f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{call_log}"\nprintf \'%s\' \'{{"enabled":true}}\'\n',  # noqa: E501 - shell stub literal
    }
    for name, body in stubs.items():
        file = commands / name
        file.write_text(body)
        file.chmod(0o755)
    values = {**os.environ, "PATH": str(commands) + os.pathsep + os.environ["PATH"]}
    values.pop(preflight.CHECK_ENV, None)
    result = subprocess.run(
        ["bash", str(Path(__file__).parents[2] / "scripts/computer-play.sh"), "unit-goal", "0"],
        env=values,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2 and "backend_checkout_unverified" in result.stderr
    calls = call_log.read_text().splitlines()
    assert len(calls) == 1 and "/status" in calls[0]
    assert "/run" not in calls[0] and "/stop" not in calls[0]


@pytest.mark.parametrize(
    "point,expected",
    [
        ((731, 209), (1462, 418)),
        ((739, 220), (1478, 440)),
        ((256, 152), (512, 304)),
        ((255, 427), (510, 854)),
    ],
)
def test_reported_run_coordinate_math_not_input(
    point: tuple[int, int], expected: tuple[int, int]
) -> None:
    from siro.services.computer_use.perception import Observation, image_to_screen

    observation = Observation(
        1,
        0,
        "Game",
        "game.exe",
        (0, 0, 1920, 1040),
        (1920, 1080),
        "hash",
        image_size=(960, 520),
        image_rect=(0, 0, 1920, 1040),
    )
    assert image_to_screen(observation, *point) == expected


def test_offline_verifier_probe_is_default_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    from computer_verify_eval import probe

    monkeypatch.delenv("SIRO_COMPUTER_VERIFY_BENCH_ENABLED", raising=False)
    with pytest.raises(ValueError, match="offline verify probe off"):
        asyncio.run(probe(tmp_path / "missing.json", tmp_path / "output.json", 1))
    assert not (tmp_path / "output.json").exists()
