from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
PROFILE = Path("src/siro/services/agent/gpt_oss_profile.json")
HELPER = REPOSITORY / "scripts/check_secrets.py"


def scan(directory: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "detect_secrets", "scan", "--all-files", "--no-verify"],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    report: dict[str, Any] = json.loads(result.stdout)
    return report


@pytest.fixture
def public_checkout(tmp_path: Path) -> Path:
    target = tmp_path / PROFILE
    target.parent.mkdir(parents=True)
    shutil.copyfile(REPOSITORY / PROFILE, target)
    return tmp_path


@pytest.fixture(scope="module")
def public_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    directory = tmp_path_factory.mktemp("public-pins")
    target = directory / PROFILE
    target.parent.mkdir(parents=True)
    shutil.copyfile(REPOSITORY / PROFILE, target)
    report = scan(directory)
    assert set(report["results"]) == {PROFILE.as_posix()}
    assert len(report["results"][PROFILE.as_posix()]) == 6
    return report


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


def test_exact_public_scanner_findings_pass(
    public_checkout: Path, public_report: dict[str, Any]
) -> None:
    result = gate(public_checkout, public_report)
    assert result.returncode == 0, result.stderr
    assert not result.stderr


def test_no_findings_pass_without_public_profile(tmp_path: Path) -> None:
    assert gate(tmp_path, {"results": {}}).returncode == 0


@pytest.mark.parametrize("location", ["profile", "other-file"])
def test_actual_scanner_new_synthetic_secret_fails(public_checkout: Path, location: str) -> None:
    synthetic = hashlib.sha256(b"ci-test-only-credential-never-valid").hexdigest()
    if location == "profile":
        target = public_checkout / PROFILE
        data = json.loads(target.read_text())
        data["api_key"] = synthetic
        target.write_text(json.dumps(data, indent=2) + "\n")
    else:
        (public_checkout / "new_provider.py").write_text(f'api_key = "{synthetic}"\n')
    report = scan(public_checkout)
    assert any(
        finding["hashed_secret"] == hashlib.sha1(synthetic.encode()).hexdigest()
        for findings in report["results"].values()
        for finding in findings
    )
    result = gate(public_checkout, report)
    assert result.returncode == 1
    assert synthetic not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_changed_profile_bytes_require_new_audit(
    public_checkout: Path, public_report: dict[str, Any]
) -> None:
    with (public_checkout / PROFILE).open("a") as output:
        output.write("\n")
    assert gate(public_checkout, public_report).returncode == 1


@pytest.mark.parametrize("state", ["missing", "directory"])
def test_unreadable_profile_does_not_acknowledge_findings(
    public_checkout: Path, public_report: dict[str, Any], state: str
) -> None:
    (public_checkout / PROFILE).unlink()
    if state == "directory":
        (public_checkout / PROFILE).mkdir()
    result = gate(public_checkout, public_report)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hashed_secret", hashlib.sha1(b"unreviewed").hexdigest()),
        ("line_number", 4),
        ("type", "Secret Keyword"),
        ("filename", "another-profile.json"),
        ("is_verified", True),
    ],
)
def test_changed_finding_is_not_public_pin(
    public_checkout: Path, public_report: dict[str, Any], field: str, value: object
) -> None:
    report = copy.deepcopy(public_report)
    report["results"][PROFILE.as_posix()][0][field] = value
    assert gate(public_checkout, report).returncode == 1


def test_reviewed_fingerprint_in_other_path_still_fails(
    public_checkout: Path, public_report: dict[str, Any]
) -> None:
    report = copy.deepcopy(public_report)
    findings = report["results"].pop(PROFILE.as_posix())
    for finding in findings:
        finding["filename"] = "another-profile.json"
    report["results"]["another-profile.json"] = findings
    assert gate(public_checkout, report).returncode == 1


@pytest.mark.parametrize(
    "report",
    [None, [], {}, {"results": None}, {"results": []}, {"results": {"p": {}}}],
)
def test_malformed_report_fails_without_traceback(tmp_path: Path, report: object) -> None:
    result = gate(tmp_path, report)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    [("line_number", True), ("line_number", "3"), ("hashed_secret", None)],
)
def test_malformed_finding_fails(
    public_checkout: Path, public_report: dict[str, Any], field: str, value: object
) -> None:
    report = copy.deepcopy(public_report)
    report["results"][PROFILE.as_posix()][0][field] = value
    assert gate(public_checkout, report).returncode == 1


@pytest.mark.parametrize(
    "raw",
    ["{", '{"results":{"p":[]},"results":{}}'],
)
def test_invalid_or_duplicate_json_fails(tmp_path: Path, raw: str) -> None:
    result = subprocess.run(
        [sys.executable, str(HELPER)],
        cwd=tmp_path,
        input=raw,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_check_excludes_git_metadata_and_keeps_application_secret_checks(
    public_checkout: Path,
) -> None:
    generated = public_checkout / ".git/FETCH_HEAD"
    generated.parent.mkdir()
    commit = hashlib.sha1(b"synthetic-public-commit").hexdigest()
    # Checkout-by-commit includes the fetched identifier in its quoted descriptor.
    generated.write_text(f"{commit}\t\t'{commit}' of https://github.com/pigon2233/SiroV2\n")
    source_paths = ["new_provider.py", ".github/workflows/check.yml", ".gitignore"]
    synthetic = hashlib.sha256(b"ci-boundary-test-credential-never-valid").hexdigest()
    for path in source_paths:
        target = public_checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'api_key = "{synthetic}"\n')
    match = re.search(r"--exclude-files '([^']+)'", (REPOSITORY / "scripts/check").read_text())
    assert match is not None
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "detect_secrets",
            "scan",
            "--all-files",
            "--no-verify",
            "--exclude-files",
            match[1],
        ],
        cwd=public_checkout,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    report = json.loads(result.stdout)
    assert generated.relative_to(public_checkout).as_posix() not in report["results"]
    assert all(path in report["results"] for path in source_paths)
    assert gate(public_checkout, report).returncode == 1
