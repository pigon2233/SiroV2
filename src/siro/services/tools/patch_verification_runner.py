"""Trusted single-process runner mounted outside the candidate source tree."""

from __future__ import annotations

import importlib
import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import cast


def restrict() -> None:
    if __package__:
        from siro.adapters.python_restrictions import restrict as apply
    else:
        # Isolated Python excludes the script directory; load only the readonly trusted copy.
        sys.path.insert(0, "/trusted")
        try:
            apply = cast(
                Callable[..., None], importlib.import_module("python_restrictions").restrict
            )
        finally:
            sys.path.pop(0)
    apply()


def main() -> int:
    try:
        restrict()
    except Exception:
        print("unsupported_sandbox", flush=True)
        return 78
    if sys.argv[1:] == ["--probe"]:
        print("SIRO_PATCH_PROFILE_READY_V1", flush=True)
        return 0
    if sys.argv[1:]:
        return 78
    # Candidate paths enter imports only after irreversible OS restrictions.
    sys.dont_write_bytecode = True
    sys.path[:0] = ["/candidate/src", "/candidate"]
    for root in (Path("/candidate/src"), Path("/candidate/tests")):
        for path in sorted(root.rglob("*.py")):
            compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    suite = unittest.defaultTestLoader.discover("/candidate/tests", pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.testsRun > 0 and result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
