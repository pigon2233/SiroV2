"""Static import-boundary checks that prevent a new central bridge."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_CORE_PREFIXES = (
    "siro.adapters",
    "siro.services",
    "siro.runtime",
)


def find_core_import_violations(core_root: Path) -> list[str]:
    """Return stable diagnostics for forbidden imports below a core directory."""

    violations: list[str] = []
    if not core_root.exists():
        return violations
    for path in sorted(core_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules.append(node.module)
            for module in modules:
                if module.startswith(FORBIDDEN_CORE_PREFIXES):
                    line_number = getattr(node, "lineno", 0)
                    violations.append(f"{path}:{line_number}: forbidden import {module}")
    return violations
