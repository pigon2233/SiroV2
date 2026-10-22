"""Owner-editable desktop pet settings, read by scripts/start-desktop at the next launch."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS: dict[str, object] = {"gpu": True, "position": None}
_LIMIT = 20000


def _clean(raw: object) -> dict[str, object]:
    data = raw if isinstance(raw, dict) else {}
    gpu = data.get("gpu")
    position = data.get("position")
    if isinstance(position, dict):
        x, y = position.get("x"), position.get("y")
        ok = all(
            isinstance(v, int) and not isinstance(v, bool) and abs(v) <= _LIMIT for v in (x, y)
        )
        position = {"x": x, "y": y} if ok else None
    else:
        position = None
    return {"gpu": gpu if isinstance(gpu, bool) else True, "position": position}


def load_desktop_settings(path: Path) -> dict[str, object]:
    try:
        return _clean(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save_desktop_settings(path: Path, settings: dict[str, object]) -> dict[str, object]:
    cleaned = _clean(settings)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    return cleaned
