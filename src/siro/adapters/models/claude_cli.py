"""Claude as a language-model tier, through the owner's logged-in `claude` CLI.

The CLI is read-only here: its own tools are disabled, and a scratch directory is the
working directory. SIRO tool calls are requested as JSON in the reply and executed by
the existing tool owner, not by the CLI. Patterns follow `claude.ask` without importing
that service (adapters do not depend on services).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelRequest,
    Privacy,
    ToolCall,
)

# Same child allowlist as services.tools.execution.restricted_environment, plus the
# CLI's own login location. The process environment is never inherited wholesale.
_CHILD_ENV = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TERM",
    "TMPDIR",
    "SYSTEMROOT",
    "USERPROFILE",
    "SIRO_CLAUDE_BIN",
    "CLAUDE_CONFIG_DIR",
)
_RATE_LIMIT = re.compile(
    r"rate[\s-]?limit|usage limit|too many requests|\b429\b|hit your .{0,40}limit",
    re.IGNORECASE,
)
_RETRY_SECONDS = re.compile(r"(\d+)\s*(?:seconds|second|secs|sec|秒)", re.IGNORECASE)
_RETRY_AT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?")
_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
_MAX_ANSWER = 24_000
_MAX_OUTPUT_BYTES = 256 * 1024

ClaudeRunner = Callable[..., Awaitable[Mapping[str, object]]]


class ClaudeCliError(RuntimeError):
    """The CLI did not return a usable answer."""


class ClaudeRateLimited(ClaudeCliError):
    """The CLI reported a provider rate limit. `retry_at` is set only when the text has one."""

    def __init__(self, retry_at: datetime | None = None) -> None:
        super().__init__("claude rate limit")
        self.retry_at = retry_at


def child_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = os.environ if source is None else source
    return {name: environment[name] for name in _CHILD_ENV if name in environment}


def _retry_at(text: str, *, now: datetime) -> datetime | None:
    match = _RETRY_AT.search(text)
    if match is not None:
        raw = match.group(0).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            if parsed > now:
                return parsed.astimezone(UTC)
    seconds = _RETRY_SECONDS.search(text)
    if seconds is None:
        return None
    try:
        delay = int(seconds.group(1))
    except ValueError:
        return None
    if not 0 <= delay <= 5 * 60 * 60:
        return None
    return now + timedelta(seconds=delay)


def _load_json(stdout: str) -> dict[str, object] | None:
    try:
        parsed = json.loads(stdout)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def interpret_cli_result(result: Mapping[str, object], *, now: datetime | None = None) -> str:
    """Return the answer text or raise ClaudeCliError / ClaudeRateLimited."""
    moment = now or datetime.now(UTC)
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    combined = f"{stdout}\n{stderr}"
    if _RATE_LIMIT.search(combined):
        raise ClaudeRateLimited(_retry_at(combined, now=moment))
    parsed = _load_json(stdout)
    if isinstance(parsed, dict):
        if parsed.get("is_error"):
            detail = str(parsed.get("result") or stderr)
            if _RATE_LIMIT.search(detail):
                raise ClaudeRateLimited(_retry_at(detail, now=moment))
            raise ClaudeCliError("claude cli failed")
        text = str(parsed.get("result") or "").strip()
        if text:
            return text
        raise ClaudeCliError("claude cli failed")
    if result.get("returncode") == 0 and stdout.strip():
        return stdout.strip()
    raise ClaudeCliError("claude cli failed")


def _conversation_text(request: ModelRequest) -> str:
    if request.messages:
        lines = [f"[{message.role}]\n{message.content}" for message in request.messages]
        return "\n\n".join(lines)
    return request.prompt


def _system_prompt(request: ModelRequest) -> str:
    base = (
        "你是 SIRO。用繁體中文直接回答主人。"
        "需要推理時先把步驟想清楚，再給可以執行的答案。"  # noqa: RUF001
        "不要聲稱已經做了你沒有做的事，也不要修改檔案。"  # noqa: RUF001
    )
    if not request.tools:
        return base
    offered = [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in request.tools
    ]
    return (
        base
        + " 若需要工具，只回一個 JSON 物件，不要加說明："  # noqa: RUF001
        + '{"tool_calls":[{"name":"工具名稱","arguments":{}}]}。'
        + "工具名稱必須是下面其中一個。不需要工具就直接用文字回答。可用工具："  # noqa: RUF001
        + json.dumps(offered, ensure_ascii=False)
    )


def parse_tool_reply(text: str, request: ModelRequest) -> tuple[ToolCall, ...] | None:
    """A tool JSON reply, or None when the text is a normal answer."""
    if not request.tools:
        return None
    stripped = text.strip()
    fenced = _FENCE.search(stripped)
    blob = fenced.group(1) if fenced else stripped
    if not blob.startswith("{"):
        return None
    try:
        parsed = json.loads(blob)
    except ValueError:
        return None
    if not isinstance(parsed, dict) or "tool_calls" not in parsed:
        return None
    raw_calls = parsed.get("tool_calls")
    if not isinstance(raw_calls, list) or not raw_calls:
        return None
    allowed = {tool.name for tool in request.tools}
    calls: list[ToolCall] = []
    for index, raw in enumerate(raw_calls):
        if not isinstance(raw, dict):
            raise ClaudeCliError("claude tool call is malformed")
        name = raw.get("name")
        arguments = raw.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError as error:
                raise ClaudeCliError("claude tool call is malformed") from error
        if not isinstance(name, str) or name not in allowed or not isinstance(arguments, dict):
            raise ClaudeCliError("claude tool call is not in the offered set")
        calls.append(ToolCall(f"claude-{request.generation_id}-{index}", name, arguments))
    return tuple(calls)


async def _default_runner(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    timeout: float,
    cancellation: CancellationToken,
) -> Mapping[str, object]:
    if cancellation.cancelled:
        return {"returncode": None, "stdout": "", "stderr": "", "cancelled": True}
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        env=dict(environment),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )

    async def stop() -> None:
        await cancellation.wait()
        if process.returncode is None:
            try:
                os.killpg(process.pid, 15)
            except (ProcessLookupError, PermissionError):
                process.kill()

    watcher = asyncio.create_task(stop())
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except TimeoutError:
        if process.returncode is None:
            try:
                os.killpg(process.pid, 15)
            except (ProcessLookupError, PermissionError):
                process.kill()
        raise
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
    if len(stdout) > _MAX_OUTPUT_BYTES or len(stderr) > _MAX_OUTPUT_BYTES:
        raise ClaudeCliError("claude cli output exceeded the limit")
    return {
        "returncode": process.returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "cancelled": cancellation.cancelled,
    }


class ClaudeCliModel:
    """One-shot Claude CLI call. Text is returned as a single chunk when the process exits."""

    def __init__(
        self,
        *,
        model: str,
        binary: Path,
        environment: Mapping[str, str] | None = None,
        runner: ClaudeRunner | None = None,
        timeout: float = 120,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("claude model name is required")
        if not 10 <= timeout <= 240:
            raise ValueError("claude timeout must be between 10 and 240 seconds")
        self.name = f"claude:{model}"
        self._model = model
        self._binary = binary
        self._environment = dict(environment) if environment is not None else child_environment()
        self._runner = runner or _default_runner
        self._timeout = timeout
        self._clock = clock or (lambda: datetime.now(UTC))

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        if request.privacy is not Privacy.CLOUD_ALLOWED:
            raise PermissionError("cloud egress requires cloud_allowed privacy")
        if cancellation.cancelled:
            return
        prompt = _conversation_text(request)
        with tempfile.TemporaryDirectory(prefix="siro-claude-route-") as scratch:
            argv = (
                str(self._binary),
                "-p",
                "--model",
                self._model,
                "--output-format",
                "json",
                "--tools",
                "",
                "--system-prompt",
                _system_prompt(request),
                "--no-session-persistence",
                prompt,
            )
            result = await self._runner(
                argv,
                cwd=Path(scratch),
                environment=self._environment,
                timeout=self._timeout,
                cancellation=cancellation,
            )
        if cancellation.cancelled or result.get("cancelled") is True:
            return
        text = interpret_cli_result(result, now=self._clock())
        if cancellation.cancelled:
            return
        calls = parse_tool_reply(text, request)
        if calls is not None:
            for call in calls:
                yield ModelChunk("tool_request", tool_call=call)
                if cancellation.cancelled:
                    return
            yield ModelChunk("finished")
            return
        visible = text[:_MAX_ANSWER]
        if visible:
            yield ModelChunk("text", visible)
        if cancellation.cancelled:
            return
        yield ModelChunk("finished")
