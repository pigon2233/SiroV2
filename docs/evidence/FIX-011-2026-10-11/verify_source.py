"""FIX-011 exact source preservation and disposable reverse/reapply rehearsal.

Run ``final`` only after the task owner freezes the five scoped source/test
files. This script never applies a patch to the shared workspace or runtime.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
EXISTING = (
    "src/siro/adapters/skill_worker.py",
    "src/siro/services/tools/execution.py",
    "src/siro/skill_worker.py",
)
NEW = (
    "src/siro/adapters/process_execution.py",
    "tests/integration/test_skill_worker_lifecycle.py",
)
SCOPE = EXISTING + NEW


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return sha256(path.read_bytes())


def baseline_hashes() -> dict[str, str]:
    hashes: dict[str, str] = json.loads((OUT / "baseline.json").read_text())["hashes"]
    assert len(hashes) == 252, len(hashes)
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
    with tempfile.TemporaryDirectory(prefix="siro-fix011-rollback-") as directory:
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
        "scope": "disposable exact five-file source patch; no live source apply or data rollback",
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("final",))
    parser.parse_args()
    preserve_and_rehearse()
