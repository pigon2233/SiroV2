"""Pure patch preflight and legacy trusted-check workspace verification."""

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


def propose_runtime_improvement(fact: dict[str, object] | None) -> dict[str, object] | None:
    """Compose one investigation view from a D41 fact, without executing or writing."""
    if fact is None or set(fact) != {
        "source_run_id",
        "state",
        "error_class",
        "tool_dispatch_recorded",
        "root_cause",
    }:
        return None
    source = fact["source_run_id"]
    if (
        not isinstance(source, str)
        or fact["state"] != "failed"
        or fact["error_class"] != "HTTPStatusError"
        or fact["root_cause"] != "UNKNOWN"
        or type(fact["tool_dispatch_recorded"]) is not bool
    ):
        return None
    try:
        if str(UUID(source)) != source:
            return None
    except ValueError:
        return None
    return {
        "schema_version": 1,
        "proposal_id": f"RI-006:{source}:http-status-v1",
        "source_task": "RI-006",
        "classification": "DEFER",
        "evidence": dict(fact),
        "root_cause": "UNKNOWN — NEEDS INVESTIGATION",
        "problem": "最近一筆可追溯的對話執行失敗，記錄的錯誤類別是 HTTPStatusError。",  # noqa: RUF001
        "expected_behavior": "請求失敗時清楚保留已知與未知，讓下一次互動仍可繼續。",  # noqa: RUF001
        "actual_behavior": "紀錄只有失敗狀態與錯誤類別，尚無足夠證據確認 HTTP 狀態碼或出錯元件。",  # noqa: RUF001
        "scope": "先以合成請求調查 HTTP 錯誤的來源邊界；確認根因後才定義最小局部修復。",  # noqa: RUF001
        "files_expected_to_change": [],
        "files_must_not_change": [
            "src/siro/core/authorization.py",
            "src/siro/config.py",
            "src/siro/persistence/migrations/",
        ],
        "compatibility_requirements": (
            "保留既有介面、取消、授權與結果未知語意；不重播工具或覆蓋記憶。"  # noqa: RUF001
        ),
        "proposed_repair": "目前只提出調查；未確認根因前不生成修改差異，也不建立立即修復任務。",  # noqa: RUF001
        "tests_required": [
            "以合成 HTTP 失敗確認實際呼叫邊界，記錄安全類別與關聯 run，不使用私人請求內容。",  # noqa: RUF001
            "確認錯誤、取消與下一輪正常回覆；不自動重送可能已產生效果的動作。",  # noqa: RUF001
            "重查來源：更正、刪除、過期或新執行紀錄使此建議失效。",  # noqa: RUF001
        ],
        "regression_tests": [
            "A01：串流有序且只有一個結束事件。",  # noqa: RUF001
            "A02：取消後舊輸出不能復活。",  # noqa: RUF001
            "A14：權限檢查與審計保留。",  # noqa: RUF001
        ],
        "acceptance_criteria": [
            "先建立可重現情境與實際根因證據；無證據時保持根因未知。",  # noqa: RUF001
            "確認最小修復範圍、原行為與回退方式，才交人工審核。",  # noqa: RUF001
        ],
        "rollback_method": "可撤除此提案入口，保留原始 journal、對話、記憶與既有版本。",  # noqa: RUF001
        "risk": (
            "有工具派送紀錄，但不能據此確認效果；先回讀結果，不自動重做。"  # noqa: RUF001
            if fact["tool_dispatch_recorded"]
            else "本筆無工具派送紀錄；仍不能由此證明其他效果或診斷語音、網路與模型問題。"  # noqa: RUF001
        ),
        "patch": None,
        "approval_required": True,
        "authorizes_execution": False,
    }


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
        preflight = preflight_patch(proposal)
        if preflight.status != "ready":
            return preflight
        changed = preflight.changed_paths
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


def preflight_patch(proposal: PatchProposal) -> VerificationReport:
    """Validate complete paths without reading source or executing any check."""
    changed = PatchVerifier._changed_paths(proposal.unified_diff)
    status = "ready"
    if not changed:
        status = "rejected_invalid_diff"
    elif any(path in PatchVerifier._PROTECTED for path in changed):
        status = "rejected_policy_change"
    return VerificationReport(proposal.proposal_id, status, changed, (), True)
