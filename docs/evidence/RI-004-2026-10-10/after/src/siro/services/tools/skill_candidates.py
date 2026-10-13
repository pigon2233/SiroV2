"""Explicit-owner, fixed-template skill preparation; never install or execute skills."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from siro.core.evolution import PatchProposal
from siro.core.skills import capture_skill
from siro.services.tools.execution import ExecutionCleanupError
from siro.services.tools.orchestrator import ToolCatalog
from siro.services.tools.patch_verification import verify_isolated_patch

CAPABILITY = "text.checklist.parse"
PROFILE = "markdown-checklist-v1"
_ALIASES = frozenset({CAPABILITY, "siro.text.checklist", "skill.siro.text.checklist"})

_PLUGIN = '''"""Bounded pasted-text checklist parser; no filesystem or network input."""
import re

def run(arguments):
    if not isinstance(arguments, dict) or set(arguments) != {"text"}:
        raise ValueError("only text is accepted")
    text = arguments["text"]
    if not isinstance(text, str) or len(text.encode("utf-8")) > 16384:
        raise ValueError("text exceeds its type or byte limit")
    lines = text.splitlines()
    if len(lines) > 256:
        raise ValueError("too many lines")
    pending, completed = [], []
    fence = None
    for line in lines:
        stripped = line.lstrip()
        marker = ("```" if stripped.startswith("```") else
                  "~~~" if stripped.startswith("~~~") else None)
        if marker:
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is not None:
            continue
        match = re.fullmatch(r"\\s*[-*+]\\s+\\[([ xX])\\]\\s+(.+)", line)
        if match is None:
            continue
        item = match[2].strip()
        if not item:
            continue
        if len(item) > 256 or len(pending) + len(completed) >= 128:
            raise ValueError("task limit exceeded")
        (pending if match[1] == " " else completed).append(item)
    return {"pending": pending, "completed": completed,
            "pending_count": len(pending), "completed_count": len(completed)}
'''

# Trusted tests stay outside the package and are projected independently of candidate bytes.
_TESTS = """import unittest
from plugin import run

