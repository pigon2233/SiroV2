"""Claude as a tool: SIRO's own model stays the mind and hands Claude a task when it needs one.

Claude (Haiku, through the logged-in `claude` CLI) answers read-only in an empty scratch
directory, with only the WebSearch tool for the research path. Only the task text is sent (no
chat history or memories); its network use is not visible to SIRO, and the activity monitor
says so. The child gets the restricted environment only. The tool name stays `claude.ask` so
saved runs, the catalog and the UI keep working. A ``caller`` label shares the process-wide
Claude budget: over budget or during a rate-limit cooldown the CLI is not started.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from siro.adapters.models.claude_budget import (
    BudgetView,
    ClaudeBudget,
    block_message,
    claude_timeout_seconds,
    observe_cli_rate_limit,
    shared_claude_budget,
)
from siro.ports.models import (
    CancellationToken,
    LanguageModel,
    ModelRequest,
    Privacy,
    ToolDefinition,
)
from siro.services.tools.execution import (
    ExecutionContext,
    execute_bounded_argv,
    restricted_environment,
)

_LOG = logging.getLogger(__name__)
CLAUDE_TOOL = "claude.ask"
MAX_TASK = 2000
MAX_ANSWER = 8000
DEFAULT_MODEL = "claude-haiku-5-5"
# Addressee and the auto-plan classifier already fall back locally. Other guarded
# callers try Groq, then Ollama, before reporting that Claude is unavailable.
_RULE_CALLERS = frozenset({"addressee", "auto_plan"})
Fallback = Callable[[str], Awaitable[tuple[str, str]]]
SYSTEM_PROMPT = "Answer the user's task directly and briefly. Do not ask questions."
Runner = Callable[..., Awaitable[dict[str, object]]]
CLAUDE_DEFINITION = ToolDefinition(
    CLAUDE_TOOL,
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


class ClaudeUnavailable(RuntimeError):
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


def fallback_targets(env: Mapping[str, str] | None = None) -> list[tuple[str, str]]:
    """Ordered ``(label, kind)`` pairs: OpenAI-compatible (Groq), then local Ollama."""
    values = os.environ if env is None else env
    found: list[tuple[str, str]] = []
    cloud_key = values.get("SIRO_OPENAI_API_KEY")
    cloud_model = values.get("SIRO_OPENAI_MODEL")
    if cloud_key and cloud_model:
        base_url = values.get("SIRO_OPENAI_BASE_URL", "https://api.groq.com/openai")
        host = urlsplit(base_url).hostname or ""
        label = f"groq:{cloud_model}" if host == "api.groq.com" else f"cloud:{cloud_model}"
        found.append((label, "openai"))
    local = values.get("SIRO_OLLAMA_MODEL") or values.get("SIRO_LOCAL_FALLBACK_OLLAMA_MODEL")
    if local:
        found.append((f"ollama:{local}", "ollama"))
    return found


async def _collect_text(model: LanguageModel, prompt: str, privacy: Privacy) -> str:
    request = ModelRequest(prompt, str(uuid4()), privacy, max_output_tokens=1536)
    parts: list[str] = []
    async for chunk in model.stream(request, CancellationToken()):
        if chunk.kind == "text" and chunk.text:
            parts.append(chunk.text)
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("fallback returned no text")
    return text


async def _complete_target(kind: str, label: str, prompt: str, env: Mapping[str, str]) -> str:
    model_name = label.split(":", 1)[1]
    if kind == "openai":
        from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter

        adapter: LanguageModel = OpenAICompatibleAdapter(
            base_url=env.get("SIRO_OPENAI_BASE_URL", "https://api.groq.com/openai"),
            api_key=env.get("SIRO_OPENAI_API_KEY", ""),
            model=model_name,
        )
        return await _collect_text(adapter, prompt, Privacy.CLOUD_ALLOWED)
    from siro.adapters.models.ollama import OllamaAdapter

    return await _collect_text(
        OllamaAdapter(model=model_name, thinking=False), prompt, Privacy.LOCAL_ONLY
    )


async def complete_fallback(
    prompt: str, *, env: Mapping[str, str] | None = None
) -> tuple[str, str]:
    """Ask Groq, then Ollama. Raises ``ClaudeUnavailable`` when neither can answer."""
    values = os.environ if env is None else env
    targets = fallback_targets(values)
    if not targets:
        raise ClaudeUnavailable("claude unavailable")
    last: Exception | None = None
    for label, kind in targets:
        try:
            return await _complete_target(kind, label, prompt, values), label
        except Exception as error:
            last = error
            _LOG.warning("claude fallback %s failed", label)
    raise ClaudeUnavailable("claude unavailable") from last


async def _when_claude_blocked(
    caller: str | None,
    view: BudgetView,
    prompt: str,
    fallback: Fallback | None,
) -> dict[str, object]:
    message = block_message(view)
    _LOG.info("claude blocked caller=%s reason=%s", caller or "unlabeled", view.reason)
    if caller in _RULE_CALLERS:
        raise ClaudeUnavailable(message)
    try:
        text, label = (
            await fallback(prompt) if fallback is not None else await complete_fallback(prompt)
        )
    except Exception as error:
        raise ClaudeUnavailable(message) from error
    cleaned = text.strip()
    if not cleaned:
        raise ClaudeUnavailable(message)
    return {
        "answer": cleaned[:MAX_ANSWER],
        "truncated": len(cleaned) > MAX_ANSWER,
        "model": label,
        "fallback": True,
    }


async def ask_claude(
    arguments: dict[str, object],
    context: ExecutionContext | None = None,
    *,
    model: str = DEFAULT_MODEL,
    binary: Path | None = None,
    run: Runner | None = None,
    prefix: str = PROMPT,
    limit: int = MAX_TASK,
    search: bool = True,
    caller: str | None = None,
    budget: ClaudeBudget | None = None,
    fallback: Fallback | None = None,
) -> dict[str, object]:
    """Ask the Claude CLI. ``caller`` opts into the shared budget.

    Computer-use still calls this without ``caller``, so it does not consume the
    budget until the suggested patch is applied. A rate-limit result always starts
    the shared cooldown, including those unguarded calls. ``SIRO_CLAUDE_TIMEOUT_SECONDS``
    is the CLI timeout.
    """
    task = arguments.get("task")
    if not isinstance(task, str) or not 2 <= len(task.strip()) <= limit:
        raise ValueError("claude.ask requires a task of 2-2000 characters")
    prompt = prefix + task.strip()
    guard = budget if budget is not None else (shared_claude_budget() if caller else None)
    if guard is not None:
        preview = await guard.snapshot()
        if not preview.allowed:
            return await _when_claude_blocked(caller, preview, prompt, fallback)
    binary = binary or claude_binary()
    if binary is None:
        raise ClaudeUnavailable("claude CLI not found")
    if guard is not None:
        reserved = await guard.try_reserve(caller)
        if not reserved.allowed:
            return await _when_claude_blocked(caller, reserved, prompt, fallback)
    environment = restricted_environment(("SIRO_CLAUDE_BIN", "CLAUDE_CONFIG_DIR"))
    active_run = run if run is not None else execute_bounded_argv
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
            prompt,
        )
        result = await active_run(
            argv,
            cwd=Path(scratch),
            environment=environment,
            timeout=float(claude_timeout_seconds()),
            context=context,
        )
    moment = guard.now() if guard is not None else datetime.now(UTC)
    if await observe_cli_rate_limit(result, budget=guard, now=moment):
        if guard is None:
            raise ClaudeUnavailable("claude did not return an answer")
        viewed = await guard.snapshot()
        if viewed.allowed:
            viewed = BudgetView(False, viewed.remaining, viewed.limit, moment, "rate_limit")
        return await _when_claude_blocked(caller, viewed, prompt, fallback)
    answer = ""
    if result.get("returncode") == 0:
        try:
            parsed = json.loads(str(result.get("stdout", "")))
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and not parsed.get("is_error"):
            answer = str(parsed.get("result") or "").strip()
    if not answer:
        raise ClaudeUnavailable("claude did not return an answer")
    return {"answer": answer[:MAX_ANSWER], "truncated": len(answer) > MAX_ANSWER, "model": model}
