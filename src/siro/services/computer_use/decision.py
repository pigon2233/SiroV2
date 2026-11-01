"""Next-step decision: structured output, strict parsing, local Ollama vision, optional Claude."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import ALLOWED_KINDS, InputAction
from siro.services.tools.claude import Runner, claude_binary, claude_model
from siro.services.tools.execution import execute_bounded_argv, restricted_environment

CLOUD_SCREEN_FLAG = "SIRO_COMPUTER_CLOUD_SCREEN"  # owner opt-in: screenshots may go to the cloud
DECIDER_ENV = "SIRO_COMPUTER_DECIDER"  # ollama (default) | claude
OLLAMA_HOST_ENV = "OLLAMA_HOST"
OLLAMA_MODEL_ENV = "SIRO_COMPUTER_OLLAMA_MODEL"
DEFAULT_OLLAMA_MODEL = "gemma4:e4b"
DECISION_KINDS = frozenset({"act", "done", "stuck", "ask", "wait"})


class DecisionError(ValueError):
    """The model reply is not an acceptable decision."""


@dataclass(frozen=True, slots=True)
class Decision:
    kind: str  # act | done | stuck | ask | wait
    action: InputAction | None = None
    expect: str = ""  # what should visibly change if the action works
    reason: str = ""
    confidence: float = 0.0
    evidence: str = ""  # for done: what on screen proves the goal is met
    seen: str = ""  # one short sentence: what the screenshot shows now (kept in the history)
    strategy: str = ""  # optional short plan update; empty keeps the previous plan


@dataclass(frozen=True, slots=True)
class StepRecord:
    step: int
    action: str
    expect: str
    outcome: str  # ok | denied:<why> | unknown | invalid:<why>
    screen_changed: bool | None
    seen: str = ""  # what the screen showed before this step


class Decider(Protocol):
    async def decide(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision: ...


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse_decision(text: str) -> Decision:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        raw = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        raw = None
    if not isinstance(raw, dict):
        raise DecisionError("not_json")
    kind = raw.get("kind")
    if kind not in DECISION_KINDS:
        raise DecisionError("bad_kind")
    confidence = raw.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise DecisionError("bad_confidence")
    if not 0 <= confidence <= 1:
        raise DecisionError("bad_confidence")
    action = None
    if kind == "act":
        spec = raw.get("action")
        if not isinstance(spec, dict) or spec.get("kind") not in ALLOWED_KINDS:
            raise DecisionError("bad_action")
        action = InputAction(
            kind=str(spec["kind"]),
            x=_int(spec.get("x")),
            y=_int(spec.get("y")),
            button=str(spec.get("button", "left")),
            key=str(spec.get("key") or spec.get("combo") or ""),
            text=str(spec.get("text", "")),
            amount=_int(spec.get("amount")) or 0,
            hold_ms=_int(spec.get("hold_ms")) or 0,
        )
        incomplete = (
            (action.kind in {"move", "click"} and (action.x is None or action.y is None))
            or (action.kind == "key" and not action.key.strip())
            or (action.kind == "type" and not action.text)
            or (action.kind == "scroll" and action.amount == 0)
        )
        if incomplete:
            raise DecisionError("incomplete_action")
    reason = str(raw.get("reason", ""))[:300]
    seen = str(raw.get("seen", "")).strip()[:200] or reason[:200]
    return Decision(
        kind=str(kind),
        action=action,
        expect=str(raw.get("expect", ""))[:300],
        reason=reason,
        confidence=float(confidence),
        evidence=str(raw.get("evidence", ""))[:300],
        seen=seen,
        strategy=str(raw.get("strategy", "")).strip()[:200],
    )


DECISION_PROMPT = """Screenshot is attached ({w}x{h} px). One next input. Be fast.

Goal: {goal}
Current strategy: {strategy}
Window "{title}" ({process}).
Recent:
{history}

Hard rules:
- Follow Current strategy with an immediate reaction to THIS screen.
- If strategy is "(none)" or the scene clearly changed (map/combat/shop/event/reward/death), set "strategy" to a short plan (≤20 words). Otherwise leave "strategy":"".
- "seen" MUST describe the screen in one short sentence (never empty).
- click/move x,y are SCREENSHOT pixels only: 0 <= x < {w}, 0 <= y < {h}. Never desktop/screen coords.
- No repeats if last act did nothing. Wait if loading. Never ask. Never type secrets.
- Defeat/death/game over/retry/continue → click once (not done).
- Combat with 0 energy / no affordable cards → click End Turn / 结束回合 (bottom-right), not cards.
- Shop open and not buying → click Leave/Proceed once (Escape only if no Leave control is visible). Never spam Escape.
- Never invent coordinates outside 0..{w}-1, 0..{h}-1. Prefer the obvious highlighted button.
JSON only:
{{"kind":"act|done|stuck|ask|wait","seen":"what is on screen","strategy":"","action":{{"kind":"click","x":0,"y":0,"button":"left"}},"expect":"what changes","reason":"why","confidence":0.8,"evidence":""}}"""  # noqa: E501

CLAUDE_DECISION_PROMPT = """Read {image} (only tool: Read). Screenshot is {w}x{h} px. One next input. Be fast.

