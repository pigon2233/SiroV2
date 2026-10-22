"""Reproduce the preregistered synthetic holdout using the existing MEM02 evaluator."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/context_quality_holdout.json"


def load_evaluator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "holdout_context_evaluator", ROOT / "scripts/evaluate_context_understanding.py"
    )
    assert spec and spec.loader
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    return evaluator


def load_cases() -> list[dict[str, Any]]:
    canonical = hashlib.sha256(FIXTURE.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    cases: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8-sig"))
    if (
        len(cases) != 12
        or canonical != "11d0d021f92137919d08d3bdcc193fc35dc858667e79c47d874b5209e238abd9"
    ):
        raise ValueError("frozen holdout changed")
    return cases


def source_hashes() -> dict[str, str]:
    paths = (
        "scripts/evaluate_context_understanding.py",
        "src/siro/core/context.py",
        "src/siro/core/memory.py",
        "src/siro/core/companion.py",
        "src/siro/core/conversation.py",
        "src/siro/persistence/memory.py",
        "src/siro/adapters/models/ollama.py",
        "src/siro/services/agent/context.py",
        "tests/fixtures/context_quality_holdout.json",
        "docs/verification/MEM02-MODEL-INPUT-FIX/run_holdout.py",
    )
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}


async def run(output: Path, git: str) -> int:
    if output.resolve().is_relative_to(ROOT):
        raise ValueError("output must be a new path outside the source tree")
    evaluator = load_evaluator()
    cases = load_cases()
    canonical = hashlib.sha256(FIXTURE.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if (
        len(cases) != 12
        or canonical != "11d0d021f92137919d08d3bdcc193fc35dc858667e79c47d874b5209e238abd9"
    ):
        raise ValueError("frozen holdout changed")
    backend, profile = evaluator.configured_backend(None)
    data: dict[str, Any] = {
        "mode": "real",
        "synthetic_only": True,
        "source_commit": subprocess.check_output(
            [git, "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_before": source_hashes(),
        "fixture_canonical_sha256": canonical,
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "profile": profile,
        "started_at": datetime.now(UTC).isoformat(),
        "body_review": "REQUIRED",
        "cases": [],
    }
    with output.open("x", encoding="utf-8") as file:
        json.dump(data, file)
    for case in cases:
        result = await evaluator.execute_case(case, backend)
        data["cases"].append(result)
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(case["id"], result["capture_passed"], result["semantic_passed"], flush=True)
        if result["http_status"] is not None:
            break
    data.update(
        source_after=source_hashes(),
        finished_at=datetime.now(UTC).isoformat(),
        capture_passed=sum(row["capture_passed"] for row in data["cases"]),
        automated_passed=sum(row["semantic_passed"] is True for row in data["cases"]),
        complete=len(data["cases"]) == 12,
        state="COMPLETE" if len(data["cases"]) == 12 else "INCOMPLETE",
    )
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1  # Real output still requires explicit, response-bound body review.


def review_result(evaluation: Path, review: Path | None, output: Path) -> int:
    """Reuse the strict common parser; only this frozen 12-case suite has target 11."""
    evaluator = load_evaluator()
    cases = load_cases()
    evaluator.load_cases = lambda: cases
    evaluator.FIXTURES = FIXTURE
    if review is None:
        return int(evaluator.review_evaluation(evaluation, None, output))
    data, _ = evaluator._read_review_json(evaluation)
    if data.get("source_before") != data.get("source_after") or not data.get("source_before"):
        raise ValueError("holdout source changed or source binding missing")
    with tempfile.TemporaryDirectory(prefix="siro-holdout-review-") as temporary:
        common_output = Path(temporary) / "common-review.json"
        evaluator.review_evaluation(evaluation, review, common_output)
        result = json.loads(common_output.read_text())
    # Never apply target 11 to the original 30 cases; load_cases pins the entire new fixture.
    result["suite"] = "frozen_context_quality_holdout_12"
    result["shared_parser_target"] = result["semantic_target"]
    result["semantic_target"] = 11
    passed = result["semantic_passed"] >= 11 and not any(
        row["hard_failed"] for row in result["cases"]
    )
    result["semantic_status"] = "PASS" if passed else "FAILED_VERIFICATION"
    with output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, ensure_ascii=False, indent=2)
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-executable", default="git")
    parser.add_argument("--mode", choices=("real", "review-template", "review"), default="real")
    parser.add_argument("--evaluation", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    if args.mode == "real":
        if args.evaluation or args.review:
            parser.error("review inputs require review mode")
        raise SystemExit(asyncio.run(run(args.output, args.git_executable)))
    if args.evaluation is None or ((args.mode == "review") != (args.review is not None)):
        parser.error("review mode requires evaluation and appropriate review inputs")
    raise SystemExit(review_result(args.evaluation, args.review, args.output))
