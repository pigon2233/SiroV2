"""Trusted fixed-entrypoint runner copied outside the readonly candidate package."""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast


def restrict(*, memory_mb: int = 256, cpu_seconds: int = 5) -> None:
    if __package__:
        from siro.adapters.python_restrictions import restrict as apply
    else:
        # -I excludes the script directory; candidate imports are still unavailable here.
        sys.path.insert(0, "/trusted")
        try:
            apply = cast(
                Callable[..., None], importlib.import_module("python_restrictions").restrict
            )
        finally:
            sys.path.pop(0)
    apply(memory_mb=memory_mb, cpu_seconds=cpu_seconds)


def _invalid_constant(value: str) -> None:
    raise ValueError("nonfinite JSON value")


def _read_object(path: Path, limit: int) -> dict[str, object]:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("trusted JSON exceeds its byte limit")
    value = json.loads(data.decode("utf-8"), parse_constant=_invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("trusted JSON must be an object")
    return value


def main() -> int:
    try:
        limits = _read_object(Path("/trusted/limits.json"), 4096)
        if set(limits) != {"memory_mb", "cpu_seconds"}:
            raise ValueError("unsupported limits")
        memory_mb, cpu_seconds = limits["memory_mb"], limits["cpu_seconds"]
        if type(memory_mb) is not int or type(cpu_seconds) is not int:
            raise ValueError("limits must be integers")
        restrict(memory_mb=memory_mb, cpu_seconds=cpu_seconds)
    except Exception:
        print("unsupported_sandbox", flush=True)
        return 78
    if sys.argv[1:] == ["--probe"]:
        print("SIRO_SKILL_PROFILE_READY_V1", flush=True)
        return 0
    if sys.argv[1:]:
        return 78
    request = _read_object(Path("/trusted/request.json"), 65536)
    # Only this fixed path enters imports after irreversible limits and syscall restrictions.
    sys.dont_write_bytecode = True
    sys.path.insert(0, "/candidate")
    function = cast(Callable[[dict[str, object]], object], importlib.import_module("plugin").run)
    response = function(request)
    if not isinstance(response, dict):
        raise ValueError("skill output must be an object")
    sys.stdout.write(
        json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
