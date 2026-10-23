"""Run explicit pytest targets and write a conservative, content-free acceptance receipt."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def source_state(root: Path, git_executable: str = "git") -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.check_output([git_executable, *args], cwd=root, text=True).strip()

    status = git("status", "--porcelain", "--untracked-files=all")
    content = hashlib.sha256(
        subprocess.check_output([git_executable, "diff", "--binary", "HEAD", "--"], cwd=root)
    )
    untracked = subprocess.check_output(
        [git_executable, "ls-files", "--others", "--exclude-standard", "-z"], cwd=root
    )
    for name in sorted(untracked.split(b"\0")):
        if not name:
            continue
        path = root / os.fsdecode(name)
        content.update(name + b"\0")
        if path.is_symlink():
            content.update(os.fsencode(os.readlink(path)))
        else:
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    content.update(chunk)
        content.update(b"\0")
    return {
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(status),
        "status_sha256": hashlib.sha256(status.encode()).hexdigest(),
        "content_sha256": content.hexdigest(),
    }


def summarize(path: Path, returncode: int) -> tuple[str, dict[str, int]]:
    counts = dict.fromkeys(("passed", "failed", "errors", "skipped", "tests"), 0)
    try:
        tree = ET.parse(path)
        if tree.getroot().tag not in {"testsuites", "testsuite"}:
            return "ERROR", counts
        cases = list(tree.iter("testcase"))
        for case in cases:
            counts["tests"] += 1
            if case.find("failure") is not None:
                counts["failed"] += 1
            elif case.find("error") is not None:
                counts["errors"] += 1
            elif case.find("skipped") is not None:
                counts["skipped"] += 1
            else:
                counts["passed"] += 1
    except (OSError, ET.ParseError):
        return "ERROR", counts
    if returncode not in (0, 1, 5):
        return "ERROR", counts
    if returncode == 1 or counts["failed"] or counts["errors"]:
        return "FAIL", counts
    if not counts["tests"] or returncode == 5:
        return "NO_TESTS", counts
    if counts["skipped"]:
        return "PARTIAL", counts
    return "PASS", counts


def run(
    root: Path, targets: list[str], output: Path, level: str, git_executable: str = "git"
) -> int:
    # Restrict this entry point to test paths, not pytest options or arbitrary scripts.
    for target in targets:
        candidate = (root / target.split("::", 1)[0]).resolve()
        if not candidate.is_relative_to((root / "tests").resolve()) or not candidate.exists():
            raise ValueError("each target must be an existing path inside tests/")
        if candidate.is_file() and candidate.suffix != ".py":
            raise ValueError("test files must have the .py suffix")
    before = source_state(root, git_executable)
    # Never reuse an old report, including after a failed or interrupted previous run.
    output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(UTC).isoformat()
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="siro-acceptance-") as temporary:
        junit = Path(temporary) / "pytest.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            *targets,
            "-o",
            "addopts=-ra --strict-config --strict-markers",
            "-o",
            "xfail_strict=true",
            f"--junitxml={junit}",
        ]
        environment = os.environ.copy()
        environment.pop("PYTEST_ADDOPTS", None)
        environment["PYTHONPATH"] = str(root / "src")
        try:
            returncode = subprocess.run(command, cwd=root, env=environment, check=False).returncode
        except OSError:
            returncode = -1
        outcome, counts = summarize(junit, returncode)
        after = source_state(root, git_executable)
        if before != after:
            outcome = "SOURCE_CHANGED"
        receipt = {
            "schema_version": 1,
            "outcome": outcome,
            "scope": "selected pytest targets only; not product or acceptance-card completion",
            "profile": "selected-pytest",
            "git_executable": git_executable,
            "declared_evidence_level": level,
            "evidence_level_verified": False,
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(),
            "duration_seconds": round(time.monotonic() - start, 3),
            "source_before": before,
            "source_after": after,
            "environment": {
                "python": platform.python_version(),
                "pytest": importlib.metadata.version("pytest"),
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "cpu_count": os.cpu_count(),
            },
            "targets": targets,
            "command": command,
            "pytest_returncode": returncode,
            "counts": counts,
            "limitations": [
                "No raw output, testcase text, environment variables or JUnit payload retained.",
                "Hardware, providers, fixture provenance and manual gates need separate evidence.",
                "No timeout or retry; interruption may leave a directory without a receipt.",
                "Source status comparison cannot detect edits reverted during execution.",
            ],
        }
        # The private temporary XML can contain assertion data; only counts survive.
        destination = output / "receipt.json"
        staging = output / "receipt.json.tmp"
        staging.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        staging.replace(destination)
    print(f"{outcome}: {destination}")
    return 0 if outcome == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", help="explicit tests/ path, optionally with ::nodeid")
    parser.add_argument(
        "--output", type=Path, required=True, help="new directory; never overwritten"
    )
    parser.add_argument(
        "--level",
        choices=("L1", "L2", "L3"),
        required=True,
        help="operator declaration, not automatic certification",
    )
    parser.add_argument(
        "--git-executable", default="git", help="Git binary used for source evidence"
    )
    args = parser.parse_args()
    try:
        return run(ROOT, args.targets, args.output.resolve(), args.level, args.git_executable)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(
            f"Acceptance setup failed ({type(error).__name__}); no PASS receipt issued.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
