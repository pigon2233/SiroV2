"""Exact eight-path source-only rollback; never touches live releases or private data."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
BASELINE = "5c67c6f78f36833e526626b2d3481654bd823165"
CHANGED = (
    "runtime/siro-runtime/src/linux.rs",
    "src/siro/core/cognition.py",
    "src/siro/persistence/goals.py",
    "src/siro/services/presentation/gateway.py",
    "src/siro/services/presentation/static/index.html",
)
ADDED = (
    "src/siro/core/goal_tasks.py",
    "src/siro/persistence/migrations/014_goal_tasks.sql",
    "src/siro/services/agent/goal_tasks.py",
)
SCOPE = (*CHANGED, *ADDED)
NEW_TESTS = (
    "tests/integration/test_goal_task_api.py",
    "tests/integration/test_goal_task_loop.py",
    "tests/integration/test_frontend_goal_tasks.py",
    "tests/integration/test_goal_startup_isolation.py",
)
ARCHIVE_PATHS = (
    "src",
    "runtime/siro-runtime",
    "tests",
    "scripts",
    ".github",
    "pyproject.toml",
    ".python-version",
    "uv.lock",
)
STEPS: list[dict[str, object]] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def run(name: str, arguments: list[str], project: Path, env: dict[str, str]) -> None:
    started = time.monotonic()
    completed = subprocess.run(
        arguments,
        cwd=project,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
        start_new_session=True,
    )
    (EVIDENCE / f"{name}.log").write_bytes(completed.stdout)
    STEPS.append(
        {
            "name": name,
            "arguments": arguments,
            "exit_code": completed.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "child_joined": True,
        }
    )
    print(f"{name}: EXIT {completed.returncode}", flush=True)
    assert completed.returncode == 0, name


def main() -> None:
    baseline_paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASELINE, "--", *ARCHIVE_PATHS],
        cwd=ROOT,
        text=True,
    ).splitlines()
    protected_paths = sorted(set((*baseline_paths, *SCOPE, *NEW_TESTS)))
    protected_before = {path: sha(ROOT / path) for path in protected_paths}
    source_patch = subprocess.check_output(
        ["git", "diff", "--binary", BASELINE, "--", *CHANGED], cwd=ROOT
    )
    for path in ADDED:
        addition = subprocess.run(
            ["git", "diff", "--no-index", "--binary", "--", os.devnull, path],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        assert addition.returncode == 1 and not addition.stderr
        source_patch += addition.stdout
    patch_paths = re.findall(rb"^diff --git a/(.+) b/(.+)$", source_patch, flags=re.MULTILINE)
    assert len(patch_paths) == 8
    assert all(left == right for left, right in patch_paths)
    assert {left.decode() for left, _ in patch_paths} == set(SCOPE)
    patch_path = EVIDENCE / "production-eight-paths.patch"
    patch_path.write_bytes(source_patch)

    result: dict[str, object] = {
        "status": "RUNNING",
        "baseline_commit": BASELINE,
        "mode": "owned public source archive; real git apply reverse/reapply; synthetic SQLite",
        "production_paths": list(SCOPE),
        "patch_sha256": sha(patch_path),
        "steps": STEPS,
        "production_source_rollback_executed": False,
        "production_deployment_release_receipt_or_key_operation": False,
        "private_runtime_data_read": False,
        "source_copy_commit_created": False,
        "rollback_policy": (
            "Disable SIRO_GOAL_TASKS_ENABLED=0 and drain/join the caller first. Reverse only "
            "the eight new source integrations. Preserve schema14 task_json/history/latest data. "
            "Never SQL-downmigrate, DROP column, restore an old database or widen/resign a "
            "schema13-only release receipt. This source proof is not signed-release authorization."
        ),
    }
    temporary_root: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="g57r-") as temporary:
            temporary_root = Path(temporary)
            project = temporary_root / "public-source"
            project.mkdir()
            archive = subprocess.check_output(
                ["git", "archive", "--format=tar", BASELINE, "--", *ARCHIVE_PATHS], cwd=ROOT
            )
            with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
                bundle.extractall(project, filter="data")
            baseline_tree = hashes(project)
            for path in SCOPE:
                target = project / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, target)
            before = hashes(project)
            assert set(before) - set(baseline_tree) == set(ADDED)
            assert {path for path in baseline_tree if before[path] != baseline_tree[path]} == set(
                CHANGED
            )
            fixture = temporary_root / "synthetic-fixture"
            workspace = fixture / "workspace"
            workspace.mkdir(parents=True)
            (workspace / "checklist.md").write_text(
                "# Synthetic rollback checklist\n- [ ] retain newest task evidence\n"
                "TODO: preserve additive schema14\nFIXME: never restore an old database\n",
                encoding="utf-8",
            )
            env = {
                "PATH": os.defpath,
                "PYTHONPATH": str(project / "src"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "LANG": "C.UTF-8",
                "SIRO_GOAL_TASKS_ENABLED": "1",
            }
            helper = str(EVIDENCE / "database-probe.py")
            child = [str(ROOT / ".venv/bin/python"), "-B", helper]
            child_arguments = [str(project), str(fixture), str(EVIDENCE)]
            run("database-initialize", [*child, "initialize", *child_arguments], project, env)
            initialized = json.loads((EVIDENCE / "database-initialize.json").read_text())
            assert initialized["withdrawal"]["feature_setting_before_source_reverse"] == "0"
            assert initialized["withdrawal"]["asyncio_children_joined"]
            env["SIRO_GOAL_TASKS_ENABLED"] = "0"
            run(
                "reverse-check",
                ["git", "apply", "--reverse", "--check", str(patch_path)],
                project,
                env,
            )
            run("reverse-apply", ["git", "apply", "--reverse", str(patch_path)], project, env)
            reversed_tree = hashes(project)
            assert reversed_tree == baseline_tree
            run("database-reversed", [*child, "reversed", *child_arguments], project, env)
            run("reapply-check", ["git", "apply", "--check", str(patch_path)], project, env)
            run("reapply-apply", ["git", "apply", str(patch_path)], project, env)
            reapplied = hashes(project)
            assert reapplied == before
            run("database-reapplied", [*child, "reapplied", *child_arguments], project, env)
            assert hashes(project) == before
            result.update(
                status="PASS",
                temporary_root=str(temporary_root),
                source_hashes={
                    "before": before,
                    "baseline": baseline_tree,
                    "reversed": reversed_tree,
                    "reapplied": reapplied,
                },
                exact_reverse_changed_paths=sorted(
                    path for path in before if reversed_tree.get(path) != before[path]
                ),
                existing_public_files_preserved_during_reverse=len(before) - len(SCOPE),
                original_python_test_helpers_preserved=sum(
                    path.startswith("tests/") and path.endswith(".py") for path in baseline_tree
                ),
                old_migration_files_preserved=sum(
                    path.startswith("src/siro/persistence/migrations/") and path.endswith(".sql")
                    for path in baseline_tree
                ),
                source_reversal_matches_baseline=True,
                reapply_restores_exact_candidate_tree=True,
                database_phases=["initialize", "reversed", "reapplied"],
                database_sql_dump_unchanged=True,
                schema14_task_json_and_latest_history_preserved=True,
                signed_schema13_release_gate_evidence="../api/REPORT.md and final API receipt",
                source_proof_is_signed_release_authorization=False,
                owned_subprocesses_joined=all(step["child_joined"] for step in STEPS),
            )
    except BaseException as error:
        result.update(status="FAIL", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        result["owned_temporary_root_removed"] = (
            temporary_root is not None and not temporary_root.exists()
        )
        protected_after = {path: sha(ROOT / path) for path in protected_paths}
        result["workspace_protected_files"] = len(protected_paths)
        result["workspace_original_and_new_source_tests_preserved"] = (
            protected_after == protected_before
        )
        result["workspace_protected_before_sha256"] = protected_before
        result["workspace_protected_after_sha256"] = protected_after
        (EVIDENCE / "rollback-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    assert result["owned_temporary_root_removed"]
    assert result["workspace_original_and_new_source_tests_preserved"]
    print("SOURCE-ONLY ROLLBACK PASS; schema14/latest data preserved; owned children/temp cleaned")


if __name__ == "__main__":
    main()
