"""RI-004 worker exact source preservation and disposable reverse/reapply.

Run ``final`` only after the task owner freezes the seven scoped source/test
files. ``before`` runs the two existing constructor contracts against exact
pre-card sources and screens new-test collection; it never claims sandbox
negative results from collection or missing constructor support.
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
    "src/siro/adapters/skill_worker.py",
    "src/siro/services/tools/patch_verification.py",
    "src/siro/services/tools/patch_verification_runner.py",
)
NEW = (
    "src/siro/adapters/isolated_python.py",
    "src/siro/adapters/python_restrictions.py",
    "src/siro/adapters/strict_skill_runner.py",
    "tests/integration/test_strict_skill_worker.py",
)
SCOPE = EXISTING + NEW


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return sha256(path.read_bytes())


def baseline_hashes() -> dict[str, str]:
    hashes: dict[str, str] = json.loads((OUT / "baseline.json").read_text())["hashes"]
    assert len(hashes) == 254, len(hashes)
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
    with tempfile.TemporaryDirectory(prefix="siro-ri004-worker-rollback-") as directory:
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
        "scope": "disposable exact seven-file source patch; no live source apply or data rollback",
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
    hashes = baseline_hashes()
    with tempfile.TemporaryDirectory(prefix="siro-ri004-worker-before-") as directory:
        isolated = Path(directory)
        for base in ("src", "tests"):
            for path in (ROOT / base).rglob("*.py"):
                relative = path.relative_to(ROOT).as_posix()
                if "__pycache__" in path.parts or relative in NEW[:3]:
                    continue
                target = isolated / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        for name in EXISTING:
            target = isolated / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(OUT / "before" / name, target)
        assert all(digest(isolated / name) == hashes[name] for name in EXISTING)
        assert all(not (isolated / name).exists() for name in NEW[:3])
        assert (isolated / NEW[-1]).is_file(), "new strict tests must exist before screen"
        formal = isolated / "tests/test_profile_before.py"
        shutil.copy2(OUT / "test_profile_before.py", formal)
        shutil.copy2(ROOT / "pyproject.toml", isolated / "pyproject.toml")
        environment = {
            "PATH": os.defpath,
            "PYTHONPATH": str(isolated / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        python = str(ROOT / ".venv/bin/python")
        proof = subprocess.run(
            [python, "-c", "import siro.adapters.skill_worker as m; print(m.__file__)"],
            cwd=isolated,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        assert str(isolated / "src") in proof.stdout
        constructor = subprocess.run(
            [python, "-m", "pytest", "-q", "tests/test_profile_before.py"],
            cwd=isolated,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        constructor_text = constructor.stdout + constructor.stderr
        (OUT / "complete-contracts-before.log").write_text(constructor_text)
        assert constructor.returncode == 1
        assert "2 failed" in constructor.stdout and "TypeError" in constructor_text
        collection = subprocess.run(
            [python, "-m", "pytest", "--collect-only", "-q", NEW[-1]],
            cwd=isolated,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        collection_text = collection.stdout + collection.stderr
        (OUT / "complete-collection-before.log").write_text(collection_text)
        assert collection.returncode in {0, 2}, collection_text
        if collection.returncode == 2:
            assert any(
                name in collection_text
                for name in ("isolated_python", "python_restrictions", "strict_skill_runner")
            ), collection_text
            assert any(
                marker in collection_text
                for marker in ("ModuleNotFoundError", "ImportError", "No module named")
            ), collection_text
        result = {
            "scope": "exact pre-card three sources, new sandbox helpers absent",
            "isolated_import_confirmed": True,
            "original_source_hashes_match": {
                name: digest(isolated / name) == hashes[name] for name in EXISTING
            },
            "new_helpers_absent": True,
            "constructor_contracts": {
                "returncode": constructor.returncode,
                "expected_failures": 2,
                "reason": "missing explicit profile constructor; TypeError before dispatch",
                "functional_constructor_tests_executed": True,
                "candidate_os_checks_executed": False,
            },
            "new_test_collection": {
                "returncode": collection.returncode,
                "result_kind": "collected_without_execution"
                if collection.returncode == 0
                else "missing_interface_collection_error",
                "summary": collection.stdout.strip().splitlines()[-1],
                "functional_tests_executed": False,
                "candidate_os_checks_executed": False,
            },
            "private_configuration_copied": False,
        }
    result["temporary_directory_removed"] = not isolated.exists()
    assert result["temporary_directory_removed"]
    save_json("complete-before.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("before", "final"))
    args = parser.parse_args()
    if args.phase == "before":
        before_projection()
    else:
        preserve_and_rehearse()
