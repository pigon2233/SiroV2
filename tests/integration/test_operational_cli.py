from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

import pytest

from siro.cli import main
from siro.config import ProactivitySettings, SiroSettings
from siro.operations import install_user_service, prune_logs
from siro.persistence.sqlite import SQLiteStore


def test_t34_backup_restore_cli_uses_clean_data_directories(tmp_path: Path) -> None:
    source_data = tmp_path / "source"
    backup = tmp_path / "backup.sqlite3"
    assert main(["demo", "--data", str(source_data), "--once", "hello"]) == 0
    assert main(["backup", "--data", str(source_data), str(backup)]) == 0
    restored_data = tmp_path / "restored"
    assert main(["restore", "--data", str(restored_data), str(backup)]) == 0
    store = SQLiteStore(restored_data / "siro.db")
    assert asyncio.run(store.integrity_check()) == "ok"


def test_t34_bundle_restores_database_and_settings_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    source_data = tmp_path / "source"
    source_config = tmp_path / "source-config.json"
    source_config.write_text(
        SiroSettings(proactivity=ProactivitySettings(enabled=True)).model_dump_json(indent=2),
        encoding="utf-8",
    )
    bundle = tmp_path / "backup.zip"
    assert main(["demo", "--data", str(source_data), "--once", "hello"]) == 0
    assert (
        main(
            [
                "backup",
                "--data",
                str(source_data),
                "--config",
                str(source_config),
                str(bundle),
            ]
        )
        == 0
    )
    restored_data = tmp_path / "restored"
    restored_config = tmp_path / "restored-config.json"
    assert (
        main(
            [
                "restore",
                "--data",
                str(restored_data),
                "--config",
                str(restored_config),
                str(bundle),
            ]
        )
        == 0
    )
    assert SiroSettings.model_validate_json(restored_config.read_text()).proactivity.enabled

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(tampered, "w") as target:
        for name in source.namelist():
            value = source.read(name)
            target.writestr(name, b"tampered" if name == "config.json" else value)
    with pytest.raises(ValueError, match="hash mismatch"):
        main(
            [
                "restore",
                "--data",
                str(tmp_path / "rejected"),
                "--config",
                str(tmp_path / "rejected.json"),
                str(tampered),
            ]
        )


def test_t34_installer_units_and_log_retention(tmp_path: Path) -> None:
    project = tmp_path / "project"
    binaries = project / ".venv/bin"
    binaries.mkdir(parents=True)
    for name in ("siro", "siro-gateway"):
        executable = binaries / name
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)
    units = tmp_path / "units"
    logs = tmp_path / "logs"
    result = install_user_service(
        project,
        unit_dir=units,
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        log_dir=logs,
        port=8765,
    )
    assert result.unit.stat().st_mode & 0o777 == 0o600
    assert "NoNewPrivileges=true" in result.unit.read_text()
    assert "SIRO_GATEWAY_PORT=8765" in result.unit.read_text()
    subprocess.run(["systemd-analyze", "verify", str(result.unit)], check=True)

    old = logs / "siro.log.2026-01-01"
    current = logs / "siro.log"
    logs.mkdir(exist_ok=True)
    old.write_text("old", encoding="utf-8")
    current.write_text("current", encoding="utf-8")
    now = time.time()
    os.utime(old, (now - 15 * 86400, now - 15 * 86400))
    assert prune_logs(logs, days=14, now=now) == (old,)
    assert current.exists()


def test_t34_start_stop_health_and_pid_cleanup(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    pid_file = tmp_path / "siro.pid"
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SIRO_") and key != "GROQ_API_KEY"
    }
    environment["SIRO_DATA_DIR"] = str(tmp_path / "data")
    environment["SIRO_GATEWAY_PORT"] = str(port)
    environment["SIRO_LOG_DIR"] = str(tmp_path / "logs")
    process = subprocess.Popen(
        [str(root / "scripts/start"), str(pid_file)],
        cwd=root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health/ready", timeout=0.2
                ) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("gateway did not become ready")
        subprocess.run([str(root / "scripts/stop"), str(pid_file)], check=True)
        process.wait(timeout=10)
        assert process.returncode in {0, 143}
        assert not pid_file.exists()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
