"""Exact dirty-source preservation and isolated patch reverse/reapply rehearsal."""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PRODUCTION = ("src/siro/core/evolution.py", "src/siro/cli.py")
TESTS = (
    "src/siro/services/tools/patch_verification.py",
    "src/siro/services/tools/patch_verification_runner.py",
    "tests/integration/test_isolated_patch_verification.py",
    "tests/integration/test_verify_patch_cli.py",
)
TEST_FILES = TESTS[2:]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preserve_and_rehearse() -> None:
    baseline = json.loads((OUT / "baseline.json").read_text())["hashes"]
    changed = [name for name, old in baseline.items() if digest(ROOT / name) != old]
    assert set(changed) == set(PRODUCTION), changed
    preservation = {
        "status": "PASS",
        "baseline_files": len(baseline),
        "changed_existing_files": changed,
        "new_files": list(TESTS),
        "private_files_read": False,
        "final_sha256": {name: digest(ROOT / name) for name in PRODUCTION + TESTS},
    }
    (OUT / "preservation.json").write_text(json.dumps(preservation, indent=2) + "\n")
    patch = []
    for name in PRODUCTION + TESTS:
        new = ROOT / name
        old = OUT / "before" / name
        after = OUT / "after" / name
        after.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(new, after)
        patch.append(f"diff --git a/{name} b/{name}\n")
        patch.extend(
            difflib.unified_diff(
                old.read_text().splitlines(keepends=True) if old.exists() else [],
                new.read_text().splitlines(keepends=True),
                fromfile=f"a/{name}" if old.exists() else "/dev/null",
                tofile=f"b/{name}",
            )
        )
    patch_file = OUT / "repair.patch"
    patch_file.write_text("".join(patch))
    commands: list[list[str]] = []
    with tempfile.TemporaryDirectory(prefix="siro-ri003-rollback-") as directory:
        isolated = Path(directory)
        for name in PRODUCTION + TESTS:
            target = isolated / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        for arguments in (["--reverse", "--check"], ["--reverse"], ["--check"], []):
            command = ["git", "apply", *arguments, str(patch_file)]
            subprocess.run(command, cwd=isolated, check=True, capture_output=True, timeout=15)
            commands.append(command[:-1] + ["repair.patch"])
            if arguments == ["--reverse"]:
                for name in PRODUCTION:
                    assert digest(isolated / name) == baseline[name], name
                assert all(not (isolated / name).exists() for name in TESTS)
        for name in PRODUCTION + TESTS:
            assert digest(isolated / name) == digest(ROOT / name), name
    result = {
        "status": "PASS",
        "scope": "isolated exact source patch, no runtime restart or database rollback",
        "production_files": list(PRODUCTION),
        "new_files": list(TESTS),
        "commands": commands,
        "patch_sha256": digest(patch_file),
        "baseline_restored": True,
        "candidate_reapplied": True,
        "temporary_directory_removed": not isolated.exists(),
    }
    (OUT / "rollback.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"preservation": preservation, "rollback": result}, indent=2))


def before_projection() -> None:
    """Run final new cases against only the two exact pre-card source files."""
    with tempfile.TemporaryDirectory(prefix="siro-ri003-before-") as directory:
        isolated = Path(directory)
        for path in (ROOT / "src").rglob("*.py"):
            if "__pycache__" in path.parts or path.relative_to(ROOT).as_posix() in TESTS[:2]:
                continue
            target = isolated / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        for name in PRODUCTION:
            target = isolated / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(OUT / "before" / name, target)
        for name in TEST_FILES:
            target = isolated / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        shutil.copy2(ROOT / "pyproject.toml", isolated / "pyproject.toml")
        # No credentials/configuration or private project data copied or inherited.
        import os

        environment = {
            "PATH": os.defpath,
            "PYTHONPATH": str(isolated / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        proof = subprocess.run(
            [str(ROOT / ".venv/bin/python"), "-c",
             "import siro.services.tools.orchestrator as m; print(m.__file__)"],
            cwd=isolated, env=environment, capture_output=True, text=True, check=True, timeout=15,
        )
        assert str(isolated / "src") in proof.stdout
        command = [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", *TEST_FILES]
        completed = subprocess.run(
            command, cwd=isolated, env=environment, capture_output=True, text=True, timeout=60,
        )
        (OUT / "complete-tests-before-final.log").write_text(completed.stdout + completed.stderr)
        result = {
            "scope": "final new cases against exact two pre-card dirty sources",
            "returncode": completed.returncode,
            "isolated_import_confirmed": True,
            "original_source_hashes_match": {
                name: digest(isolated / name) == json.loads(
                    (OUT / "baseline.json").read_text())["hashes"][name]
                for name in PRODUCTION
            },
            "summary": completed.stdout.strip().splitlines()[-1],
            "private_configuration_copied": False,
        }
        assert completed.returncode == 1, result
        assert all(result["original_source_hashes_match"].values())
        (OUT / "complete-tests-before-final.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["before"]:
        before_projection()
    else:
        preserve_and_rehearse()
