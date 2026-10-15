"""Run new cancellation-budget cases against an owned public source copy."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
PHASE = sys.argv[1]
assert PHASE in {"red", "green"}
BASELINE = "5c67c6f78f36833e526626b2d3481654bd823165"
TEST = "tests/integration/test_cancel_budget_reserve.py"
ORIGINAL_TEST = "tests/integration/test_execution_lifecycle.py"
ORCHESTRATOR = "src/siro/services/tools/orchestrator.py"
OVERLAYS = (
    "runtime/siro-runtime/src/linux.rs",
    "src/siro/core/cognition.py",
    "src/siro/core/goal_tasks.py",
    "src/siro/persistence/goals.py",
    "src/siro/persistence/migrations/014_goal_tasks.sql",
    "src/siro/services/agent/goal_tasks.py",
    "src/siro/services/presentation/gateway.py",
    "src/siro/services/presentation/static/index.html",
    ORCHESTRATOR,
    TEST,
)
UNCHANGED = (
    "src/siro/services/presentation/integrated.py",
    "src/siro/services/tools/execution.py",
    "src/siro/adapters/process_execution.py",
    "src/siro/services/agent/runs.py",
    "src/siro/core/conversation.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protected = (*OVERLAYS, ORIGINAL_TEST, *UNCHANGED)
    before = {path: sha(ROOT / path) for path in protected}
    baseline_orchestrator = subprocess.check_output(
        ["git", "show", f"{BASELINE}:{ORCHESTRATOR}"], cwd=ROOT
    )
    if PHASE == "red":
        assert (ROOT / ORCHESTRATOR).read_bytes() == baseline_orchestrator
    original_test = subprocess.check_output(
        ["git", "show", f"{BASELINE}:{ORIGINAL_TEST}"], cwd=ROOT
    )
    assert (ROOT / ORIGINAL_TEST).read_bytes() == original_test
    for path in UNCHANGED:
        baseline = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT)
        assert (ROOT / path).read_bytes() == baseline
    result: dict[str, object] = {
        "status": "RUNNING",
        "phase": PHASE,
        "baseline_public_commit": BASELINE,
        "new_test": TEST,
        "source_before": before,
        "source_overlay": list(OVERLAYS),
        "main_private_tree_scanned": False,
        "controlled_terminal_bookkeeping_seconds": 0.5,
        "controlled_contextual_cleanup_seconds": 4.2,
        "original_total_bound_seconds": 5,
        "old_assertions_modified": False,
        "full_suite_delay_root_cause_claimed": False,
        "unchanged_integrated_execution_backend_and_journal": list(UNCHANGED),
        "checks": [],
    }
    temporary_root: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="g58budget-") as temporary:
            temporary_root = Path(temporary)
            project = temporary_root / "public-source"
            project.mkdir()
            archive = subprocess.check_output(
                [
                    "git",
                    "archive",
                    "--format=tar",
                    BASELINE,
                    "--",
                    "src",
                    "tests",
                    "runtime/siro-runtime",
                    "pyproject.toml",
                ],
                cwd=ROOT,
            )
            with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
                bundle.extractall(project, filter="data")
            for path in OVERLAYS:
                target = project / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, target)
            assert (project / ORIGINAL_TEST).read_bytes() == original_test
            child_before = {path: sha(project / path) for path in protected}
            env = {
                "PATH": os.defpath,
                "PYTHONPATH": str(project / "src"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "LANG": "C.UTF-8",
                "TMPDIR": str(temporary_root),
                "SIRO_GOAL_TASKS_ENABLED": "0",
            }
            command = [str(ROOT / ".venv/bin/python"), "-B", "-m", "pytest", "-q", TEST]
            started = time.monotonic()
            completed = subprocess.run(
                command,
                cwd=project,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=60,
                check=False,
                start_new_session=True,
            )
            (EVIDENCE / f"{PHASE}-tests.log").write_bytes(completed.stdout)
            result.update(
                command=command,
                exit_code=completed.returncode,
                elapsed_seconds=round(time.monotonic() - started, 3),
                owned_subprocess_joined=True,
                owned_temporary_root=str(temporary_root),
                owned_source_before=child_before,
                owned_source_after={path: sha(project / path) for path in protected},
            )
            checks = result["checks"]
            assert isinstance(checks, list)
            checks.append(
                {
                    "name": f"{PHASE}-new-tests",
                    "command": command,
                    "exit_code": completed.returncode,
                }
            )
            assert result["owned_source_after"] == child_before
            if PHASE == "red":
                assert completed.returncode == 1
                assert b"1 failed, 1 passed" in completed.stdout
                assert (
                    b"test_arguments_only_cancel_reserves_terminal_bookkeeping" in completed.stdout
                )
                assert b"assert elapsed < 5" in completed.stdout
                result["status"] = "EXPECTED_RED"
            else:
                assert completed.returncode == 0 and b"2 passed" in completed.stdout

                def owned_command(
                    name: str, arguments: list[str], expected: int, summary: bytes | None = None
                ) -> None:
                    started = time.monotonic()
                    owned = subprocess.run(
                        arguments,
                        cwd=project,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=60,
                        check=False,
                        start_new_session=True,
                    )
                    (EVIDENCE / f"{name}.log").write_bytes(owned.stdout)
                    checks.append(
                        {
                            "name": name,
                            "command": arguments,
                            "exit_code": owned.returncode,
                            "elapsed_seconds": round(time.monotonic() - started, 3),
                            "child_joined": True,
                        }
                    )
                    assert owned.returncode == expected, name
                    if summary is not None:
                        assert summary in owned.stdout, name

                lifecycle = [
                    str(ROOT / ".venv/bin/python"),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    ORIGINAL_TEST,
                ]
                owned_command("original-lifecycle-tests", lifecycle, 0, b"25 passed")
                patch = subprocess.check_output(
                    ["git", "diff", "--binary", BASELINE, "--", ORCHESTRATOR], cwd=ROOT
                )
                assert patch.count(b"diff --git ") == 1
                assert patch.startswith(
                    b"diff --git a/src/siro/services/tools/orchestrator.py "
                    b"b/src/siro/services/tools/orchestrator.py\n"
                )
                patch_path = EVIDENCE / "orchestrator-repair.patch"
                patch_path.write_bytes(patch)
                owned_command(
                    "reverse-check", ["git", "apply", "--reverse", "--check", str(patch_path)], 0
                )
                owned_command("reverse-apply", ["git", "apply", "--reverse", str(patch_path)], 0)
                assert (project / ORCHESTRATOR).read_bytes() == baseline_orchestrator
                reversed_hashes = {path: sha(project / path) for path in protected}
                assert {
                    path for path in protected if reversed_hashes[path] != child_before[path]
                } == {ORCHESTRATOR}
                owned_command("reversed-new-tests", command, 1, b"1 failed, 1 passed")
                owned_command("reapply-check", ["git", "apply", "--check", str(patch_path)], 0)
                owned_command("reapply-apply", ["git", "apply", str(patch_path)], 0)
                assert {path: sha(project / path) for path in protected} == child_before
                owned_command("reapplied-new-tests", command, 0, b"2 passed")
                assert {path: sha(project / path) for path in protected} == child_before
                result.update(
                    leaf_patch_sha256=sha(patch_path),
                    leaf_reverse_baseline_sha256=hashlib.sha256(baseline_orchestrator).hexdigest(),
                    leaf_reapply_final_sha256=sha(project / ORCHESTRATOR),
                    reversed_source_hashes=reversed_hashes,
                    leaf_reverse_changed_paths=[ORCHESTRATOR],
                    final_new_tests="2 PASS",
                    original_lifecycle_tests="25 PASS",
                    source_reverse_new_tests="1 FAIL / 1 PASS",
                    source_reapply_new_tests="2 PASS",
                    original_backend_cleanup_timeout_seconds=4.5,
                    contextual_or_mixed_cleanup_timeout_seconds=4.75,
                    arguments_only_cleanup_timeout_seconds=4.0,
                )
                result["status"] = "PASS"
    except BaseException as error:
        result.update(status="FAIL", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        result["owned_temporary_root_removed"] = (
            temporary_root is not None and not temporary_root.exists()
        )
        result["source_after"] = {path: sha(ROOT / path) for path in protected}
        result["workspace_source_and_original_test_preserved"] = result["source_after"] == before
        (EVIDENCE / f"{PHASE}-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    assert result["owned_temporary_root_removed"]
    assert result["workspace_source_and_original_test_preserved"]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
