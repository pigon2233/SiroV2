"""RI-004 exact source preservation and disposable reverse/reapply rehearsal.

Run ``final`` only after the task owner freezes the six scoped source files.
The optional ``before`` projection deliberately omits the new service: its
collection failure is recorded as a missing-interface RED result, never as
executed test failures or as a functional verification result.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
EXISTING = (
    "src/siro/services/presentation/gateway.py",
    "src/siro/services/presentation/static/index.html",
)
NEW = (
    "src/siro/services/tools/skill_candidates.py",
    "tests/integration/test_skill_candidates.py",
    "tests/integration/test_skill_candidate_product.py",
    "tests/integration/test_frontend_skill_candidate.py",
)
SCOPE = EXISTING + NEW
TEST_FILES = NEW[1:]
TEST_HELPERS = (
    "tests/integration/test_frontend_control.py",
    "tests/integration/test_isolated_patch_verification.py",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return sha256(path.read_bytes())


def baseline_hashes() -> dict[str, str]:
    hashes: dict[str, str] = json.loads((OUT / "baseline.json").read_text())["hashes"]
    assert len(hashes) == 248, len(hashes)
    assert all(name in hashes for name in EXISTING)
    assert all(name not in hashes for name in NEW)
    return hashes


def changed_existing(hashes: dict[str, str]) -> list[str]:
    changed = [name for name, old in hashes.items() if digest(ROOT / name) != old]
    assert set(changed) == set(EXISTING), changed
    return changed


def save_json(name: str, data: dict[str, object]) -> None:
    (OUT / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def preserve_and_rehearse() -> None:
    hashes = baseline_hashes()
    changed = changed_existing(hashes)
    original = {name: (OUT / "before" / name).read_bytes() for name in EXISTING}
    assert all(sha256(original[name]) == hashes[name] for name in EXISTING)
    captured = {name: (ROOT / name).read_bytes() for name in SCOPE}
    final_hashes = {name: sha256(data) for name, data in captured.items()}
    patch: list[str] = []
    for name in SCOPE:
        data = captured[name]
        old = original.get(name, b"")
        assert data.endswith(b"\n"), name
        assert not old or old.endswith(b"\n"), name
        after = OUT / "after" / name
        after.parent.mkdir(parents=True, exist_ok=True)
        after.write_bytes(data)
        patch.append(f"diff --git a/{name} b/{name}\n")
        patch.extend(
            difflib.unified_diff(
                old.decode("utf-8").splitlines(keepends=True),
                data.decode("utf-8").splitlines(keepends=True),
                fromfile=f"a/{name}" if name in EXISTING else "/dev/null",
                tofile=f"b/{name}",
            )
        )
    patch_file = OUT / "repair.patch"
    patch_file.write_bytes("".join(patch).encode("utf-8"))
    commands: list[list[str]] = []
    environment = {
        "PATH": os.defpath,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    with tempfile.TemporaryDirectory(prefix="siro-ri004-rollback-") as directory:
        isolated = Path(directory)
        for name, data in captured.items():
            target = isolated / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for arguments in (["--reverse", "--check"], ["--reverse"], ["--check"], []):
            command = ["git", "apply", *arguments, str(patch_file)]
            subprocess.run(
                command,
                cwd=isolated,
                env=environment,
                check=True,
                capture_output=True,
                timeout=15,
            )
            commands.append([*command[:-1], "repair.patch"])
            if arguments == ["--reverse"]:
                assert all(digest(isolated / name) == hashes[name] for name in EXISTING)
                assert all(not (isolated / name).exists() for name in NEW)
        assert all(digest(isolated / name) == final_hashes[name] for name in SCOPE)
    assert not isolated.exists()
    assert all(digest(ROOT / name) == final_hashes[name] for name in SCOPE)
    assert changed_existing(hashes) == changed
    assert all(digest(OUT / "after" / name) == final_hashes[name] for name in SCOPE)
    preservation: dict[str, object] = {
        "status": "PASS",
        "baseline_files": len(hashes),
        "unchanged_existing_files": len(hashes) - len(changed),
        "changed_existing_files": changed,
        "new_files": list(NEW),
        "final_sha256": final_hashes,
        "captured_source_unchanged_during_rehearsal": True,
        "private_files_read": False,
    }
    rollback: dict[str, object] = {
        "status": "PASS",
        "scope": "disposable exact six-file source patch; no live source apply or data rollback",
        "existing_files": list(EXISTING),
        "new_files": list(NEW),
        "commands": commands,
        "patch_sha256": digest(patch_file),
        "baseline_restored": True,
        "candidate_reapplied": True,
        "temporary_directory_removed": True,
        "live_source_unchanged": True,
        "runtime_restarted": False,
        "database_rollback": False,
    }
    save_json("preservation.json", preservation)
    save_json("rollback.json", rollback)
    print(json.dumps({"preservation": preservation, "rollback": rollback}, indent=2))


def before_projection() -> None:
    """Observe missing service against exact pre-card Gateway/index source."""
    hashes = baseline_hashes()
    with tempfile.TemporaryDirectory(prefix="siro-ri004-before-") as directory:
        isolated = Path(directory)
        for path in (ROOT / "src").rglob("*.py"):
            relative = path.relative_to(ROOT).as_posix()
            if "__pycache__" in path.parts or relative == NEW[0]:
                continue
            target = isolated / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        for name in EXISTING:
            target = isolated / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(OUT / "before" / name, target)
        for name in TEST_FILES + TEST_HELPERS:
            target = isolated / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        shutil.copy2(ROOT / "pyproject.toml", isolated / "pyproject.toml")
        environment = {
            "PATH": os.defpath,
            "PYTHONPATH": str(isolated / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        python = str(ROOT / ".venv/bin/python")
        proof = subprocess.run(
            [
                python,
                "-c",
                "import siro.services.tools.orchestrator as m; print(m.__file__)",
            ],
            cwd=isolated,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert str(isolated / "src") in proof.stdout
        assert not (isolated / NEW[0]).exists()
        completed = subprocess.run(
            [python, "-m", "pytest", "-q", *TEST_FILES],
            cwd=isolated,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )
        text = completed.stdout + completed.stderr
        (OUT / "complete-tests-before-final.log").write_text(text, encoding="utf-8")
        result: dict[str, object] = {
            "scope": "new cases with exact pre-card Gateway/index and no new candidate service",
            "result_kind": "expected_missing_interface_collection_error",
            "returncode": completed.returncode,
            "isolated_import_confirmed": True,
            "new_service_absent": True,
            "original_source_hashes_match": {
                name: digest(isolated / name) == hashes[name] for name in EXISTING
            },
            "summary": completed.stdout.strip().splitlines()[-1],
            "private_configuration_copied": False,
            "functional_tests_executed": False,
        }
        assert completed.returncode == 2, result
        assert "skill_candidates" in text and (
            "cannot import name 'skill_candidates'" in text
            or "No module named 'siro.services.tools.skill_candidates'" in text
        )
        assert all(digest(isolated / name) == hashes[name] for name in EXISTING)
    result["temporary_directory_removed"] = not isolated.exists()
    assert result["temporary_directory_removed"] is True
    save_json("complete-tests-before-final.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("before", "final"))
    arguments = parser.parse_args()
    if arguments.phase == "before":
        before_projection()
    else:
        preserve_and_rehearse()
