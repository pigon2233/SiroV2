"""Verify this card's source rollback in an isolated directory, preserving FIX-003."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
TRACKED = [
    "src/siro/services/presentation/gateway.py",
    "src/siro/services/presentation/static/index.html",
    "tests/integration/test_frontend_companion.py",
    "tests/integration/test_frontend_speech_cancel.py",
    "tests/integration/test_run_journal.py",
    "tests/integration/test_agent_batches.py",
]
ADDED = [
    "tests/integration/test_session_tokens.py",
    "tests/integration/test_frontend_session.py",
    "tests/integration/test_frontend_control.py",
]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="siro-fix004-rollback-") as directory:
        isolated = Path(directory)

        def git(*args: str) -> bytes:
            return subprocess.run(
                ["git", *args], cwd=isolated, check=True, capture_output=True
            ).stdout

        git("init", "-q")
        for name in TRACKED:
            destination = isolated / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(EVIDENCE / "before-source" / name, destination)
        git("add", *TRACKED)
        for name in TRACKED + ADDED:
            destination = isolated / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        git("add", "-N", *ADDED)
        patch = git("diff", "--binary", "--", *TRACKED, *ADDED)
        (EVIDENCE / "source.patch").write_bytes(patch)
        git("apply", "--reverse", "--check", str(EVIDENCE / "source.patch"))
        git("apply", "--reverse", str(EVIDENCE / "source.patch"))
        assert all(
            (isolated / name).read_bytes() == (EVIDENCE / "before-source" / name).read_bytes()
            for name in TRACKED
        )
        assert all(not (isolated / name).exists() for name in ADDED)
        git("apply", "--check", str(EVIDENCE / "source.patch"))
        git("apply", str(EVIDENCE / "source.patch"))
        assert all(
            (isolated / name).read_bytes() == (ROOT / name).read_bytes() for name in TRACKED + ADDED
        )
        result = {
            "isolated_source_reverse_and_reapply": "PASS",
            "baseline": "FIX-003 completed sources plus pre-FIX-004 gateway/tests",
            "tracked_restored": len(TRACKED),
            "added_removed": len(ADDED),
            "production_runtime_or_db_modified": False,
            "patch_sha256": hashlib.sha256(patch).hexdigest(),
            "source_sha256": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in TRACKED + ADDED
            },
        }
        (EVIDENCE / "rollback.json").write_text(json.dumps(result, indent=2) + "\n")
        print("PASS: isolated source reverse/reapply; FIX-003 baseline preserved")


if __name__ == "__main__":
    main()
