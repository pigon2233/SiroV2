"""Synthetic candidate preparation to actual strict worker; no install or enable."""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import time
from pathlib import Path

from siro.adapters.skill_worker import WorkerSupervisor
from siro.core.skills import load_skill
from siro.services.tools.orchestrator import ToolCatalog
from siro.services.tools.skill_candidates import CAPABILITY, SkillCandidatePreparer


async def main() -> None:
    owner = SkillCandidatePreparer(ToolCatalog([]))
    started = time.monotonic()
    try:
        review = await owner.prepare(CAPABILITY)
        assert review["status"] == "awaiting_review"
        assert review["verification"]["status"] == "passed"
        assert not review["enabled"] and not review["installed"]
        assert not review["authorizes_execution"]
        with tempfile.TemporaryDirectory(prefix="siro-strict-checklist-") as directory:
            root = Path(directory).resolve()
            for name, contents in review["files"].items():
                assert name in {"manifest.json", "input.json", "output.json", "plugin.py"}
                (root / name).write_text(contents, encoding="utf-8")
            skill = load_skill(root)
            assert skill.manifest_hash == review["package_hash"]
            result = await WorkerSupervisor(profile="python-stdlib-single").execute(
                skill,
                {"text": "- [ ] 買牛奶\n* [x] 已完成\n```\n- [ ] hidden\n```\n+ [X] 測試"},
            )
            expected = {
                "pending": ["買牛奶"],
                "completed": ["已完成", "測試"],
                "pending_count": 1,
                "completed_count": 2,
            }
            assert result == expected
            assert load_skill(root) == skill
            payload = {
                "status": "PASS",
                "scope": "actual candidate preparation plus actual strict worker; synthetic data",
                "profile": "python-stdlib-single",
                "elapsed_seconds": round(time.monotonic() - started, 4),
                "package_hash": skill.manifest_hash,
                "candidate_source_sha256": hashlib.sha256((root / "plugin.py").read_bytes()).hexdigest(),
                "verification": review["verification"]["status"],
                "output": result,
                "package_unchanged": True,
                "registry_installed": False,
                "product_enabled": False,
                "live_service_touched": False,
                "private_data_used": False,
            }
    finally:
        await owner.close()
    assert not root.exists()
    payload["temporary_package_removed"] = True
    output = Path(__file__).with_name("actual-worker.json")
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
