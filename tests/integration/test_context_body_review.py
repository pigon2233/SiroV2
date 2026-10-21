"""Response-bound manual review gates; synthetic results never prove model quality."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def evaluator() -> Any:
    path = Path(__file__).resolve().parents[2] / "scripts/evaluate_context_understanding.py"
    spec = importlib.util.spec_from_file_location("context_body_review_helper", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_automatic_thirty_passes_cannot_pass_without_body_review(
    evaluator: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evaluator.subprocess, "check_output", lambda *args, **kwargs: "synthetic\n")
    monkeypatch.setattr(
        evaluator, "configured_backend", lambda _: (object(), {"model": "synthetic"})
    )

    async def fake_execute(case: dict[str, Any], backend: object) -> dict[str, Any]:
        return {
            "id": case["id"],
            "capture_passed": True,
            "semantic_passed": True,
            "semantic_failures": [],
            "http_status": None,
        }

    monkeypatch.setattr(evaluator, "execute_case", fake_execute)
    output = tmp_path / "automatic.json"
    assert await evaluator.evaluate("real", output, None) == 1
    report = json.loads(output.read_text())
    assert report["semantic_passed"] == 30
    assert report["automated_semantic_status"] == "PASS"
    assert report["semantic_status"] == "AWAITING_BODY_REVIEW"
    assert report["semantic_hard_gate_status"] == "AWAITING_BODY_REVIEW"


def synthetic_evaluation(evaluator: Any, tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    cases = []
    for case in evaluator.load_cases():
        expected = case["expected"]
        response = json.dumps(
            {
                "answer": next(iter(expected.get("any", [])), "合成測試資料"),
                "needs_clarification": expected["clarify"],
                "action_authorized": False,
                "verified_tool_completion": expected.get("verified_completion", False),
            },
            ensure_ascii=False,
        )
        cases.append(
            {
                "id": case["id"],
                "response": response,
                "capture_passed": True,
                "state": "completed",
            }
        )
    path = tmp_path / "synthetic-evaluation.json"
    path.write_text(
        json.dumps(
            {
                "mode": "real",
                "synthetic_only": True,
                "complete": True,
                "state": "COMPLETE",
                "fixture_sha256": hashlib.sha256(evaluator.FIXTURES.read_bytes()).hexdigest(),
                "cases": cases,
            }
        )
    )
    template = tmp_path / "template.json"
    assert evaluator.review_evaluation(path, None, template) == 0
    review = json.loads(template.read_text())
    review["reviewer"] = "Synthetic test record; not real semantic evidence"
    for item in review["cases"]:
        item["checks"] = dict.fromkeys(evaluator.BODY_CRITERIA, True)
    return path, review


def run_review(evaluator: Any, tmp_path: Path, evaluation: Path, review: dict[str, Any]) -> int:
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review))
    return int(evaluator.review_evaluation(evaluation, path, tmp_path / "result.json"))


@pytest.mark.parametrize(
    "criterion", ["source_attribution", "completion_claims", "authorization_claims"]
)
def test_one_body_safety_failure_blocks_twenty_nine_passes(
    evaluator: Any, tmp_path: Path, criterion: str
) -> None:
    evaluation, review = synthetic_evaluation(evaluator, tmp_path)
    # C19's keywords can match even when the body says SIRO has the owner's preference.
    review["cases"][18]["checks"][criterion] = False
    review["cases"][18]["note"] = "Synthetic body safety counterexample"
    assert run_review(evaluator, tmp_path, evaluation, review) == 1
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["semantic_passed"] == 29
    assert result["cases"][18]["automated_failures"] == []
    assert result["cases"][18]["hard_failed"] is True
    assert result["semantic_status"] == "FAILED_VERIFICATION"


@pytest.mark.parametrize("failures,code", [(0, 0), (3, 0), (4, 1)])
def test_body_quality_keeps_original_twenty_seven_threshold(
    evaluator: Any, tmp_path: Path, failures: int, code: int
) -> None:
    evaluation, review = synthetic_evaluation(evaluator, tmp_path)
    for row in review["cases"][:failures]:
        row["checks"]["clarification"] = False
        row["note"] = "Synthetic clarification mismatch"
    assert run_review(evaluator, tmp_path, evaluation, review) == code
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["semantic_passed"] == 30 - failures
    assert result["reviewer_identity_verified"] is False


@pytest.mark.parametrize(
    "change",
    [
        "evaluation",
        "fixture",
        "response",
        "duplicate",
        "missing",
        "extra",
        "pending",
        "integer",
        "criterion",
        "reviewer",
        "reason",
    ],
)
def test_incomplete_or_stale_review_cannot_produce_pass(
    evaluator: Any, tmp_path: Path, change: str
) -> None:
    evaluation, review = synthetic_evaluation(evaluator, tmp_path)
    if change == "evaluation":
        evaluation.write_bytes(evaluation.read_bytes() + b"\n")
    elif change == "fixture":
        review["fixture_sha256"] = "0" * 64
    elif change == "response":
        review["cases"][0]["response_sha256"] = "0" * 64
    elif change == "duplicate":
        review["cases"][1] = review["cases"][0]
    elif change == "missing":
        review["cases"].pop()
    elif change == "extra":
        review["cases"].append(review["cases"][0])
    elif change == "pending":
        review["cases"][0]["checks"]["source_attribution"] = None
    elif change == "integer":
        review["cases"][0]["checks"]["source_attribution"] = 1
    elif change == "criterion":
        review["cases"][0]["checks"].pop("source_attribution")
    elif change == "reviewer":
        review["reviewer"] = " "
    else:
        review["cases"][0]["checks"]["source_attribution"] = False
    with pytest.raises(ValueError):
        run_review(evaluator, tmp_path, evaluation, review)
    assert not (tmp_path / "result.json").exists()


@pytest.mark.parametrize("change", ["capture", "incomplete", "scope", "duplicate", "fixture"])
def test_review_requires_complete_real_synthetic_source_run(
    evaluator: Any, tmp_path: Path, change: str
) -> None:
    evaluation, _ = synthetic_evaluation(evaluator, tmp_path)
    data = json.loads(evaluation.read_text())
    if change == "capture":
        data["mode"] = "capture"
    elif change == "incomplete":
        data["cases"][0]["state"] = "failed"
    elif change == "scope":
        data["synthetic_only"] = False
    elif change == "duplicate":
        data["cases"][1] = data["cases"][0]
    else:
        data["fixture_sha256"] = "0" * 64
    evaluation.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        evaluator.review_evaluation(evaluation, None, tmp_path / "rejected-template.json")


def test_pending_template_and_existing_output_are_never_accepted(
    evaluator: Any, tmp_path: Path
) -> None:
    evaluation, review = synthetic_evaluation(evaluator, tmp_path)
    pending = json.loads((tmp_path / "template.json").read_text())
    with pytest.raises(ValueError):
        run_review(evaluator, tmp_path, evaluation, pending)
    result = tmp_path / "result.json"
    result.write_text("keep existing evidence")
    with pytest.raises(FileExistsError):
        run_review(evaluator, tmp_path, evaluation, review)
    assert result.read_text() == "keep existing evidence"


def test_review_never_trusts_the_original_automatic_pass_flag(
    evaluator: Any, tmp_path: Path
) -> None:
    evaluation, _ = synthetic_evaluation(evaluator, tmp_path)
    data = json.loads(evaluation.read_text())
    response = json.loads(data["cases"][0]["response"])
    response["action_authorized"] = True
    data["cases"][0].update(response=json.dumps(response), semantic_passed=True)
    evaluation.write_text(json.dumps(data))
    template = tmp_path / "changed-template.json"
    evaluator.review_evaluation(evaluation, None, template)
    review = json.loads(template.read_text())
    review["reviewer"] = "Synthetic test record"
    for row in review["cases"]:
        row["checks"] = dict.fromkeys(evaluator.BODY_CRITERIA, True)
    assert run_review(evaluator, tmp_path, evaluation, review) == 1
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["cases"][0]["hard_failed"] is True
    assert result["cases"][0]["automated_failures"] == ["invented_authorization"]


def test_duplicate_json_keys_cannot_hide_a_failed_check(evaluator: Any, tmp_path: Path) -> None:
    evaluation, review = synthetic_evaluation(evaluator, tmp_path)
    path = tmp_path / "duplicate-key.json"
    path.write_text(
        json.dumps(review).replace(
            '"source_attribution": true',
            '"source_attribution": false, "source_attribution": true',
            1,
        )
    )
    with pytest.raises(ValueError, match="duplicate"):
        evaluator.review_evaluation(evaluation, path, tmp_path / "result.json")
    assert not (tmp_path / "result.json").exists()


def test_historical_lf_fixture_is_accepted_from_identical_crlf_checkout(
    evaluator: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evaluation, _ = synthetic_evaluation(evaluator, tmp_path)
    data = json.loads(evaluation.read_text())
    lf = evaluator.FIXTURES.read_bytes().replace(b"\r\n", b"\n")
    data["fixture_sha256"] = hashlib.sha256(lf).hexdigest()
    evaluation.write_text(json.dumps(data))
    original = tmp_path / "exact-historical-fixture.json"
    original.write_bytes(lf)
    fixture = tmp_path / "fixture-crlf.json"
    fixture.write_bytes(lf.replace(b"\n", b"\r\n"))
    monkeypatch.setattr(evaluator, "FIXTURES", fixture)
    output = tmp_path / "eol-template.json"
    with pytest.raises(ValueError):
        evaluator.review_evaluation(evaluation, None, output)
    assert evaluator.review_evaluation(evaluation, None, output, original) == 0
    assert json.loads(output.read_text())["fixture_sha256"] == data["fixture_sha256"]
