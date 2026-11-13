"""Windows pet launcher: one entry point, in-repo backend, wrapper only as fallback."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SETSID = """#!/bin/bash
printf '%s\\n' "$*" >> "$SIRO_TEST_SETSID_LOG"
printf 'token=%s\\n' "${SIRO_COMPUTER_TOKEN-}" >> "$SIRO_TEST_SETSID_LOG"
printf 'other=%s\\n' "${SIRO_OTHER-unset}" >> "$SIRO_TEST_SETSID_LOG"
if [[ -n "${SIRO_TEST_HOLD:-}" ]]; then
  sleep 30 &
  echo $! > "$SIRO_WIN_LAUNCHER_PID"
  echo $! >> "$SIRO_TEST_HOLD_PIDS"
fi
exit 0
"""

CURL = """#!/bin/bash
n=0
if [[ -f "$SIRO_TEST_CURL_COUNT" ]]; then n=$(cat "$SIRO_TEST_CURL_COUNT"); fi
n=$((n + 1))
printf '%s\\n' "$n" > "$SIRO_TEST_CURL_COUNT"
if [[ "$n" -ge "${SIRO_TEST_CURL_READY:-99}" ]]; then exit 0; fi
exit 7
"""


def _executable(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {
        "PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin",
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "SIRO_GATEWAY_PORT": "18765",
        "SIRO_WIN_BACKEND_LOG": str(tmp_path / "backend.log"),
        "SIRO_WIN_LAUNCHER_PID": str(tmp_path / "launcher.pid"),
        "SIRO_READY_ATTEMPTS": "3",
        "SIRO_READY_PAUSE": "0",
        "SIRO_TEST_SETSID_LOG": str(tmp_path / "setsid.log"),
        "SIRO_TEST_CURL_COUNT": str(tmp_path / "curl.count"),
        "SIRO_TEST_CURL_READY": "99",
        "SIRO_COMPUTER_ENV_FILE": str(tmp_path / "missing-computer.env"),
        "SIRO_START_COMPANION": str(tmp_path / "start-companion"),
        "SIRO_COMPANION_WRAPPER": str(tmp_path / "wrapper"),
        "SIRO_CANDIDATE_WRAPPER": str(tmp_path / "candidate-wrapper"),
        "SIRO_TEST_HOLD_PIDS": str(tmp_path / "hold.pids"),
    }
    env.update(extra)
    return env


def _install_fakes(tmp_path: Path) -> None:
    _executable(tmp_path / "bin/setsid", SETSID)
    _executable(tmp_path / "bin/curl", CURL)


def _run(tmp_path: Path, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    _install_fakes(tmp_path)
    return subprocess.run(
        ["bash", str(ROOT / "scripts/start-win-backend"), *args],
        cwd=ROOT,
        env=_env(tmp_path, **extra),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def _stop_holds(tmp_path: Path) -> None:
    path = tmp_path / "hold.pids"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").split():
        if not line.isdigit():
            continue
        with contextlib.suppress(ProcessLookupError):
            os.kill(int(line), signal.SIGTERM)


def _setsid_log(tmp_path: Path) -> str:
    path = tmp_path / "setsid.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_already_ready_backend_is_left_alone(tmp_path: Path) -> None:
    result = _run(tmp_path, SIRO_TEST_CURL_READY="1")
    assert result.returncode == 0, result.stderr
    assert _setsid_log(tmp_path) == ""


def test_candidate_refuses_to_reuse_a_running_backend(tmp_path: Path) -> None:
    result = _run(tmp_path, "candidate", SIRO_TEST_CURL_READY="1")
    assert result.returncode == 1
    assert "後端仍在執行" in result.stderr
    assert _setsid_log(tmp_path) == ""


def test_in_repo_companion_starts_before_any_wrapper(tmp_path: Path) -> None:
    _executable(tmp_path / "start-companion", "#!/bin/bash\nexit 0\n")
    _executable(tmp_path / "wrapper", "#!/bin/bash\nexit 0\n")
    result = _run(tmp_path, SIRO_TEST_CURL_READY="2")
    assert result.returncode == 0, result.stderr
    log = _setsid_log(tmp_path)
    assert "COMPANION_BACKEND_ONLY=1" in log
    assert str(tmp_path / "start-companion") in log
    assert str(tmp_path / "wrapper") not in log


def test_wrapper_is_used_only_after_the_checkout_launcher_is_missing(tmp_path: Path) -> None:
    _executable(tmp_path / "wrapper", "#!/bin/bash\nexit 0\n")
    result = _run(tmp_path, SIRO_TEST_CURL_READY="4")
    assert result.returncode == 0, result.stderr
    log = _setsid_log(tmp_path)
    assert str(tmp_path / "wrapper") in log
    assert str(tmp_path / "start-companion") not in log
    assert log.count("COMPANION_BACKEND_ONLY=1") == 1


def test_candidate_does_not_fall_back_to_the_daily_wrapper(tmp_path: Path) -> None:
    _executable(tmp_path / "wrapper", "#!/bin/bash\nexit 0\n")
    result = _run(tmp_path, "candidate")
    assert result.returncode == 1
    assert str(tmp_path / "wrapper") not in _setsid_log(tmp_path)


def test_living_checkout_launch_blocks_a_second_backend(tmp_path: Path) -> None:
    _executable(tmp_path / "start-companion", "#!/bin/bash\nexit 0\n")
    _executable(tmp_path / "wrapper", "#!/bin/bash\nexit 0\n")
    try:
        result = _run(tmp_path, SIRO_TEST_HOLD="1", SIRO_READY_ATTEMPTS="1")
        assert result.returncode == 1
        assert "尚未就緒" in result.stderr
        assert str(tmp_path / "wrapper") not in _setsid_log(tmp_path)
        assert _setsid_log(tmp_path).count("COMPANION_BACKEND_ONLY=1") == 1
    finally:
        _stop_holds(tmp_path)


def test_computer_env_values_are_not_executed(tmp_path: Path) -> None:
    pwn = tmp_path / "pwn"
    env_file = tmp_path / "computer.env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "SIRO_OTHER=should-not-export",
                f"SIRO_COMPUTER_TOKEN=$(touch {pwn})",
                'export SIRO_COMPUTER_ALLOWED_PROCESSES="game.exe"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    _executable(tmp_path / "start-companion", "#!/bin/bash\nexit 0\n")
    result = _run(
        tmp_path,
        SIRO_TEST_CURL_READY="2",
        SIRO_COMPUTER_ENV_FILE=str(env_file),
    )
    assert result.returncode == 0, result.stderr
    assert not pwn.exists()
    log = _setsid_log(tmp_path)
    assert f"token=$(touch {pwn})" in log
    assert "other=unset" in log
    assert "should-not-export" not in log


def test_unknown_backend_mode_is_rejected(tmp_path: Path) -> None:
    result = _run(tmp_path, "nope")
    assert result.returncode == 2
    assert _setsid_log(tmp_path) == ""


def test_stop_prefers_the_local_stop_command(tmp_path: Path) -> None:
    marker = tmp_path / "stopped"
    _executable(
        tmp_path / "siro-stop",
        f"#!/bin/bash\nprintf stopped > {marker}\n",
    )
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/stop-win-backend")],
        cwd=ROOT,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path / "home"),
            "SIRO_STOP_BIN": str(tmp_path / "siro-stop"),
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8") == "stopped"


def test_stop_falls_back_to_the_companion_pid_file(tmp_path: Path) -> None:
    held = subprocess.Popen(["sleep", "30"])
    data = tmp_path / "data"
    data.mkdir()
    (data / "companion-service.pid").write_text(f"{held.pid}\n", encoding="utf-8")
    try:
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/stop-win-backend")],
            cwd=ROOT,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(tmp_path / "home"),
                "SIRO_STOP_BIN": str(tmp_path / "missing-stop"),
                "SIRO_DATA_DIR": str(data),
            },
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        held.wait(timeout=5)
    finally:
        if held.poll() is None:
            held.kill()


def test_user_facing_windows_launchers_are_the_vrm_win_pair() -> None:
    commands = sorted(path.name for path in ROOT.glob("*.cmd"))
    assert commands == ["Play-SIRO.cmd", "Start-SIRO-VRM-Win.cmd", "Stop-SIRO-Win.cmd"]
    legacy = sorted(path.name for path in (ROOT / "scripts/legacy").glob("*.cmd"))
    assert legacy == [
        "Start-ESP32-Broker.cmd",
        "Start-SIRO-VRM-Candidate.cmd",
        "Start-SIRO-VRM.cmd",
        "Start-SIRO.cmd",
        "Stop-SIRO.cmd",
    ]
    broker = (ROOT / "scripts/start-esp32-broker.ps1").read_text(encoding="utf-8")
    assert "scripts\\legacy\\Start-ESP32-Broker.cmd" in broker
    moved = (ROOT / "scripts/legacy/Start-ESP32-Broker.cmd").read_text(encoding="utf-8")
    assert "%ROOT%\\scripts\\esp32_mqtt_broker.py" in moved
    assert "%~dp0scripts\\" not in moved
    window = (ROOT / "Start-SIRO-VRM-Win.cmd").read_text(encoding="utf-8")
    assert "/stop" in window and "/backend" in window and "/candidate" in window
    assert "start http" not in window.lower()
    stop = (ROOT / "Stop-SIRO-Win.cmd").read_text(encoding="utf-8")
    assert 'Start-SIRO-VRM-Win.cmd" /stop' in stop
    pet = (ROOT / "desktop-win/main.js").read_text(encoding="utf-8")
    assert "skipTaskbar: false" not in pet
    assert pet.count("skipTaskbar: true") >= 2
    host = pet.split("function ensureCaptureHost", 1)[1].split("function ", 1)[0]
    assert "skipTaskbar: true" in host and "show: false" in host
