"""Rehearse only D52 source changes in a disposable copy; never operate on live data."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT = Path(__file__).resolve().parents[3]
EVIDENCE = PROJECT / "docs/evidence/RI-005-launcher-2026-10-13"
EXISTING = (
    "src/siro/core/releases.py",
    "scripts/launch_companion.py",
    "src/siro/services/presentation/gateway.py",
)
NEW = (
    "tests/integration/test_release_launch_selection.py",
    "tests/integration/test_release_ready_identity.py",
    "tests/integration/test_signed_companion_launcher.py",
    "tests/integration/test_release_source_process.py",
)
PRESERVED_FENCES = (
    "src/siro/persistence/sqlite.py",
    "src/siro/cli.py",
    "tests/integration/test_sqlite_backup_lifecycle.py",
    "tests/integration/test_backup_cli_cancellation.py",
    "src/siro/adapters/data_ownership.py",
    "src/siro/operations.py",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot(paths: tuple[str, ...] | list[str]) -> dict[str, bytes]:
    return {relative: (PROJECT / relative).read_bytes() for relative in paths}


def make_patch(before: dict[str, bytes], after: dict[str, bytes]) -> str:
    chunks: list[str] = []
    for relative in (*EXISTING, *NEW):
        old = before.get(relative, b"")
        new = after[relative]
        chunks.append(f"diff --git a/{relative} b/{relative}\n")
        if relative in NEW:
            chunks.append("new file mode 100644\n")
        chunks.extend(
            difflib.unified_diff(
                old.decode().splitlines(keepends=True),
                new.decode().splitlines(keepends=True),
                fromfile=f"a/{relative}" if relative in EXISTING else "/dev/null",
                tofile=f"b/{relative}",
            )
        )
    return "".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", choices=("preliminary", "final"), required=True)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    baseline = json.loads((EVIDENCE / "baseline.json").read_text())["hashes"]
    assert len(baseline) == 273
    expected_changed = set(EXISTING)
    current = snapshot(list(baseline))
    new_files = snapshot(NEW)
    current.update(new_files)
    changed = {
        relative for relative, expected in baseline.items() if sha(current[relative]) != expected
    }
    assert changed == expected_changed, {"unexpected_changed": sorted(changed)}
    assert set(NEW).isdisjoint(baseline)
    before = {relative: (EVIDENCE / "before" / relative).read_bytes() for relative in EXISTING}
    for relative in EXISTING:
        assert sha(before[relative]) == baseline[relative], f"before mismatch: {relative}"
    after_hashes = {relative: sha(current[relative]) for relative in (*EXISTING, *NEW)}
    if args.freeze is not None:
        freeze = json.loads(args.freeze.read_text())
        expected = freeze.get("source_sha256", freeze.get("hashes", freeze))
        assert set(expected) == set(after_hashes), "freeze must identify exactly seven source files"
        assert all(expected[relative] == digest for relative, digest in after_hashes.items())
    patch = make_patch(before, current)
    patch_path = EVIDENCE / f"rollback-repair-{args.label}.patch"
    patch_path.write_text(patch)
    operations: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="siro-d52-rollback-") as directory:
        disposable = Path(directory)
        for relative, data in current.items():
            path = disposable / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        local_patch = disposable / "d52.patch"
        local_patch.write_text(patch)
        for label, flags in (
            ("reverse_check", ["--reverse", "--check"]),
            ("reverse_apply", ["--reverse"]),
        ):
            result = subprocess.run(
                ["git", "apply", *flags, str(local_patch)],
                cwd=disposable,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, (label, result.stderr)
            operations.append({"operation": label, "exit_code": result.returncode})
        for relative, digest in baseline.items():
            assert sha((disposable / relative).read_bytes()) == digest, relative
        assert all(not (disposable / relative).exists() for relative in NEW)
        for label, flags in (("reapply_check", ["--check"]), ("reapply", [])):
            result = subprocess.run(
                ["git", "apply", *flags, str(local_patch)],
                cwd=disposable,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, (label, result.stderr)
            operations.append({"operation": label, "exit_code": result.returncode})
        assert all(
            (disposable / relative).read_bytes() == data for relative, data in current.items()
        )
    finish = snapshot(list(baseline))
    finish.update(snapshot(NEW))
    assert current == finish, "STALE_SOURCE: working source changed during rehearsal"
    report = {
        "label": args.label,
        "scope": "exact seven source files in disposable copy only",
        "baseline_count": len(baseline),
        "unchanged_old_files": len(baseline) - len(EXISTING),
        "existing_changed": list(EXISTING),
        "new_test_files": list(NEW),
        "before_hashes": {relative: baseline[relative] for relative in EXISTING},
        "after_hashes": after_hashes,
        "preserved_fences": {relative: baseline[relative] for relative in PRESERVED_FENCES},
        "source_stable": True,
        "freeze_bound": args.freeze is not None,
        "freeze_sha256": sha(args.freeze.read_bytes()) if args.freeze is not None else None,
        "patch_sha256": sha(patch.encode()),
        "operations": operations,
        "reverse_matches_all_273_baseline_files": True,
        "reverse_removes_only_4_new_tests": True,
        "reapply_matches_all_277_current_files": True,
        "temporary_root_removed": not disposable.exists(),
        "workspace_data_index_mutated": False,
        "operational_release_rollback": "NOT_RUN",
        "deployment_approval": "NOT_PROVIDED_BY_THIS_REHEARSAL",
    }
    (EVIDENCE / f"rollback-{args.label}.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps({"label": args.label, "passed": True, "freeze_bound": args.freeze is not None})
    )


if __name__ == "__main__":
    main()
