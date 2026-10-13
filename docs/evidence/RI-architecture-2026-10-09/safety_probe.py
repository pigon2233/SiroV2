"""Synthetic audit counterexamples; never reads or mutates the real SIRO data tree."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from siro.adapters.skill_worker import SkillDispatcher
from siro.core.evolution import PatchProposal, PatchVerifier
from siro.core.releases import ReleaseManager, ReleaseManifest
from siro.core.skills import load_skill
from siro.persistence.skills import SQLiteSkillRegistry
from siro.persistence.sqlite import SQLiteStore


def patch(diff: str) -> PatchProposal:
    return PatchProposal(proposal_id=uuid4(), unified_diff=diff, created_at=datetime.now(UTC))


async def skill_probe(root: Path) -> dict[str, object]:
    root.mkdir()
    manifest = {
        "id": "audit.fixture",
        "version": "1.0.0",
        "contract_version": 1,
        "description": "Synthetic audit fixture",
        "entrypoint": "python:plugin:run",
        "input_schema": "input.json",
        "output_schema": "output.json",
        "permissions": [{"capability": "fixture.read", "scope_required": "fixture"}],
        "risk": "observe",
        "timeout_ms": 1000,
        "concurrency": 1,
        "resource_limits": {"memory_mb": 64, "output_bytes": 1024, "cpu_seconds": 1},
        "network": "denied",
        "idempotency": "read_only",
        "cancellation": "process",
        "compensation": "none",
    }
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    (root / "manifest.json").write_text(json.dumps(manifest))
    for name in ("input.json", "output.json"):
        (root / name).write_text(json.dumps(schema))
    (root / "plugin.py").write_text("def run(arguments): return {}\n")
    before = load_skill(root)
    store = SQLiteStore(root.parent / "fixture.sqlite3")
    await store.initialize()
    registry = SQLiteSkillRegistry(store)
    await registry.install(before, enabled=True)
    (root / "plugin.py").write_text("def run(arguments): raise RuntimeError('changed')\n")
    after = load_skill(root)

    class RecordingSupervisor:
        called = False

        async def execute(self, skill: object, arguments: object) -> dict[str, object]:
            self.called = True
            return {}

    supervisor = RecordingSupervisor()
    await SkillDispatcher(registry, supervisor).execute(after, {})  # type: ignore[arg-type]
    return {
        "code_change_preserves_manifest_hash": before.manifest_hash == after.manifest_hash,
        "changed_code_object_reaches_supervisor": supervisor.called,
        "execution": "recording fake supervisor only; no generated code executed",
    }


def patch_probe(root: Path) -> dict[str, object]:
    root.mkdir()
    (root / "calc.py").write_text("VALUE = 1\n")
    policy = root / "src/siro/core/authorization.py"
    policy.parent.mkdir(parents=True)
    policy.write_text("POLICY = 'deny'\n")
    verifier = PatchVerifier(((sys.executable, "-c", "from calc import VALUE; assert VALUE == 2"),))
    deletion = verifier.verify(
        root,
        patch(
            "--- a/calc.py\n+++ b/calc.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
            "--- a/src/siro/core/authorization.py\n+++ /dev/null\n"
            "@@ -1 +0,0 @@\n-POLICY = 'deny'\n"
        ),
    )
    marker = root.parent / "outside-copy.txt"
    injection = f"from pathlib import Path; Path({str(marker)!r}).write_text('synthetic')"
    escaped = verifier.verify(
        root,
        patch(
            "--- a/calc.py\n+++ b/calc.py\n@@ -1 +1,2 @@\n-VALUE = 1\n"
            f"+{injection}\n+VALUE = 2\n"
        ),
    )
    return {
        "protected_delete_status": deletion.status,
        "protected_delete_reported_paths": deletion.changed_paths,
        "same_user_test_writes_outside_copy": marker.exists(),
        "outside_copy_check_status": escaped.status,
        "original_fixture_files_unchanged": policy.read_text() == "POLICY = 'deny'\n"
        and (root / "calc.py").read_text() == "VALUE = 1\n",
    }


def release_probe(root: Path) -> dict[str, object]:
    bundle = root / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "app.txt").write_text("synthetic")
    key = b"synthetic-audit-key"
    manager = ReleaseManager(root / "manager", key, current_schema=8)
    digest = manager._digest(bundle)
    original = ReleaseManifest(
        version="1.0.0",
        source_sha256=digest,
        signature=hmac.new(key, f"1.0.0:{digest}".encode(), hashlib.sha256).hexdigest(),
        min_schema=1,
        max_schema=2,
    )
    changed = original.model_copy(update={"max_schema": 8})
    result = manager.stage_and_activate(bundle, changed, (sys.executable, "-c", "pass"))
    return {
        "original_schema_compatible": manager._compatible(original),
        "schema_bounds_changed_without_resigning": changed.signature == original.signature,
        "altered_manifest_activation_status": result.status,
        "execution": "temporary synthetic release directory only",
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="siro-ri-audit-") as directory:
        root = Path(directory)
        result = {
            "date": "2026-10-09",
            "scope": "synthetic fixtures only; no private DB, service, GPU or network",
            "skill": asyncio.run(skill_probe(root / "skill")),
            "patch": patch_probe(root / "project"),
            "release": release_probe(root / "release"),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
