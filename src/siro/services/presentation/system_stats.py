"""Read-only host load for the monitor page; display only, never sent to the model."""

from __future__ import annotations

import platform
from datetime import UTC, datetime
from pathlib import Path

import psutil  # type: ignore[import-untyped]

# interval=None measures since the previous call; the first call returns a meaningless 0.0.
psutil.cpu_percent(interval=None)


def _disk(path: Path) -> dict[str, object]:
    usage = psutil.disk_usage(str(path))
    return {"path": str(path), "total": usage.total, "used": usage.used, "percent": usage.percent}


def read_system_stats(data_dir: Path | None = None) -> dict[str, object]:
    """Blocking psutil calls: run through asyncio.to_thread."""
    memory = psutil.virtual_memory()
    disks = [_disk(Path(Path.cwd().anchor))]
    if data_dir is not None and data_dir.exists():
        extra = _disk(data_dir)
        if extra["total"] != disks[0]["total"] or extra["used"] != disks[0]["used"]:
            disks.append(extra)
    release = platform.release()
    return {
        "observed_at": datetime.now(UTC).isoformat(),
        # Under WSL2 these are the Linux VM's numbers, not the whole Windows host.
        "environment": "wsl" if "microsoft" in release.lower() else platform.system().lower(),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_count": psutil.cpu_count(),
        "memory": {"total": memory.total, "used": memory.used, "percent": memory.percent},
        "disks": disks,
    }