class ChecklistTests(unittest.TestCase):
    def test_items_and_counts(self):
        text = "- [ ] 買牛奶\\n* [x] done\\n+ [X] 測試\\nordinary\\n- [ ]  "
        self.assertEqual(run({"text": text}),
                         {"pending": ["買牛奶"], "completed": ["done", "測試"],
                          "pending_count": 1, "completed_count": 2})
    def test_fences(self):
        text = "```python\\n- [ ] hidden\\n```\\n~~~\\n* [x] hidden\\n~~~\\n- [ ] visible"
        self.assertEqual(run({"text": text})["pending"], ["visible"])
    def test_empty(self):
        self.assertEqual(run({"text": ""}), {"pending": [], "completed": [],
                                           "pending_count": 0, "completed_count": 0})
    def test_invalid_objects(self):
        for value in (None, [], {}, {"text": False}, {"text": "", "path": "/etc/passwd"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run(value)
    def test_over_limits(self):
        for text in ("a" * 16385, "界" * 5462, "\\n" * 257, "- [ ] " + "a" * 257,
                     "\\n".join("- [ ] a" for _ in range(129))):
            with self.subTest(length=len(text)), self.assertRaises(ValueError):
                run({"text": text})
    def test_exact_limits(self):
        text = "\\n".join("- [ ] a" for _ in range(128))
        self.assertEqual(len(run({"text": text})["pending"]), 128)
        self.assertEqual(run({"text": "- [ ] " + "a" * 256})["pending_count"], 1)
        self.assertEqual(run({"text": "\\n" * 256})["pending_count"], 0)
        self.assertEqual(run({"text": "a" * 16384})["pending_count"], 0)
"""


class SkillCandidateBusy(RuntimeError):
    """An explicit owner preparation is already active; no queue is created."""


class SkillCandidateClosed(RuntimeError):
    """The service owner has shut down."""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _package_files() -> dict[str, str]:
    return {
        "manifest.json": _json(
            {
                "id": "siro.text.checklist",
                "version": "1.0.0",
                "contract_version": 1,
                "description": "Parse a pasted Markdown checklist into pending/completed tasks.",
                "entrypoint": "python:plugin:run",
                "input_schema": "input.json",
                "output_schema": "output.json",
                "permissions": [],
                "risk": "observe",
                "timeout_ms": 1000,
                "concurrency": 1,
                "resource_limits": {"memory_mb": 256, "output_bytes": 131072, "cpu_seconds": 5},
                "network": "denied",
                "idempotency": "read_only",
                "cancellation": "process",
                "compensation": "none",
            }
        ),
        "input.json": _json(
            {
                "type": "object",
                "properties": {"text": {"type": "string", "maxLength": 16384}},
                "required": ["text"],
                "additionalProperties": False,
            }
        ),
        "output.json": _json(
            {
                "type": "object",
                "properties": {
                    "pending": {
                        "type": "array",
                        "maxItems": 128,
                        "items": {"type": "string", "maxLength": 256},
                    },
                    "completed": {
                        "type": "array",
                        "maxItems": 128,
                        "items": {"type": "string", "maxLength": 256},
                    },
                    "pending_count": {"type": "integer", "minimum": 0, "maximum": 128},
                    "completed_count": {"type": "integer", "minimum": 0, "maximum": 128},
                },
                "required": ["pending", "completed", "pending_count", "completed_count"],
                "additionalProperties": False,
            }
        ),
        "plugin.py": _PLUGIN,
    }


@dataclass(frozen=True, slots=True)
class _Workspace:
    root: Path
    proposal: PatchProposal
    files: dict[str, str]
    package_hash: str


def _remove_workspace(root: Path) -> None:
    try:
        shutil.rmtree(root)
    except OSError as error:
        raise ExecutionCleanupError("skill candidate workspace cleanup failed") from error


def _build_workspace() -> _Workspace:
    root = Path(tempfile.mkdtemp(prefix="siro-skill-candidate-")).resolve()
    try:
        package = root / "package"
        package.mkdir()
        expected = _package_files()
        for name, text in expected.items():
            (package / name).write_text(text, encoding="utf-8")
            (package / name).chmod(0o600)
        skill, captured = capture_skill(package)
        if set(captured) != set(expected) or any(
            data != expected[name].encode("utf-8") or mode != 0
            for name, (data, mode) in captured.items()
        ):
            raise ValueError("fixed template package changed during capture")
        files = {name: data.decode("utf-8") for name, (data, _) in captured.items()}
        projection = root / "projection"
        (projection / "src").mkdir(parents=True)
        (projection / "tests").mkdir()
        (projection / "tests/test_checklist.py").write_text(_TESTS, encoding="utf-8")
        lines = files["plugin.py"].splitlines(keepends=True)
        diff = (
            "diff --git a/src/plugin.py b/src/plugin.py\nnew file mode 100644\n"
            "--- /dev/null\n+++ b/src/plugin.py\n"
            f"@@ -0,0 +1,{len(lines)} @@\n" + "".join("+" + line for line in lines)
        )
        proposal = PatchProposal(
            proposal_id=uuid4(), unified_diff=diff, created_at=datetime.now(UTC)
        )
        return _Workspace(root, proposal, files, skill.manifest_hash)
    except BaseException:
        _remove_workspace(root)
        raise


async def _join_owned[T](task: asyncio.Task[T]) -> T:
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


async def _workspace() -> _Workspace:
    preparation = asyncio.create_task(asyncio.to_thread(_build_workspace))
    try:
        return await asyncio.shield(preparation)
    except asyncio.CancelledError:
        workspace = await _join_owned(preparation)
        await _join_owned(asyncio.create_task(asyncio.to_thread(_remove_workspace, workspace.root)))
        raise


class SkillCandidatePreparer:
    def __init__(self, catalog: ToolCatalog) -> None:
        self._catalog = catalog
        self._active: asyncio.Task[dict[str, object]] | None = None
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._active is not None and not self._active.done()

    async def prepare(self, capability: str) -> dict[str, object]:
        if self._closed:
            raise SkillCandidateClosed("skill candidate owner closed")
        if self.busy:
            raise SkillCandidateBusy("skill candidate preparation busy")
        job = asyncio.create_task(self._prepare(capability))
        self._active = job
        try:
            return await asyncio.shield(job)
        except asyncio.CancelledError:
            job.cancel()
            with suppress(asyncio.CancelledError):
                await _join_owned(job)
            raise
        finally:
            if self._active is job:
                self._active = None

    async def cancel(self) -> bool:
        job = self._active
        if job is None or job.done():
            return False
        job.cancel()
        with suppress(asyncio.CancelledError):
            await _join_owned(job)
        return True

    async def close(self) -> None:
        self._closed = True
        await self.cancel()

    async def _prepare(self, capability: str) -> dict[str, object]:
        snapshot = self._catalog.capture()
        result: dict[str, object] = {
            "capability": capability,
            "profile": PROFILE,
            "source": f"siro_builtin_template:{PROFILE}",
            "trust_level": "unreviewed",
            "enabled": False,
            "installed": False,
            "authorizes_execution": False,
            "approval_required": True,
            "catalog_checked_at": snapshot.checked_at,
        }
        aliases = _ALIASES if capability in _ALIASES else frozenset({capability})
        for row in snapshot.inventory:
            if row["name"] == "computer.execute":
                result["general_alternative"] = dict(row)
        for row in snapshot.inventory:
            if row["name"] in aliases:
                result.update(status="existing_" + str(row["availability"]), existing=dict(row))
                return result
        if capability not in _ALIASES:
            result["status"] = "unsupported_capability"
            return result
        workspace = await _workspace()
        try:
            report = await verify_isolated_patch(workspace.root / "projection", workspace.proposal)
            bound = (
                report.proposal_id == workspace.proposal.proposal_id
                and report.changed_paths == ("src/plugin.py",)
                and report.workspace_removed
                and sum(len(output.encode("utf-8")) for output in report.outputs) <= 65536
            )
            result.update(
                status="awaiting_review"
                if bound and report.status == "passed"
                else "verification_failed",
                package_hash=workspace.package_hash,
                source_sha256=hashlib.sha256(workspace.files["plugin.py"].encode()).hexdigest(),
                tests_sha256=hashlib.sha256(_TESTS.encode()).hexdigest(),
                proposal_sha256=hashlib.sha256(
                    workspace.proposal.unified_diff.encode()
                ).hexdigest(),
                proposal_id=str(workspace.proposal.proposal_id),
                files=workspace.files,
                verification={
                    "proposal_id": str(report.proposal_id),
                    "status": report.status if bound else "binding_mismatch",
                    "changed_paths": list(report.changed_paths),
                    "workspace_removed": report.workspace_removed,
                    "outputs": list(report.outputs) if bound else [],
                },
            )
        finally:
            cleanup = asyncio.create_task(asyncio.to_thread(_remove_workspace, workspace.root))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await _join_owned(cleanup)
                raise
        return result
