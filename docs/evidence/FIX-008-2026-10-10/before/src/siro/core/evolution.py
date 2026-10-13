"""Isolated patch-proposal verification; production files are never mutated."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatchProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: UUID
    unified_diff: str = Field(min_length=1, max_length=500_000)
    created_at: datetime


@dataclass(frozen=True, slots=True)
class VerificationReport:
    proposal_id: UUID
    status: str
    changed_paths: tuple[str, ...]
    outputs: tuple[str, ...]
    workspace_removed: bool


class PatchVerifier:
    _PROTECTED = frozenset({"src/siro/core/authorization.py", "src/siro/config.py"})

    def __init__(self, checks: tuple[tuple[str, ...], ...]) -> None:
        if not checks or len(checks) > 8 or any(not command for command in checks):
            raise ValueError("trusted verifier requires between one and eight checks")
        self._checks = checks

    def verify(self, project_root: Path, proposal: PatchProposal) -> VerificationReport:
        root = project_root.resolve()
        changed = self._changed_paths(proposal.unified_diff)
        if not changed:
            return VerificationReport(proposal.proposal_id, "rejected_invalid_diff", (), (), True)
        if any(path in self._PROTECTED for path in changed):
            return VerificationReport(
                proposal.proposal_id, "rejected_policy_change", changed, (), True
            )
        before = self._tree_digest(root)
        workspace = Path(tempfile.mkdtemp(prefix="siro-evolution-"))
        outputs: list[str] = []
        try:
            shutil.copytree(
                root,
                workspace / "project",
                ignore=shutil.ignore_patterns(".git", ".venv", "target", "__pycache__", ".siro-*"),
            )
            worktree = workspace / "project"
            self._run(("git", "init", "-q"), worktree, outputs)
            applied = self._run(
                ("git", "apply", "--check", "-"), worktree, outputs, proposal.unified_diff
            )
            if applied != 0:
                return VerificationReport(
                    proposal.proposal_id, "rejected_unappliable", changed, tuple(outputs), True
                )
            self._run(("git", "apply", "-"), worktree, outputs, proposal.unified_diff)
            status = "passed"
            for command in self._checks:
                if self._run(command, worktree, outputs) != 0:
                    status = "failed_checks"
                    break
            if self._tree_digest(root) != before:
                raise RuntimeError("production tree changed during isolated verification")
            # The finally block runs before this value is returned, so callers only
            # receive the report after the temporary workspace has been removed.
            return VerificationReport(proposal.proposal_id, status, changed, tuple(outputs), True)
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    @staticmethod
    def _changed_paths(diff: str) -> tuple[str, ...]:
        paths: list[str] = []
        for line in diff.splitlines():
            if not line.startswith("+++ b/"):
                continue
            path = line.removeprefix("+++ b/")
            candidate = Path(path)
            if candidate.is_absolute() or ".." in candidate.parts or path.startswith(".git/"):
                return ()
            paths.append(path)
        return tuple(dict.fromkeys(paths))

    @staticmethod
    def _run(
        command: tuple[str, ...], cwd: Path, outputs: list[str], input_text: str | None = None
    ) -> int:
        completed = subprocess.run(
            command,
            cwd=cwd,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        outputs.append((completed.stdout + completed.stderr)[-4000:])
        return completed.returncode

    @staticmethod
    def _tree_digest(root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*")):
            if not path.is_file() or any(
                part in {".git", ".venv", "target", "__pycache__"} for part in path.parts
            ):
                continue
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()
