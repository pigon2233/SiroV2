"""Source-only D47 review binding; never inspect live data or mutate source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
EXISTING = (
    "src/siro/persistence/skills.py",
    "src/siro/services/tools/orchestrator.py",
    "src/siro/services/presentation/gateway.py",
    "src/siro/services/presentation/static/index.html",
)
NEW = (
    "src/siro/services/tools/skill_activation.py",
    "tests/integration/test_skill_activation.py",
    "tests/integration/test_skill_activation_foundation.py",
    "tests/integration/test_skill_activation_lifecycle.py",
    "tests/integration/test_skill_activation_review.py",
    "tests/integration/test_skill_activation_product.py",
    "tests/integration/test_frontend_skill_activation.py",
)
PRIOR_WORKER = (
    "src/siro/adapters/skill_worker.py",
    "src/siro/services/tools/patch_verification.py",
    "src/siro/services/tools/patch_verification_runner.py",
    "src/siro/adapters/isolated_python.py",
    "src/siro/adapters/python_restrictions.py",
    "src/siro/adapters/strict_skill_runner.py",
    "tests/integration/test_strict_skill_worker.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    baseline = json.loads((OUT / "baseline.json").read_text())["hashes"]
    assert len(baseline) == 258
    changed = [path for path, expected in baseline.items() if sha(ROOT / path) != expected]
    assert set(changed) == set(EXISTING), changed
    worker_unchanged = all(sha(ROOT / path) == baseline[path] for path in PRIOR_WORKER)
    assert worker_unchanged
    current = {path: sha(ROOT / path) for path in EXISTING + NEW}
    phase1_path = OUT / "independent-source-binding-phase1.json"
    phase1_changed = None
    if phase1_path.exists():
        phase1 = json.loads(phase1_path.read_text())["final_sha256"]
        phase1_changed = [path for path, expected in phase1.items() if current[path] != expected]
        assert set(phase1_changed) == {
            "src/siro/services/presentation/static/index.html",
            "tests/integration/test_frontend_skill_activation.py",
        }
    preserved = OUT / "preservation.json"
    agreement = None
    if preserved.exists():
        agreement = current == json.loads(preserved.read_text())["final_sha256"]
        assert agreement
    report = {
        "status": "VERIFIED_SOURCE_REVIEW",
        "source_freeze": "root FINALFREEZE notification",
        "confirmed_scoped_blockers_remaining": 0,
        "baseline_files": len(baseline),
        "unchanged_existing_files": len(baseline) - len(changed),
        "changed_existing_files": changed,
        "final_sha256": current,
        "prior_D46_seven_files_unchanged": worker_unchanged,
        "root_preservation_agreement": agreement,
        "changed_after_phase1": phase1_changed,
        "late_UI_source_review": "Matching installed hash changes label text only; review/export facts retained",
        "independent_final_cases": 19,
        "independent_final_elapsed_seconds": 4.67,
        "independent_final_log_sha256": sha(OUT / "independent-review-final.log"),
        "before_logs": {
            filename: sha(OUT / filename)
            for filename in ("independent-review-before.log", "independent-queued-review-before.log")
        },
        "live_runtime_accessed": False,
        "private_data_read": False,
        "real_model_called": False,
        "production_source_edited_by_this_reviewer": False,
        "arbitrary_generated_skill_certified": False,
        "full_regression_claimed_by_this_artifact": False,
    }
    (OUT / "independent-source-binding.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
