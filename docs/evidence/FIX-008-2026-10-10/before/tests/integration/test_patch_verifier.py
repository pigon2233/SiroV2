from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from siro.core.evolution import PatchProposal, PatchVerifier


def proposal(diff: str) -> PatchProposal:
    return PatchProposal(
        proposal_id=uuid4(),
        unified_diff=diff,
        created_at=datetime(2026, 9, 26, 14, tzinfo=UTC),
    )


def test_t31_pass_fail_and_policy_protection_stay_outside_production(tmp_path: Path) -> None:
    root = tmp_path / "production"
    root.mkdir()
    (root / "calc.py").write_text("VALUE = 1\n", encoding="utf-8")
    policy = root / "src/siro/core"
    policy.mkdir(parents=True)
    (policy / "authorization.py").write_text("POLICY = 'deny'\n", encoding="utf-8")
    before = (root / "calc.py").read_text(encoding="utf-8")
    passing_verifier = PatchVerifier(
        ((sys.executable, "-c", "from calc import VALUE; assert VALUE == 2"),)
    )
    passing = passing_verifier.verify(
        root,
        proposal(
            "--- a/calc.py\n+++ b/calc.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n",
        ),
    )
    assert passing.status == "passed"
    assert passing.workspace_removed is True
    assert (root / "calc.py").read_text(encoding="utf-8") == before

    failing_verifier = PatchVerifier(
        ((sys.executable, "-c", "from calc import VALUE; assert VALUE == 2"),)
    )
    failing = failing_verifier.verify(
        root,
        proposal(
            "--- a/calc.py\n+++ b/calc.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 3\n",
        ),
    )
    assert failing.status == "failed_checks"
    assert failing.workspace_removed is True
    assert (root / "calc.py").read_text(encoding="utf-8") == before

    protected = passing_verifier.verify(
        root,
        proposal(
            "--- a/src/siro/core/authorization.py\n+++ b/src/siro/core/authorization.py\n"
            "@@ -1 +1 @@\n-POLICY = 'deny'\n+POLICY = 'allow'\n",
        ),
    )
    assert protected.status == "rejected_policy_change"
    assert (policy / "authorization.py").read_text(encoding="utf-8") == "POLICY = 'deny'\n"
