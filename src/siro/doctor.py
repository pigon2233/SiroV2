"""Read-only environment diagnostics for SIRO."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One doctor capability result."""

    name: str
    state: str
    detail: str
    required_for: str


def _data_dir(environment: dict[str, str]) -> Path:
    configured = environment.get("SIRO_DATA_DIR")
    if configured:
        return Path(configured)
    base = environment.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "siro"
    return Path.home() / ".local" / "share" / "siro"


def _command_check(name: str, required_for: str) -> CheckResult:
    location = shutil.which(name)
    if location is None:
        return CheckResult(name, "unavailable", "not found on PATH", required_for)
    return CheckResult(name, "available", location, required_for)


def _nvidia_check() -> CheckResult:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return CheckResult("nvidia", "unavailable", "nvidia-smi not found", "local-ai")
    try:
        result = subprocess.run(
            [executable, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return CheckResult("nvidia", "unavailable", type(error).__name__, "local-ai")
    if result.returncode != 0:
        return CheckResult("nvidia", "unavailable", "driver/runtime not ready", "local-ai")
    return CheckResult("nvidia", "available", result.stdout.strip(), "local-ai")


def _config_check(environment: dict[str, str]) -> CheckResult:
    from siro.config import load_settings

    configured = environment.get("SIRO_CONFIG")
    path = Path(configured) if configured else Path.home() / ".config/siro/config.json"
    if not path.is_file():
        return CheckResult("config", "unavailable", str(path), "companion")
    try:
        load_settings(path)
    except (OSError, ValueError) as error:
        return CheckResult("config", "unavailable", type(error).__name__, "companion")
    return CheckResult("config", "available", str(path), "companion")


def _gateway_check(environment: dict[str, str]) -> CheckResult:
    port = environment.get("SIRO_GATEWAY_PORT", "8000")
    url = f"http://127.0.0.1:{port}/health/ready"
    try:
        with urllib.request.urlopen(url, timeout=0.5) as response:
            if response.status == 200:
                return CheckResult("gateway", "available", url, "companion")
    except (OSError, ValueError):
        pass
    return CheckResult("gateway", "unavailable", url, "companion")


def collect_checks(environment: dict[str, str] | None = None) -> list[CheckResult]:
    """Collect diagnostics without changing the host."""

    selected_environment = dict(os.environ if environment is None else environment)
    data_dir = _data_dir(selected_environment)
    data_parent = data_dir.parent
    writable = os.access(data_parent, os.W_OK) if data_parent.exists() else False
    results = [
        CheckResult("python", "available", sys.version.split()[0], "minimal"),
        CheckResult(
            "data-directory",
            "available" if writable else "unavailable",
            str(data_dir),
            "minimal",
        ),
        _config_check(selected_environment),
        _gateway_check(selected_environment),
        _command_check("wpctl", "companion audio"),
        _command_check("docker", "broker integration tests"),
        _command_check("rustc", "runtime"),
        _command_check("node", "presentation UI"),
        _nvidia_check(),
    ]
    return results


def checks_as_dicts(checks: list[CheckResult]) -> list[dict[str, str]]:
    """Serialize checks for JSON output."""

    return [asdict(check) for check in checks]
