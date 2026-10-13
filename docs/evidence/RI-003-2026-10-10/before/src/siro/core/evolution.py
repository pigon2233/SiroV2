"""Isolated patch-proposal verification; production files are never mutated."""

from __future__ import annotations

import hashlib
import re
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
        """Validate the complete bounded text dialect before trusting either path."""

        def path(value: str) -> str:
            if (
                not value
                or any(
                    char.isspace() or ord(char) < 32 or 127 <= ord(char) <= 159 or char in '\\"'
                    for char in value
                )
                or any(part in {"", ".", "..", ".git"} for part in value.split("/"))
            ):
                raise ValueError("unsupported path")
            return value

        def header(line: str, marker: str, prefix: str) -> str | None:
            if not line.startswith(marker):
                raise ValueError("missing paired header")
            value = line[len(marker) :]
            if value == "/dev/null":
                return None
            if not value.startswith(prefix):
                raise ValueError("unsupported header")
            return path(value[len(prefix) :])

        # Split only on actual diff line separators, never payload control characters.
        if len(diff) > 500_000 or not diff.endswith("\n") or "\r" in diff or "\0" in diff:
            return ()
        lines = diff[:-1].split("\n")
        paths: list[str] = []
        position = 0
        try:
            while position < len(lines):
                git_paths: tuple[str, str] | None = None
                metadata: dict[str, str] = {}
                if lines[position].startswith("diff --git "):
                    match = re.fullmatch(r"diff --git a/(\S+) b/(\S+)", lines[position])
                    if match is None:
                        raise ValueError("unsupported git header")
                    git_paths = (path(match[1]), path(match[2]))
                    position += 1
                    while position < len(lines) and not lines[position].startswith("--- "):
                        line = lines[position]
                        if re.fullmatch(
                            r"index [0-9a-fA-F]{4,64}\.\.[0-9a-fA-F]{4,64}(?: 100(?:644|755))?",
                            line,
                        ):
                            key, value = "index", line
                        elif re.fullmatch(r"(?:new file|deleted file) mode 100(?:644|755)", line):
                            key, value = "file_mode", line.split(" mode ")[0]
                        elif line.startswith("rename from "):
                            key, value = "rename_from", path(line[len("rename from ") :])
                        elif line.startswith("rename to "):
                            key, value = "rename_to", path(line[len("rename to ") :])
                        elif re.fullmatch(r"similarity index (?:[0-9]|[1-9][0-9]|100)%", line):
                            key, value = "similarity", line
                        else:
                            raise ValueError("unsupported metadata")
                        if key in metadata:
                            raise ValueError("duplicate metadata")
                        metadata[key] = value
                        position += 1
                if position + 1 >= len(lines):
                    raise ValueError("truncated file headers")
                old = header(lines[position], "--- ", "a/")
                new = header(lines[position + 1], "+++ ", "b/")
                position += 2
                if old is None and new is None:
                    raise ValueError("missing changed path")
                if git_paths is not None and git_paths != (old or new, new or old):
                    raise ValueError("conflicting file identity")
                renamed = old is not None and new is not None and old != new
                if renamed:
                    if git_paths is None or (
                        metadata.get("rename_from"),
                        metadata.get("rename_to"),
                    ) != (old, new):
                        raise ValueError("incomplete rename identity")
                elif any(key in metadata for key in ("rename_from", "rename_to", "similarity")):
                    raise ValueError("unexpected rename metadata")
                file_mode = metadata.get("file_mode")
                if file_mode is not None and (
                    renamed
                    or (file_mode == "new file" and old is not None)
                    or (file_mode == "deleted file" and new is not None)
                ):
                    raise ValueError("conflicting file mode")
                hunks = 0
                while position < len(lines) and lines[position].startswith("@@ "):
                    match = re.fullmatch(
                        r"@@ -[0-9]+(?:,([0-9]+))? \+[0-9]+(?:,([0-9]+))? @@(?: .*)?",
                        lines[position],
                    )
                    if match is None:
                        raise ValueError("unsupported hunk header")
                    old_left = int(match[1]) if match[1] is not None else 1
                    new_left = int(match[2]) if match[2] is not None else 1
                    if old_left + new_left == 0 or max(old_left, new_left) > 500_000:
                        raise ValueError("invalid hunk counts")
                    if (old is None and old_left) or (new is None and new_left):
                        raise ValueError("nonempty null side")
                    position += 1
                    while old_left or new_left:
                        if position >= len(lines) or not lines[position]:
                            raise ValueError("truncated hunk")
                        marker = lines[position][0]
                        if marker not in " +-":
                            raise ValueError("invalid hunk line")
                        old_left -= marker in " -"
                        new_left -= marker in " +"
                        if old_left < 0 or new_left < 0:
                            raise ValueError("inconsistent hunk counts")
                        position += 1
                        if (
                            position < len(lines)
                            and lines[position] == "\\ No newline at end of file"
                        ):
                            position += 1
                    hunks += 1
                if not hunks:
                    raise ValueError("missing text hunks")
                paths.extend(value for value in (old, new) if value is not None)
        except ValueError:
            return ()
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
