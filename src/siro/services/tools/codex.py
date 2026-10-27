"""Codex as a tool: SIRO's own model stays the mind and hands Codex a task when it needs one.

Codex runs read-only in an empty scratch directory with live web search. Only the task
text is sent (no chat history or memories); its own network use is not visible to SIRO,
and the activity monitor says so. Cancelling the run ends the Codex process group.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from siro.ports.models import ToolDefinition
from siro.services.tools.execution import (
    ExecutionContext,
    execute_bounded_argv,
    restricted_environment,
)

CODEX_TOOL = "codex.ask"
MAX_TASK = 2000
MAX_ANSWER = 8000
TIMEOUT_SECONDS = 240
DEFAULT_MODEL = "gpt-6-luna"
CODEX_DEFINITION = ToolDefinition(
    CODEX_TOOL,
    "Ask Codex, a stronger cloud model that can search the live web, to look something up or "
    "work through a multi-step task. It is read-only and slower than you. Use it for current "
    "facts (weather, news, prices, schedules) or careful research, not for small talk. Send "
    "only the task in your own words; it returns a text answer with source links.",
    {
        "type": "object",
        "properties": {"task": {"type": "string", "minLength": 2, "maxLength": MAX_TASK}},
        "required": ["task"],
        "additionalProperties": False,
    },
)
PROMPT = (
    "你是 SIRO 的研究助手。用繁體中文簡潔回答下面的任務，"  # noqa: RUF001
    "每個事實後面附上你實際讀到的來源網址；不確定就說不確定，不要編造。"  # noqa: RUF001
    "這是唯讀任務，不要修改任何檔案。\n\n任務："  # noqa: RUF001
)

Runner = Callable[..., Awaitable[dict[str, object]]]


class CodexUnavailable(RuntimeError):
    """Codex ran but gave no answer (not logged in, offline, quota or a crash)."""


def codex_binary() -> Path:
    configured = os.environ.get("SIRO_CODEX_BIN")
    return Path(configured) if configured else Path.home() / ".local/codex/node_modules/.bin/codex"


def codex_ready(binary: Path) -> bool:
    """Installed and logged in; this is not proof that a call will succeed."""
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    return binary.is_file() and (home / "auth.json").is_file()


async def ask_codex(
    arguments: dict[str, object],
    context: ExecutionContext | None = None,
    *,
    binary: Path,
    model: str = DEFAULT_MODEL,
    run: Runner = execute_bounded_argv,
) -> dict[str, object]:
    task = arguments.get("task")
    if not isinstance(task, str) or not 2 <= len(task.strip()) <= MAX_TASK:
        raise ValueError("codex.ask requires a task of 2-2000 characters")
    environment = restricted_environment(("CODEX_HOME", "SIRO_CODEX_BIN"))
    with tempfile.TemporaryDirectory(prefix="siro-codex-") as scratch:
        answer_file = Path(scratch) / "answer.txt"
        argv = (
            str(binary),
            "--search",
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "--color",
            "never",
            "-m",
            model,
            "-C",
            scratch,
            "-o",
            str(answer_file),
            PROMPT + task.strip(),
        )
        result = await run(
            argv,
            cwd=Path(scratch),
            environment=environment,
            timeout=TIMEOUT_SECONDS,
            context=context,
        )
        answer = answer_file.read_text(encoding="utf-8").strip() if answer_file.is_file() else ""
    if result.get("returncode") != 0 or not answer:
        raise CodexUnavailable("codex did not return an answer")
    return {"answer": answer[:MAX_ANSWER], "truncated": len(answer) > MAX_ANSWER, "model": model}
