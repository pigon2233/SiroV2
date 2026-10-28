"""Claude as a tool: SIRO's own model stays the mind and hands Claude a task when it needs one.

Claude (Haiku, through the logged-in `claude` CLI) answers read-only in an empty scratch
directory, with only the WebSearch tool for the research path. Only the task text is sent (no
chat history or memories); its network use is not visible to SIRO, and the activity monitor
says so. The child gets the restricted environment only. The tool name stays `codex.ask` so
saved runs, the catalog and the UI keep working.
"""

from __future__ import annotations

import json
import os
import shutil
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
DEFAULT_MODEL = "claude-haiku-5-5"
SYSTEM_PROMPT = "Answer the user's task directly and briefly. Do not ask questions."
Runner = Callable[..., Awaitable[dict[str, object]]]
CODEX_DEFINITION = ToolDefinition(
    CODEX_TOOL,
    "Ask Claude, a stronger cloud model that can search the live web, to look something up or "
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


class CodexUnavailable(RuntimeError):
    """Claude gave no answer (not logged in, offline, quota or a crash)."""


def claude_model() -> str:
    return os.environ.get("SIRO_CLAUDE_MODEL") or DEFAULT_MODEL


def claude_binary() -> Path | None:
    configured = os.environ.get("SIRO_CLAUDE_BIN")
    found = configured or shutil.which("claude")
    if not found:
        # The launcher PATH has no Windows side; WSL can still run the npm-installed CLI.
        shims = sorted(Path("/mnt/c/Users").glob("*/AppData/Roaming/npm/claude"))
        found = str(shims[0]) if shims else None
    return Path(found) if found else None


def claude_ready(binary: Path | None = None) -> bool:
    """The CLI is installed; login is only proven by a call that succeeds."""
    binary = binary or claude_binary()
    return binary is not None and binary.is_file()


async def ask_claude(
    arguments: dict[str, object],
    context: ExecutionContext | None = None,
    *,
    model: str = DEFAULT_MODEL,
    binary: Path | None = None,
    run: Runner = execute_bounded_argv,
    prefix: str = PROMPT,
    limit: int = MAX_TASK,
    search: bool = True,
) -> dict[str, object]:
    task = arguments.get("task")
    if not isinstance(task, str) or not 2 <= len(task.strip()) <= limit:
        raise ValueError("codex.ask requires a task of 2-2000 characters")
    binary = binary or claude_binary()
    if binary is None:
        raise CodexUnavailable("claude CLI not found")
    environment = restricted_environment(("SIRO_CLAUDE_BIN", "CLAUDE_CONFIG_DIR"))
    with tempfile.TemporaryDirectory(prefix="siro-claude-") as scratch:
        argv = (
            str(binary),
            "-p",
            "--model",
            model,
            "--output-format",
            "json",
            "--tools",
            "WebSearch" if search else "",
            "--system-prompt",
            SYSTEM_PROMPT,
            *(("--allowedTools", "WebSearch") if search else ()),
            "--no-session-persistence",
            prefix + task.strip(),
        )
        result = await run(
            argv,
            cwd=Path(scratch),
            environment=environment,
            timeout=TIMEOUT_SECONDS,
            context=context,
        )
    answer = ""
    if result.get("returncode") == 0:
        try:
            parsed = json.loads(str(result.get("stdout", "")))
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and not parsed.get("is_error"):
            answer = str(parsed.get("result") or "").strip()
    if not answer:
        raise CodexUnavailable("claude did not return an answer")
    return {"answer": answer[:MAX_ANSWER], "truncated": len(answer) > MAX_ANSWER, "model": model}
