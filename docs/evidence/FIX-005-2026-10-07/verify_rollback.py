"""Exercise FIX-005 source rollback in an isolated, synthetic-data checkout.

This is source compatibility evidence, not a deployed-service or GPU rollback.
The copy uses an explicit project-source allowlist. No original data directory,
environment file, database, model, or voice recording enters the sandbox.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
TRACKED = [
    "scripts/qwen_tts_worker.py",
    "src/siro/services/audio/tts.py",
    "src/siro/services/presentation/gateway.py",
    "src/siro/services/presentation/static/index.html",
    "tests/integration/test_frontend_companion.py",
    "tests/integration/test_frontend_speech_cancel.py",
    "tests/integration/test_qwen_lifecycle.py",
]
ADDED = [
    "tests/test_qwen_worker_completion.py",
    "tests/integration/test_speech_plan.py",
    "tests/integration/test_frontend_speech_queue.py",
    "tests/integration/test_speech_completion_edges.py",
]
REGRESSION = [
    "tests/contract/test_model_adapters.py",
    "tests/integration/test_provider_completion.py",
    "tests/integration/test_session_tokens.py",
    "tests/integration/test_frontend_session.py",
    "tests/integration/test_frontend_control.py",
    "tests/integration/test_frontend_companion.py",
    "tests/integration/test_frontend_speech_cancel.py",
    "tests/integration/test_qwen_lifecycle.py",
    "tests/contract/test_audio_protocol.py",
    "tests/test_audio_pipeline.py",
    "tests/integration/test_gateway.py",
    "tests/integration/test_integrated_companion.py",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_public_source(source: Path, destination: Path) -> None:
    """Reject symlinks and copy only source/static files, not local runtime data."""
    allowed = {".py", ".html", ".js", ".mjs", ".json", ".sql", ".css", ".toml"}
    for item in source.rglob("*"):
        if "__pycache__" in item.parts:
            continue
        if item.is_symlink():
            raise AssertionError(f"source allowlist contains a symlink: {item.relative_to(ROOT)}")
        if not item.is_file() or item.suffix not in allowed:
            continue
        target = destination / item.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item, target)


def main() -> None:
    started = time.monotonic()
    version = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    source_hashes = {name: digest(ROOT / name) for name in TRACKED + ADDED}
    baseline_hashes: dict[str, str] = {}
    for card in ("FIX-003", "FIX-004"):
        record = json.loads((EVIDENCE.parent / f"{card}-2026-10-07/rollback.json").read_text())
        baseline_hashes.update(record["source_sha256"])

    with tempfile.TemporaryDirectory(prefix="siro-fix005-source-rollback-") as directory:
        isolated = Path(directory)

        def git(*args: str) -> bytes:
            return subprocess.run(
                ["git", *args], cwd=isolated, check=True, capture_output=True
            ).stdout

        git("init", "-q")
        copy_public_source(ROOT / "src", isolated / "src")
        copy_public_source(ROOT / "scripts", isolated / "scripts")
        copy_public_source(ROOT / "tests", isolated / "tests")
        shutil.copyfile(ROOT / "pyproject.toml", isolated / "pyproject.toml")
        for name in TRACKED:
            destination = isolated / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(EVIDENCE / "before-source" / name, destination)
        for name in ADDED:
            (isolated / name).unlink()
        assert not (isolated / ".siro-data").exists()
        assert not list(isolated.rglob("*.db"))
        assert not list(isolated.rglob("*.wav"))
        assert not list(isolated.rglob(".env*"))
        git("add", *TRACKED)
        for name in TRACKED + ADDED:
            destination = isolated / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
            assert digest(destination) == source_hashes[name]
        git("add", "-N", *ADDED)
        patch = git("diff", "--binary", "--", *TRACKED, *ADDED)
        patch_path = EVIDENCE / "source.patch"
        patch_path.write_bytes(patch)
        git("apply", "--reverse", "--check", str(patch_path))
        git("apply", "--reverse", str(patch_path))
        assert all(
            (isolated / name).read_bytes() == (EVIDENCE / "before-source" / name).read_bytes()
            for name in TRACKED
        )
        assert all(not (isolated / name).exists() for name in ADDED)
        assert all(
            digest(isolated / name) == expected for name, expected in baseline_hashes.items()
        )

        # Exclude provider credentials and runtime configuration inherited from the host.
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SIRO_")
            and not any(word in key.upper() for word in ("TOKEN", "SECRET", "API_KEY"))
            and key not in {"PYTHONPATH", "PYTHONHOME"}
        }
        environment["PYTHONPATH"] = str(isolated / "src")
        environment["SIRO_DATA_DIR"] = str(isolated / "synthetic-runtime")
        environment["PYTEST_ADDOPTS"] = ""
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        source_check = subprocess.run(
            [
                sys.executable,
                "-c",
                "import pathlib,siro.services.presentation.gateway as g; "
                "assert pathlib.Path(g.__file__).is_relative_to(pathlib.Path.cwd())",
            ],
            cwd=isolated,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        assert source_check.returncode == 0
        blocked: list[str] = []
        network_available = True
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
        except PermissionError:
            network_available = False
            blocked = [
                "tests/contract/test_model_adapters.py::test_http_stream_cancellation_closes_stalled_request",
                "tests/integration/test_provider_completion.py (local TCP fixtures)",
            ]

        def run_tests(label: str, tests: list[str]) -> dict[str, object]:
            selected = tests.copy()
            command = [sys.executable, "-m", "pytest", "-q", "-m", "not real_provider"]
            if not network_available:
                selected.remove("tests/integration/test_provider_completion.py")
                command += ["-k", "not test_http_stream_cancellation_closes_stalled_request"]
            command += selected
            result = subprocess.run(
                command,
                cwd=isolated,
                env=environment,
                capture_output=True,
                text=True,
                timeout=180,
            )
            output = result.stdout + result.stderr
            (EVIDENCE / f"rollback-{label}.log").write_text(output)
            return {
                "command": command,
                "exit_code": result.returncode,
                "result": "PASS" if result.returncode == 0 else "FAIL",
                "log": f"rollback-{label}.log",
                "summary": next(
                    (line for line in reversed(output.splitlines()) if "passed" in line),
                    "see log",
                ),
            }

        baseline_tests = run_tests("pre005", REGRESSION)
        git("apply", "--check", str(patch_path))
        git("apply", str(patch_path))
        assert all(digest(isolated / name) == expected for name, expected in source_hashes.items())
        reapplied_tests = run_tests("reapplied005", REGRESSION + ADDED)
        unchanged = all(digest(ROOT / name) == expected for name, expected in source_hashes.items())
        result = {
            "date_timezone": "2026-10-08 Asia/Taipei",
            "commit": version,
            "dirty_worktree": True,
            "isolated_source_reverse_and_reapply": "PASS",
            "baseline": "FIX-003 and FIX-004 completed sources; all recorded baseline hashes match",
            "baseline_preserved_hashes": baseline_hashes,
            "tracked_restored": len(TRACKED),
            "added_removed": len(ADDED),
            "production_runtime_or_db_modified": False,
            "original_private_data_copied": False,
            "real_gpu_or_deployment_rollback": "NOT VERIFIED",
            "socket_fixtures": "RUN" if network_available else "BLOCKED_PERMISSION_NOT_RUN",
            "not_run": blocked,
            "pre005_regressions": baseline_tests,
            "reapplied005_regressions": reapplied_tests,
            "source_unchanged_during_probe": unchanged,
            "patch_sha256": hashlib.sha256(patch).hexdigest(),
            "source_sha256": source_hashes,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        passed = (
            baseline_tests["exit_code"] == 0 and reapplied_tests["exit_code"] == 0 and unchanged
        )
        result["overall_scope_result"] = "PASS" if passed else "FAIL_OR_STALE"
        (EVIDENCE / "rollback.json").write_text(json.dumps(result, indent=2) + "\n")
        if not passed:
            raise SystemExit("FAIL/STALE: see rollback.json and isolated regression logs")
        print("PASS: isolated FIX-005 source rollback/reapply and scoped regressions")
        if blocked:
            print("NOT RUN: socket fixtures blocked by environment; see rollback.json")


if __name__ == "__main__":
    main()
