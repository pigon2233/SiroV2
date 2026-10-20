"""Actual subprocess acceptance outcomes; no product services or private fixtures."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def helper() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "acceptance_runner", Path(__file__).resolve().parents[1] / "scripts/run_acceptance.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "README").write_text("synthetic\n")
    subprocess.run(["git", "add", "README"], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "synthetic baseline",
        ],
        cwd=root,
        check=True,
    )
    return root


@pytest.mark.parametrize(
    ("body", "expected", "passed", "failed", "skipped"),
    [
        ("def test_ok(): assert True", "PASS", 1, 0, 0),
        ("def test_bad(): assert False", "FAIL", 0, 1, 0),
        (
            "import pytest\n@pytest.mark.skip(reason='synthetic')\ndef test_skip(): pass",
            "PARTIAL",
            0,
            0,
            1,
        ),
        ("import pytest\n@pytest.mark.xfail\ndef test_xfail(): assert False", "PARTIAL", 0, 0, 1),
        ("import pytest\n@pytest.mark.xfail\ndef test_xpass(): assert True", "FAIL", 0, 1, 0),
        ("# no tests", "NO_TESTS", 0, 0, 0),
        ("raise RuntimeError('SYNTHETIC_PRIVATE_SENTINEL')", "ERROR", 0, 0, 0),
    ],
)
def test_real_pytest_outcomes(
    helper: ModuleType,
    repository: Path,
    tmp_path: Path,
    body: str,
    expected: str,
    passed: int,
    failed: int,
    skipped: int,
) -> None:
    (repository / "tests/test_fixture.py").write_text(body + "\n")
    output = tmp_path / "receipt"
    code = helper.run(repository, ["tests/test_fixture.py"], output, "L1")
    text = (output / "receipt.json").read_text()
    receipt = json.loads(text)
    assert code == (0 if expected == "PASS" else 1)
    assert receipt["outcome"] == expected
    assert receipt["counts"]["passed"] == passed
    assert receipt["counts"]["failed"] == failed
    assert receipt["counts"]["skipped"] == skipped
    assert receipt["declared_evidence_level"] == "L1"
    assert receipt["evidence_level_verified"] is False
    assert receipt["source_before"]["dirty"] is True
    assert receipt["source_before"] == receipt["source_after"]
    assert "SYNTHETIC_PRIVATE_SENTINEL" not in text
    assert list(output.iterdir()) == [output / "receipt.json"]


def test_does_not_reuse_old_evidence(helper: ModuleType, repository: Path, tmp_path: Path) -> None:
    output = tmp_path / "old"
    output.mkdir()
    original = output / "receipt.json"
    original.write_text("old evidence")
    with pytest.raises(FileExistsError):
        helper.run(repository, ["tests"], output, "L1")
    assert original.read_text() == "old evidence"


@pytest.mark.parametrize(
    "target", ["../outside.py", "--collect-only", "README", "tests/missing.py"]
)
def test_rejects_invalid_target(
    helper: ModuleType,
    repository: Path,
    tmp_path: Path,
    target: str,
) -> None:
    output = tmp_path / "invalid"
    with pytest.raises(ValueError):
        helper.run(repository, [target], output, "L1")
    assert not output.exists()


def test_missing_and_invalid_junit_never_pass(helper: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    assert helper.summarize(path, 0)[0] == "ERROR"
    path.write_text("<not-junit/>")
    assert helper.summarize(path, 0)[0] == "ERROR"
    path.write_text("<testsuites")
    assert helper.summarize(path, 0)[0] == "ERROR"


def test_source_change_invalidates_pass(
    helper: ModuleType,
    repository: Path,
    tmp_path: Path,
) -> None:
    (repository / "tests/test_edit.py").write_text(
        "from pathlib import Path\ndef test_edit(): Path('README').write_text('changed')\n"
    )
    assert helper.run(repository, ["tests"], tmp_path / "changed", "L1") == 1
    receipt: dict[str, Any] = json.loads((tmp_path / "changed/receipt.json").read_text())
    assert receipt["outcome"] == "SOURCE_CHANGED"
    assert receipt["counts"]["passed"] == 1


def test_dirty_content_change_invalidates_pass(
    helper: ModuleType,
    repository: Path,
    tmp_path: Path,
) -> None:
    (repository / "README").write_text("already dirty")
    (repository / "tests/test_edit.py").write_text(
        "from pathlib import Path\ndef test_edit(): Path('README').write_text('different dirty')\n"
    )
    assert helper.run(repository, ["tests"], tmp_path / "dirty-change", "L1") == 1
    receipt = json.loads((tmp_path / "dirty-change/receipt.json").read_text())
    assert receipt["outcome"] == "SOURCE_CHANGED"
    assert receipt["source_before"]["status_sha256"] == receipt["source_after"]["status_sha256"]
    assert receipt["source_before"]["content_sha256"] != receipt["source_after"]["content_sha256"]


def test_environment_cannot_silently_disable_tests(
    helper: ModuleType,
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (repository / "tests/test_fail.py").write_text("def test_fail(): assert False\n")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    assert helper.run(repository, ["tests"], tmp_path / "env", "L1") == 1
    receipt = json.loads((tmp_path / "env/receipt.json").read_text())
    assert receipt["outcome"] == "FAIL"
    assert receipt["counts"]["failed"] == 1


@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        ("def test_ok(): assert True", 0),
        ("def test_bad(): assert False", 1),
    ],
)
def test_cli_exit_and_receipt(
    helper: ModuleType,
    repository: Path,
    tmp_path: Path,
    body: str,
    expected_code: int,
) -> None:
    import sys

    (repository / "scripts").mkdir()
    script = repository / "scripts/run_acceptance.py"
    assert helper.__file__ is not None
    script.write_text(Path(helper.__file__).read_text())
    (repository / "tests/test_fixture.py").write_text(body + "\n")
    output = tmp_path / "cli"
    command = [sys.executable, str(script), "tests", "--level", "L1", "--output", str(output)]
    result = subprocess.run(command, cwd=repository, check=False)
    assert result.returncode == expected_code
    receipt = (output / "receipt.json").read_bytes()
    assert json.loads(receipt)["outcome"] == ("PASS" if expected_code == 0 else "FAIL")
    repeated = subprocess.run(command, cwd=repository, check=False)
    assert repeated.returncode == 2
    assert (output / "receipt.json").read_bytes() == receipt


def test_git_failure_never_issues_receipt(
    helper: ModuleType,
    repository: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "no-git"
    with pytest.raises(FileNotFoundError):
        helper.run(repository, ["tests"], output, "L1", str(tmp_path / "missing-git"))
    assert not output.exists()
