"""Disposable, source-only reverse/reapply proof; never rolls back live releases/data."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
PRODUCTION = Path("src/siro/core/releases.py")
IDENTITY_TEST = Path("tests/integration/test_release_tree_identity.py")
FINAL_SHA256 = "c959036b436e817d96db14a971b430c02b2b8c096dee00586e3cdf98de36003e"
STEPS: list[dict[str, object]] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(project: Path) -> dict[str, str]:
    return {
        str(path.relative_to(project)): sha(path)
        for path in sorted((project / "src").rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def run(name: str, arguments: list[str], project: Path, env: dict[str, str], expected: int) -> str:
    completed = subprocess.run(
        arguments,
        cwd=project,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )
    (EVIDENCE / f"rollback-{name}.log").write_text(completed.stdout, encoding="utf-8")
    STEPS.append({"name": name, "arguments": arguments, "exit_code": completed.returncode})
    print(name, "exit", completed.returncode, flush=True)
    assert completed.returncode == expected, name
    return completed.stdout


def main() -> None:
    baseline = json.loads((EVIDENCE / "baseline.json").read_text())["files"][str(PRODUCTION)]
    assert sha(ROOT / PRODUCTION) == FINAL_SHA256
    production_before = source_hashes(ROOT)
    patch = subprocess.run(
        ["git", "diff", "--binary", "--", str(PRODUCTION)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert patch.startswith("diff --git a/src/siro/core/releases.py b/src/siro/core/releases.py\n")
    assert patch.count("diff --git ") == 1
    patch_path = EVIDENCE / "production-repair.patch"
    patch_path.write_text(patch, encoding="utf-8")
    result: dict[str, object] = {
        "mode": "owned disposable source copy; real git reverse/reapply and synthetic tests",
        "production_rollback_executed": False,
        "baseline_sha256": baseline,
        "final_sha256": FINAL_SHA256,
        "steps": STEPS,
        "rollback_policy": (
            "Withdraw release execution first. Source reversal is not approval to execute v1, "
            "resign receipts, restore DB backups, or deploy."
        ),
    }
    temporary_root: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="siro-fix020-source-rollback-") as temporary:
            temporary_root = Path(temporary)
            project = temporary_root / "project"
            project.mkdir()
            shutil.copytree(
                ROOT / "src",
                project / "src",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            target_test = project / IDENTITY_TEST
            target_test.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / IDENTITY_TEST, target_test)
            shutil.copyfile(ROOT / "pyproject.toml", project / "pyproject.toml")
            before = source_hashes(project)
            assert before == production_before
            env = {
                "PATH": os.defpath,
                "PYTHONPATH": str(project / "src"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "LANG": "C.UTF-8",
            }
            reverse = ["git", "apply", "--reverse"]
            run("reverse-check", [*reverse, "--check", str(patch_path)], project, env, 0)
            run("reverse-apply", [*reverse, str(patch_path)], project, env, 0)
            assert sha(project / PRODUCTION) == baseline
            reversed_tree = source_hashes(project)
            changed = [path for path in before if before[path] != reversed_tree[path]]
            assert changed == [str(PRODUCTION)]
            result["reverse_changed_paths"] = changed
            result["reversed_sha256"] = sha(project / PRODUCTION)
            tests = [sys.executable, "-m", "pytest", "-q", str(IDENTITY_TEST)]
            red = run("identity-reversed", tests, project, env, 1)
            assert "15 failed" in red
            run("reapply-check", ["git", "apply", "--check", str(patch_path)], project, env, 0)
            run("reapply-apply", ["git", "apply", str(patch_path)], project, env, 0)
            assert sha(project / PRODUCTION) == FINAL_SHA256
            assert source_hashes(project) == before
            green = run("identity-reapplied", tests, project, env, 0)
            assert "15 passed" in green
            result["reapplied_sha256"] = sha(project / PRODUCTION)
            result["source_files_preserved"] = len(before) - 1
            result["new_identity_tests"] = {"reversed": "15 FAIL", "reapplied": "15 PASS"}
            result["status"] = "PASS"
    except BaseException as error:
        result["status"] = "FAIL"
        result["error_type"] = type(error).__name__
        raise
    finally:
        result["owned_temporary_root_removed"] = (
            temporary_root is not None and not temporary_root.exists()
        )
        result["workspace_source_unchanged"] = source_hashes(ROOT) == production_before
        (EVIDENCE / "rollback-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
