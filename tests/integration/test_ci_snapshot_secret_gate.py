from __future__ import annotations

import copy
import hashlib
import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
HELPER = REPOSITORY / "scripts/check_secrets.py"
INVENTORY = "docs/runtime-evolution/SOURCE_INVENTORY.json"
LEGACY_TEST = "docs/runtime-evolution/verification/RT011_2026-10-05/test_independent.py"
REVIEWED_PATHS = (
    "docs/runtime-evolution/SOURCE_INVENTORY.json",
    "docs/runtime-evolution/verification/RT005_reverification_2026-10-01/source-snapshot.json",
    "docs/runtime-evolution/verification/RT006_2026-10-01/gpu.log",
    "docs/runtime-evolution/verification/RT006_2026-10-01/source-snapshot.json",
    "docs/runtime-evolution/verification/RT007_2026-10-02/source-snapshot.json",
    "docs/runtime-evolution/verification/RT009_reverification_2026-10-05/source-snapshot.json",
    "docs/runtime-evolution/verification/RT010_2026-10-05/source-snapshot.json",
    "docs/runtime-evolution/verification/RT011_2026-10-05/source-snapshot.json",
    "docs/runtime-evolution/verification/RT011_2026-10-05/test_independent.py",
    "docs/runtime-evolution/verification/RT012_2026-10-05/source-snapshot.json",
    "docs/runtime-evolution/verification/RT014_2026-10-05/source-snapshot.json",
    "docs/runtime-evolution/verification/architecture_review_2026-10-03/source-digests.json",
    "docs/runtime-evolution/verification/architecture_review_2026-10-05/source-digests.json",
    "assets/companion/haru-upperbody/0.1.0/pack.json",
)


def scan(directory: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "detect_secrets", "scan", "--all-files", "--no-verify"],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def gate(directory: Path, report: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER)],
        cwd=directory,
        input=json.dumps(report),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.fixture(scope="module")
def audited_snapshot(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    directory = tmp_path_factory.mktemp("reviewed-history")
    for name in REVIEWED_PATHS:
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / name, target)
    report = scan(directory)
    assert set(report["results"]) == set(REVIEWED_PATHS)
    assert sum(map(len, report["results"].values())) == 1343
    return directory, report


@pytest.fixture
def snapshot_checkout(tmp_path: Path, audited_snapshot: tuple[Path, dict[str, Any]]) -> Path:
    shutil.copytree(audited_snapshot[0], tmp_path, dirs_exist_ok=True)
    return tmp_path


def test_actual_reviewed_scanner_batches_pass(
    snapshot_checkout: Path,
    audited_snapshot: tuple[Path, dict[str, Any]],
) -> None:
    result = gate(snapshot_checkout, audited_snapshot[1])
    assert result.returncode == 0, result.stderr
    assert not result.stdout + result.stderr


def test_finding_order_does_not_change_reviewed_batch(
    snapshot_checkout: Path,
    audited_snapshot: tuple[Path, dict[str, Any]],
) -> None:
    report = copy.deepcopy(audited_snapshot[1])
    for findings in report["results"].values():
        findings.reverse()
    assert gate(snapshot_checkout, report).returncode == 0


@pytest.mark.parametrize("name", REVIEWED_PATHS)
def test_any_changed_snapshot_bytes_require_new_review(
    snapshot_checkout: Path,
    audited_snapshot: tuple[Path, dict[str, Any]],
    name: str,
) -> None:
    with (snapshot_checkout / name).open("a") as output:
        output.write("\n")
    result = gate(snapshot_checkout, audited_snapshot[1])
    assert result.returncode == 1
    assert name in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("line_number", 3),
        ("type", "Secret Keyword"),
        ("hashed_secret", hashlib.sha1(b"unreviewed-finding").hexdigest()),
        ("filename", "another-snapshot.json"),
        ("is_verified", True),
    ],
)
def test_changed_snapshot_finding_is_rejected(
    snapshot_checkout: Path,
    audited_snapshot: tuple[Path, dict[str, Any]],
    field: str,
    value: object,
) -> None:
    report = copy.deepcopy(audited_snapshot[1])
    report["results"][INVENTORY][0][field] = value
    result = gate(snapshot_checkout, report)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("change", ["missing", "duplicate", "additional", "same-size-duplicate"])
