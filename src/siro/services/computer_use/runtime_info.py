"""Optional non-secret identity of the ACTUAL loaded decision module, not launcher's cwd."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

RUNTIME_ENV = "SIRO_COMPUTER_RUNTIME_DIAGNOSTICS"


def runtime_info(decider: object, env: Mapping[str, str] | None = None) -> dict[str, Any] | None:
    values = os.environ if env is None else env
    if values.get(RUNTIME_ENV, "0") != "1":
        return None
    from siro.services.computer_use import decision

    chain = []
    seen: set[int] = set()
    current = decider
    for _ in range(8):
        if id(current) in seen:
            break
        seen.add(id(current))
        chain.append(type(current).__name__)
        inner = getattr(current, "inner", getattr(current, "_inner", None))
        if inner is None:
            break
        current = inner
    return {
        "version": 1,
        "pid": os.getpid(),
        "source_root": str(Path(decision.__file__).resolve().parents[4]),
        "decision_module": str(Path(decision.__file__).resolve()),
        "decider_chain": chain,
    }
