"""The normal companion launcher must preserve the private ESP32 relay setting."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def _write_script(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


def _token_file(tmp_path: Path, *, mode: int = 0o600) -> Path:
    path = tmp_path / "config/siro/esp32-relay-token"
    path.parent.mkdir(parents=True)
    path.write_text("synthetic-relay-token-12345678901234567890", encoding="ascii")
    path.chmod(mode)
    return path


def test_companion_passes_private_token_only_to_gateway(tmp_path: Path) -> None:
    project = tmp_path / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    for name in ("start-companion", "load-esp32-relay-token"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    _write_script(
        scripts / "start",
        "#!/usr/bin/env bash\n"
        'printf "%s" "${SIRO_ESP32_RELAY_TOKEN:-missing}" > "$SIRO_TEST_GATEWAY_TOKEN"\n'
        'touch "$SIRO_TEST_READY"\n',
    )
    _write_script(
        scripts / "start-desktop",
        "#!/usr/bin/env bash\n"
        'printf "%s" "${SIRO_ESP32_RELAY_TOKEN:-unset}" > "$SIRO_TEST_DESKTOP_TOKEN"\n',
    )
    binary = tmp_path / "bin"
    binary.mkdir()
    _write_script(binary / "curl", '#!/usr/bin/env bash\ntest -e "$SIRO_TEST_READY"\n')
    token_file = _token_file(tmp_path)
    environment = {
        **os.environ,
        "PATH": f"{binary}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(token_file.parents[1]),
        "SIRO_DATA_DIR": str(tmp_path / "data"),
        "SIRO_LOG_DIR": str(tmp_path / "logs"),
        "SIRO_TEST_GATEWAY_TOKEN": str(tmp_path / "gateway-token"),
        "SIRO_TEST_DESKTOP_TOKEN": str(tmp_path / "desktop-token"),
        "SIRO_TEST_READY": str(tmp_path / "ready"),
    }
    environment.pop("SIRO_ESP32_RELAY_TOKEN", None)
    result = subprocess.run(
        ["bash", "scripts/start-companion"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "gateway-token").read_text() == token_file.read_text()
    assert (tmp_path / "desktop-token").read_text() == "unset"
    assert token_file.read_text() not in result.stdout + result.stderr


@pytest.mark.parametrize("mode", [0o644, 0o660])
def test_private_token_rejects_shared_permissions(tmp_path: Path, mode: int) -> None:
    token_file = _token_file(tmp_path, mode=mode)
    environment = {
        **os.environ,
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(token_file.parents[1]),
    }
    environment.pop("SIRO_ESP32_RELAY_TOKEN", None)
    result = subprocess.run(
        ["bash", "-c", 'source "$1"', "bash", str(ROOT / "scripts/load-esp32-relay-token")],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    assert token_file.read_text() not in result.stdout + result.stderr


def test_no_private_token_keeps_ingress_disabled(tmp_path: Path) -> None:
    environment = {**os.environ, "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path)}
    environment.pop("SIRO_ESP32_RELAY_TOKEN", None)
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; printf "%s" "${SIRO_ESP32_RELAY_TOKEN:-unset}"',
            "bash",
            str(ROOT / "scripts/load-esp32-relay-token"),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "unset"


def test_private_token_rejects_symlink(tmp_path: Path) -> None:
    source = _token_file(tmp_path)
    link = source.with_name("token-link")
    source.rename(link)
    source.symlink_to(link)
    environment = {**os.environ, "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(source.parents[1])}
    environment.pop("SIRO_ESP32_RELAY_TOKEN", None)
    result = subprocess.run(
        ["bash", "-c", 'source "$1"', "bash", str(ROOT / "scripts/load-esp32-relay-token")],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    assert link.read_text() not in result.stdout + result.stderr


def test_explicit_environment_token_takes_precedence(tmp_path: Path) -> None:
    _token_file(tmp_path, mode=0o644)
    provided = "synthetic-explicit-token-12345678901234567890"
    environment = {
        **os.environ,
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "SIRO_ESP32_RELAY_TOKEN": provided,
    }
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; printf "%s" "$SIRO_ESP32_RELAY_TOKEN"',
            "bash",
            str(ROOT / "scripts/load-esp32-relay-token"),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == provided