def test_partial_or_extended_snapshot_batch_is_rejected(
    snapshot_checkout: Path,
    audited_snapshot: tuple[Path, dict[str, Any]],
    change: str,
) -> None:
    report = copy.deepcopy(audited_snapshot[1])
    findings = report["results"][INVENTORY]
    if change == "missing":
        findings.pop()
    elif change == "same-size-duplicate":
        findings[-1] = copy.deepcopy(findings[0])
    else:
        extra = copy.deepcopy(findings[0])
        if change == "additional":
            extra["hashed_secret"] = hashlib.sha1(b"new-metadata-or-secret").hexdigest()
        findings.append(extra)
    assert gate(snapshot_checkout, report).returncode == 1


@pytest.mark.parametrize(
    "alias",
    ["other.json", "./" + INVENTORY, "../" + INVENTORY, "docs/../" + INVENTORY],
)
def test_reviewed_snapshot_findings_are_not_accepted_at_other_paths(
    snapshot_checkout: Path,
    audited_snapshot: tuple[Path, dict[str, Any]],
    alias: str,
) -> None:
    findings = copy.deepcopy(audited_snapshot[1]["results"][INVENTORY])
    for finding in findings:
        finding["filename"] = alias
    assert gate(snapshot_checkout, {"results": {alias: findings}}).returncode == 1


@pytest.mark.parametrize("state", ["missing", "directory", "leaf-symlink", "parent-symlink"])
def test_unavailable_or_symlinked_snapshot_is_rejected(
    snapshot_checkout: Path,
    audited_snapshot: tuple[Path, dict[str, Any]],
    state: str,
) -> None:
    target = snapshot_checkout / INVENTORY
    if state == "parent-symlink":
        old_parent = target.parent
        moved = snapshot_checkout / "relocated"
        old_parent.rename(moved)
        old_parent.symlink_to(moved, target_is_directory=True)
    else:
        content = target.read_bytes()
        target.unlink()
        if state == "directory":
            target.mkdir()
        elif state == "leaf-symlink":
            moved = snapshot_checkout / "relocated.json"
            moved.write_bytes(content)
            target.symlink_to(moved)
    result = gate(snapshot_checkout, audited_snapshot[1])
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_snapshot_read_failure_is_closed(
    snapshot_checkout: Path,
    audited_snapshot: tuple[Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = runpy.run_path(str(HELPER))
    original = Path.read_bytes

    def fail_reviewed_read(path: Path) -> bytes:
        if path.as_posix() == INVENTORY:
            raise PermissionError("synthetic permission failure")
        return original(path)

    monkeypatch.chdir(snapshot_checkout)
    monkeypatch.setattr(Path, "read_bytes", fail_reviewed_read)
    failures = helper["unresolved"](audited_snapshot[1])
    assert any(path == INVENTORY for path, _, _ in failures)


@pytest.mark.parametrize(
    "name", [INVENTORY, LEGACY_TEST, "new_provider.py", ".github/workflows/check.yml"]
)
def test_actual_scanner_rejects_added_credentials_in_reviewed_or_new_files(
    snapshot_checkout: Path,
    name: str,
) -> None:
    synthetic = hashlib.sha256(b"snapshot-boundary-test-credential-never-valid").hexdigest()
    target = snapshot_checkout / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if name.endswith(".json"):
        data = json.loads(target.read_text())
        data["api_key"] = synthetic
        target.write_text(json.dumps(data, indent=2) + "\n")
    elif name == LEGACY_TEST:
        parameter = "api_key"
        original = parameter + "=" + json.dumps("synthetic")
        replacement = parameter + "=" + json.dumps(synthetic)
        target.write_text(target.read_text().replace(original, replacement))
    else:
        target.write_text(f'api_key = "{synthetic}"\n')
    report = scan(snapshot_checkout)
    assert any(
        finding["hashed_secret"] == hashlib.sha1(synthetic.encode()).hexdigest()
        for findings in report["results"].values()
        for finding in findings
    )
    result = gate(snapshot_checkout, report)
    assert result.returncode == 1
    assert name in result.stderr
    assert synthetic not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
