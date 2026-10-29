"""Next-step decision: structured output, strict parsing, and the vision-capable cloud decider."""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import ALLOWED_KINDS, InputAction
from siro.services.tools.claude import Runner, claude_binary, claude_model
from siro.services.tools.execution import execute_bounded_argv, restricted_environment

CLOUD_SCREEN_FLAG = "SIRO_COMPUTER_CLOUD_SCREEN"  # owner opt-in: screenshots may go to the cloud
DECISION_KINDS = frozenset({"act", "done", "stuck", "ask"})


class DecisionError(ValueError):
    """The model reply is not an acceptable decision."""


@dataclass(frozen=True, slots=True)
class Decision:
    kind: str  # act | done | stuck | ask
    action: InputAction | None = None
    expect: str = ""  # what should visibly change if the action works
    reason: str = ""
    confidence: float = 0.0
    evidence: str = ""  # for done: what on screen proves the goal is met


@dataclass(frozen=True, slots=True)
class StepRecord:
    step: int
    action: str
    expect: str
    outcome: str  # ok | denied:<why> | unknown | invalid:<why>
    screen_changed: bool | None


class Decider(Protocol):
    async def decide(
        self, goal: str, history: Sequence[StepRecord], observation: Observation
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
            key=str(spec.get("key", "")),
            text=str(spec.get("text", "")),
            amount=_int(spec.get("amount")) or 0,
        )
    return Decision(
        kind=str(kind),
        action=action,
        expect=str(raw.get("expect", ""))[:300],
        reason=str(raw.get("reason", ""))[:300],
        confidence=float(confidence),
        evidence=str(raw.get("evidence", ""))[:300],
    )


DECISION_PROMPT = """You control a Windows PC for the owner, one input at a time. Read the screenshot file \
{image} (your only tool is Read). Decide the single best next step toward the goal, or stop.

Goal: {goal}
Foreground window: "{title}" ({process}); window rect left,top,width,height = {rect}; screen = {screen}.
Coordinates are physical screen pixels and must fall inside the window rect.
Recent steps (oldest first):
{history}

Rules:
- Judge only from what the screenshot shows now. If the last step had no visible effect, do NOT repeat it unchanged: try something different, or answer "stuck".
- Answer "done" only if the screenshot itself proves the goal is met; put that proof in "evidence".
- Answer "ask" if you need the owner (ambiguous goal, risky/irreversible choice, login or payment).
- Never type secrets. Allowed inputs: move, click(left|right), scroll(amount -20..20), key(combo like "space" or "ctrl+c"), type(text<=200).
- confidence is 0..1: how sure you are this step is correct.
Reply with JSON only:
{{"kind":"act|done|stuck|ask","action":{{"kind":"click","x":0,"y":0,"button":"left"}},"expect":"what should change","reason":"why","confidence":0.0,"evidence":""}}"""  # noqa: E501


class CloudScreenNotAllowed(RuntimeError):
    """The owner has not allowed screenshots to leave the machine."""


def cloud_screen_allowed(env: dict[str, str] | None = None) -> bool:
    return (os.environ if env is None else env).get(CLOUD_SCREEN_FLAG, "0") == "1"


def _history_text(history: Sequence[StepRecord]) -> str:
    if not history:
        return "(none yet)"
    return "\n".join(
        f"{r.step}. {r.action} -> expected: {r.expect or '-'}; outcome: {r.outcome}; "
        f"screen changed: {'?' if r.screen_changed is None else r.screen_changed}"
        for r in history[-8:]
    )


class ClaudeVisionDecider:
    """Cloud decider via the logged-in `claude` CLI (Read tool on a scratch screenshot)."""

    def __init__(
        self,
        *,
        model: str | None = None,
        binary: Path | None = None,
        run: Runner = execute_bounded_argv,
        env: dict[str, str] | None = None,
        timeout: int = 90,
    ) -> None:
        self._model = model or claude_model()
        self._binary = binary
        self._run = run
        self._env = env
        self._timeout = timeout

    async def decide(
        self, goal: str, history: Sequence[StepRecord], observation: Observation
    ) -> Decision:
        if not cloud_screen_allowed(self._env):
            raise CloudScreenNotAllowed(CLOUD_SCREEN_FLAG)
        if not observation.image_png_b64:
            raise DecisionError("no_image")
        binary = self._binary or claude_binary()
        if binary is None:
            raise DecisionError("claude_cli_missing")
        with tempfile.TemporaryDirectory(prefix="siro-screen-") as scratch:
            (Path(scratch) / "screen.png").write_bytes(base64.b64decode(observation.image_png_b64))
            prompt = DECISION_PROMPT.format(
                image="screen.png",
                goal=goal,
                title=observation.window_title,
                process=observation.process,
                rect=observation.window_rect,
                screen=observation.screen,
                history=_history_text(history),
            )
            argv = (
                str(binary), "-p", "--model", self._model, "--output-format", "json",
                "--tools", "Read", "--allowedTools", "Read", "--no-session-persistence", prompt,
            )  # fmt: skip
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
        if not isinstance(parsed, dict) or parsed.get("is_error"):
            raise DecisionError("claude_error")
        return parse_decision(str(parsed.get("result") or ""))