Goal: {goal}
Current strategy: {strategy}
Window "{title}" ({process}).
Recent:
{history}

Hard rules:
- Follow Current strategy with an immediate reaction to THIS screen.
- If strategy is "(none)" or the scene clearly changed, set "strategy" to a short plan (≤20 words). Otherwise "".
- "seen" MUST describe the screen in one short sentence (never empty).
- click/move x,y are SCREENSHOT pixels only: 0 <= x < {w}, 0 <= y < {h}. Never desktop coords.
- No repeats if last act did nothing. Wait if loading. Never ask. Never type secrets.
- Defeat/death/game over/retry/continue → click once (not done).
- Combat with 0 energy / no affordable cards → click End Turn / 结束回合 (bottom-right), not cards.
- Shop open and not buying → click Leave/Proceed once (Escape only if no Leave control is visible). Never spam Escape.
- Never invent coordinates outside 0..{w}-1, 0..{h}-1. Prefer the obvious highlighted button.
JSON only:
{{"kind":"act|done|stuck|ask|wait","seen":"what is on screen","strategy":"","action":{{"kind":"click","x":0,"y":0,"button":"left"}},"expect":"what changes","reason":"why","confidence":0.8,"evidence":""}}"""  # noqa: E501


class CloudScreenNotAllowed(RuntimeError):
    """The owner has not allowed screenshots to leave the machine."""


def cloud_screen_allowed(env: dict[str, str] | None = None) -> bool:
    return (os.environ if env is None else env).get(CLOUD_SCREEN_FLAG, "0") == "1"


def _history_text(history: Sequence[StepRecord]) -> str:
    if not history:
        return "(none yet)"
    return "\n".join(
        f"{r.step}. saw: {r.seen or '-'} | did: {r.action} | expected: {r.expect or '-'} | "
        f"outcome: {r.outcome}; "
        f"screen changed: {'?' if r.screen_changed is None else r.screen_changed}"
        for r in history[-3:]
    )


def _ollama_base_url(env: Mapping[str, str] | None = None) -> str:
    values = os.environ if env is None else env
    host = (values.get(OLLAMA_HOST_ENV) or "127.0.0.1:11434").strip()
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    return f"http://{host}"


def _prompt_fields(
    goal: str,
    history: Sequence[StepRecord],
    observation: Observation,
    *,
    strategy: str = "",
) -> dict[str, object]:
    width, height = observation.image_size or (0, 0)
    return {
        "goal": goal,
        "strategy": strategy.strip() or "(none)",
        "title": observation.window_title,
        "process": observation.process,
        "w": width,
        "h": height,
        "history": _history_text(history),
    }


class OllamaVisionDecider:
    """Local vision decider via Ollama /api/chat (screenshots stay on this machine)."""

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 90.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        values = os.environ if env is None else env
        self._env = env
        self._model = model or values.get(OLLAMA_MODEL_ENV) or values.get("SIRO_OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        self._base_url = (base_url or _ollama_base_url(values)).rstrip("/")
        self._timeout = timeout
        self._client = client

    async def _decide_once(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision:
        if not observation.image_png_b64:
            raise DecisionError("no_image")
        fields = _prompt_fields(goal, history, observation, strategy=strategy)
        prompt = DECISION_PROMPT.format(**fields)
        if fields["strategy"] == "(none)" or "MUST set a non-empty \"strategy\"" in goal:
            prompt += '\nThis turn: you MUST set a non-empty "strategy" short plan.'
        payload = {
            "model": self._model,
            "stream": False,
            "think": False,
            "keep_alive": values_keep_alive(self._env),
            "options": {"temperature": 0.1, "num_predict": 260, "num_ctx": 4096},
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [observation.image_png_b64],
                }
            ],
        }
        url = f"{self._base_url}/api/chat"
        try:
            if self._client is not None:
                response = await self._client.post(url, json=payload)
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, json=payload)
        except httpx.TimeoutException as error:
            raise DecisionError("ollama_timeout") from error
        except httpx.HTTPError as error:
            raise DecisionError("ollama_failed") from error
        if response.status_code >= 400:
            raise DecisionError("ollama_failed")
        try:
            body = response.json()
        except ValueError as error:
            raise DecisionError("ollama_bad_output") from error
        if not isinstance(body, dict):
            raise DecisionError("ollama_bad_output")
        message = body.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise DecisionError("ollama_empty")
        return parse_decision(content)

    async def decide(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision:
        """Retry malformed JSON/action once; one transient Ollama retry."""
        transient = {"ollama_failed", "ollama_timeout", "ollama_bad_output", "ollama_empty"}
        last: DecisionError | None = None
        for attempt in range(2):
            try:
                return await self._decide_once(goal, history, observation, strategy=strategy)
            except DecisionError as error:
                last = error
                code = str(error)
                if code in {"not_json", "bad_action", "incomplete_action", "bad_kind"}:
                    return await self._decide_once(
                        goal, history, observation, strategy=strategy
                    )
                if code not in transient or attempt >= 1:
                    raise
                await asyncio.sleep(0.2)
        assert last is not None
        raise last


def values_keep_alive(env: Mapping[str, str] | None) -> str:
    values = os.environ if env is None else env
    return values.get("SIRO_OLLAMA_KEEP_ALIVE") or "30m"


class ClaudeVisionDecider:
    """Cloud decider via the logged-in `claude` CLI (Read tool on a scratch screenshot)."""

    def __init__(
        self,
        *,
        model: str | None = None,
        binary: Path | None = None,
        run: Runner = execute_bounded_argv,
        env: dict[str, str] | None = None,
        timeout: int = 35,
    ) -> None:
        self._model = model or claude_model()
        self._binary = binary
        self._run = run
        self._env = env
        self._timeout = timeout

    async def _decide_once(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision:
        if not cloud_screen_allowed(self._env):
            raise CloudScreenNotAllowed(CLOUD_SCREEN_FLAG)
        if not observation.image_png_b64:
            raise DecisionError("no_image")
        binary = self._binary or claude_binary()
        if binary is None:
            raise DecisionError("claude_cli_missing")
        with tempfile.TemporaryDirectory(prefix="siro-screen-") as scratch:
            # Local captures may be JPEG now; Claude still Reads the bytes via this path name.
            screen_name = "screen.jpg"
            (Path(scratch) / screen_name).write_bytes(base64.b64decode(observation.image_png_b64))
            prompt = CLAUDE_DECISION_PROMPT.format(
                image=screen_name,
                **_prompt_fields(goal, history, observation, strategy=strategy),
            )
            # --effort low cuts thinking time; do not use --bare (it disables OAuth login).
            argv = (
                str(binary),
                "-p",
                "--effort",
                "low",
                "--model",
                self._model,
                "--output-format",
                "json",
                "--tools",
                "Read",
                "--allowedTools",
                "Read",
                "--no-session-persistence",
                prompt,
            )
            result = await self._run(
                argv,
                cwd=Path(scratch),
                environment=restricted_environment(("SIRO_CLAUDE_BIN", "CLAUDE_CONFIG_DIR")),
                timeout=self._timeout,
            )
        if result.get("returncode") != 0:
            raise DecisionError("claude_failed")
        try:
            parsed = json.loads(str(result.get("stdout", "")))
        except ValueError as error:
            raise DecisionError("claude_bad_output") from error
        if not isinstance(parsed, dict):
            raise DecisionError("claude_error")
        if parsed.get("is_error"):
            blob = json.dumps(parsed, ensure_ascii=False).lower()
            result_text = str(parsed.get("result") or "").lower()
            if (
                parsed.get("api_error_status") in {401, 403}
                or "401" in blob
                or "authenticat" in result_text
                or "unauthorized" in result_text
            ):
                raise DecisionError("claude_auth")
            raise DecisionError("claude_error")
        return parse_decision(str(parsed.get("result") or ""))

    async def decide(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision:
        """Retry malformed replies once; one transient Claude CLI retry (never retry auth)."""
        transient = {"claude_failed", "claude_error", "claude_bad_output"}
        last: DecisionError | None = None
        for attempt in range(2):
            try:
                return await self._decide_once(goal, history, observation, strategy=strategy)
            except DecisionError as error:
                last = error
                code = str(error)
                if code == "claude_auth":
                    raise
                if code in {"not_json", "bad_action", "incomplete_action", "bad_kind"}:
                    return await self._decide_once(
                        goal, history, observation, strategy=strategy
                    )
                if code not in transient or attempt >= 1:
                    raise
                await asyncio.sleep(0.25)
        assert last is not None
        raise last


def make_decider(env: Mapping[str, str] | None = None) -> Decider:
    """Owner chooses the computer-use brain; default is local Ollama vision (no Claude)."""
    values = dict(os.environ if env is None else env)
    kind = values.get(DECIDER_ENV, "ollama").strip().lower() or "ollama"
    if kind in {"claude", "claude_cli", "cloud"}:
        return ClaudeVisionDecider(env=values)
    return OllamaVisionDecider(env=values)
