"""Reproducible local installation, configuration backup, and log retention."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from siro.config import SiroSettings
from siro.persistence.sqlite import SQLiteStore


@dataclass(frozen=True, slots=True)
class InstallResult:
    unit: Path
    timer: Path
    config: Path


def _unit_quote(value: str) -> str:
    return '"' + value.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _unit_path(value: str) -> str:
    return value.replace("%", "%%").replace(" ", "\\x20")


def install_user_service(
    project_root: Path,
    *,
    unit_dir: Path,
    config_dir: Path,
    data_dir: Path,
    log_dir: Path,
    port: int = 8000,
) -> InstallResult:
    """Install deterministic user units without starting them."""

    root = project_root.resolve()
    executable = root / ".venv/bin/siro-gateway"
    cli = root / ".venv/bin/siro"
    if not executable.is_file() or not cli.is_file():
        raise FileNotFoundError("run 'uv sync --locked' before installing the service")
    for directory in (unit_dir, config_dir, data_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)
    config = config_dir / "config.json"
    if not config.exists():
        _atomic_write(config, SiroSettings().model_dump_json(indent=2) + "\n", 0o600)
    unit = unit_dir / "siro-gateway.service"
    unit_content = f"""[Unit]
Description=SIRO loopback presentation gateway
After=network.target

[Service]
Type=simple
WorkingDirectory={_unit_path(str(root))}
ExecStart={_unit_quote(str(executable))}
Environment={_unit_quote(f"SIRO_CONFIG={config}")}
Environment={_unit_quote(f"SIRO_DATA_DIR={data_dir}")}
Environment={_unit_quote(f"SIRO_LOG_DIR={log_dir}")}
Environment={_unit_quote(f"SIRO_GATEWAY_PORT={port}")}
Restart=on-failure
RestartSec=3
KillSignal=SIGTERM
TimeoutStopSec=20
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
"""
    _atomic_write(unit, unit_content, 0o600)
    prune_service = unit_dir / "siro-log-prune.service"
    _atomic_write(
        prune_service,
        "[Unit]\nDescription=Prune expired SIRO operational logs\n\n"
        "[Service]\nType=oneshot\n"
        f"ExecStart={_unit_quote(str(cli))} prune-logs --directory "
        f"{_unit_quote(str(log_dir))} --days 14\nNoNewPrivileges=true\n",
        0o600,
    )
    timer = unit_dir / "siro-log-prune.timer"
    _atomic_write(
        timer,
        "[Unit]\nDescription=Daily SIRO log retention\n\n"
        "[Timer]\nOnCalendar=daily\nPersistent=true\nUnit=siro-log-prune.service\n\n"
        "[Install]\nWantedBy=timers.target\n",
        0o600,
    )
    return InstallResult(unit, timer, config)


def enable_user_service() -> None:
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "siro-gateway.service"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "siro-log-prune.timer"], check=True)


def prune_logs(directory: Path, *, days: int, now: float | None = None) -> tuple[Path, ...]:
    if not 1 <= days <= 3650:
        raise ValueError("retention days must be between 1 and 3650")
    cutoff = (time.time() if now is None else now) - days * 86400
    removed: list[Path] = []
    if not directory.exists():
        return ()
    for path in directory.glob("siro.log.*"):
        if path.is_file() and not path.is_symlink() and path.stat().st_mtime < cutoff:
            path.unlink()
            removed.append(path)
    return tuple(removed)


async def create_backup_bundle(store: SQLiteStore, destination: Path, *, config: Path) -> None:
    """Create a hashed ZIP containing the consistent DB snapshot and settings."""

    settings = SiroSettings.model_validate_json(config.read_text(encoding="utf-8"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="siro-backup-") as raw:
        temporary_dir = Path(raw)
        database = temporary_dir / "siro.db"
        await store.backup_to(database)
        config_bytes = settings.model_dump_json(indent=2).encode() + b"\n"
        database_bytes = database.read_bytes()
        manifest = {
            "format": 1,
            "files": {
                "siro.db": hashlib.sha256(database_bytes).hexdigest(),
                "config.json": hashlib.sha256(config_bytes).hexdigest(),
            },
        }
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("siro.db", database_bytes)
            archive.writestr("config.json", config_bytes)
            archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        temporary.replace(destination)


async def restore_backup_bundle(store: SQLiteStore, source: Path, *, config: Path) -> None:
    """Verify a bundle fully before atomically restoring DB and settings."""

    with zipfile.ZipFile(source) as archive:
        if set(archive.namelist()) != {"siro.db", "config.json", "manifest.json"}:
            raise ValueError("backup bundle has unexpected files")
        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict) or manifest.get("format") != 1:
            raise ValueError("unsupported backup bundle format")
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ValueError("backup manifest is malformed")
        database_bytes = archive.read("siro.db")
        config_bytes = archive.read("config.json")
    for name, value in (("siro.db", database_bytes), ("config.json", config_bytes)):
        if files.get(name) != hashlib.sha256(value).hexdigest():
            raise ValueError(f"backup hash mismatch: {name}")
    settings = SiroSettings.model_validate_json(config_bytes)
    with tempfile.NamedTemporaryFile(prefix="siro-restore-", suffix=".db", delete=False) as handle:
        handle.write(database_bytes)
        database_source = Path(handle.name)
    try:
        await store.restore_from(database_source)
        _atomic_write(config, settings.model_dump_json(indent=2) + "\n", 0o600)
    finally:
        database_source.unlink(missing_ok=True)


def _atomic_write(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.chmod(temporary, mode)
    temporary.replace(path)
