#!/usr/bin/env python3
"""Read-only CLI preflight; OFF unless SIRO_COMPUTER_REQUIRE_CHECKOUT=1. Never sends input."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CHECK_ENV = "SIRO_COMPUTER_REQUIRE_CHECKOUT"


def enabled(env: Mapping[str, str], config: Path | None) -> bool:
    value = env.get(CHECK_ENV)
    if value is None and config is not None:
        try:
            for line in config.read_text(encoding="utf-8").splitlines():
                key, sep, entry = line.strip().removeprefix("export ").partition("=")
                if sep and key.strip() == CHECK_ENV:
                    value = entry.strip().strip("\"'")
        except OSError:
            pass
    return value == "1"


def validate(status: Any, expected: Path) -> str:
    info = status.get("runtime") if isinstance(status, dict) else None
    if not isinstance(info, dict) or info.get("version") != 1:
        return (
            "backend_checkout_unverified: old/missing runtime identity; restart intended backend "
            "with SIRO_COMPUTER_RUNTIME_DIAGNOSTICS=1"
        )
    source = info.get("source_root")
    module = info.get("decision_module")
    if not isinstance(source, str) or not isinstance(module, str):
        return "backend_checkout_unverified: missing source paths"
    root = expected.resolve()
    if (
        Path(source).resolve() != root
        or Path(module).resolve() != root / "src/siro/services/computer_use/decision.py"
    ):
        return "backend_checkout_mismatch: serving backend is not this checkout; no run was sent"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if not enabled(os.environ, args.config):
        return 0
    try:
        status = json.load(sys.stdin)
    except ValueError:
        print("backend_checkout_unverified: invalid status JSON", file=sys.stderr)
        return 2
    error = validate(status, args.expected)
    if error:
        print(error, file=sys.stderr)
        return 2
    print("Backend checkout verified: " + str(args.expected), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
