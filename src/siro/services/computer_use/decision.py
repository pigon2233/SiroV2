"""Next-step decision: structured output, strict parsing, local Ollama vision, optional Claude."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from siro.services.computer_use.perception import Observation, annotate_coord_grid
from siro.services.computer_use.safety import ALLOWED_KINDS, InputAction
from siro.services.tools.claude import Runner, claude_binary, claude_model
from siro.services.tools.execution import execute_bounded_argv, restricted_environment

CLOUD_SCREEN_FLAG = "SIRO_COMPUTER_CLOUD_SCREEN"  # owner opt-in: screenshots may go to the cloud
DECIDER_ENV = "SIRO_COMPUTER_DECIDER"  # ollama (default) | claude | groq
OLLAMA_HOST_ENV = "OLLAMA_HOST"
OLLAMA_MODEL_ENV = "SIRO_COMPUTER_OLLAMA_MODEL"
OLLAMA_NUM_PREDICT_ENV = "SIRO_COMPUTER_OLLAMA_NUM_PREDICT"
DEFAULT_OLLAMA_MODEL = "gemma4:e2b"
DEFAULT_OLLAMA_NUM_PREDICT = 150  # short JSON decisions; was 260 and slowed local VLM turns
GROQ_MODEL_ENV = "SIRO_COMPUTER_GROQ_MODEL"
GROQ_REASONING_ENV = "SIRO_COMPUTER_GROQ_REASONING"  # reasoning_effort; "" omits the field
# Llama 4 Scout was shut down on Groq free/dev tiers; Qwen3.8 27B is the current vision pick.
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
GROQ_MAX_IMAGE_B64 = 3_500_000  # Groq caps base64 image payloads near ~4MB
DECISION_KINDS = frozenset({"act", "done", "stuck", "ask", "wait"})
SCENES = frozenset(
    {"map", "combat", "shop", "event", "reward", "pause", "defeat", "menu", "unknown"}
)


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
    scene: str = ""  # map|combat|shop|event|reward|pause|defeat|menu|unknown
    energy: str = ""  # e.g. "3/3", "0", "n/a"
    targets: str = ""  # actionable controls visible now
    uncertainty: str = ""  # unreadable bits; empty if clear


@dataclass(frozen=True, slots=True)
class StepRecord:
    step: int
    action: str
    expect: str
    outcome: str  # sent | visual_change | effective | unconfirmed | ineffective | ...
    screen_changed: bool | None
    seen: str = ""  # what the screen showed before this step
    scene: str = ""
    detail: str = ""  # verification note or failure reason


@dataclass(frozen=True, slots=True)
class VerifyResult:
    status: str  # confirmed | denied | unknown
    detail: str = ""
    seen: str = ""
    scene: str = ""


class Decider(Protocol):
    async def decide(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision: ...

    async def verify(
        self,
        expect: str,
        before_seen: str,
        observation: Observation,
    ) -> VerifyResult: ...


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _scene_of(raw: Mapping[str, object]) -> str:
    scene = str(raw.get("scene", "")).strip().lower()
    return scene if scene in SCENES else "unknown"


def parse_verify(text: str) -> VerifyResult:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        raw = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        raw = None
    if not isinstance(raw, dict):
        return VerifyResult("unknown", "verify_not_json")
    status = str(raw.get("status", "")).strip().lower()
    if status not in {"confirmed", "denied", "unknown"}:
        status = "unknown"
    return VerifyResult(
        status=status,
        detail=str(raw.get("detail", "")).strip()[:200],
        seen=str(raw.get("seen", "")).strip()[:200],
        scene=_scene_of(raw),
    )


_KIND_ALIASES = {
    "action": "act",
    "click": "act",
    "tap": "act",
    "press": "act",
    "play": "act",
    "select": "act",
    "choose": "act",
    "move": "act",
    "pause": "wait",
    "sleep": "wait",
    "observe": "wait",
    "look": "wait",
    "inspect": "wait",
    "reobserve": "wait",
    "thinking": "wait",
    "think": "wait",
    "stop": "stuck",
    "fail": "stuck",
    "help": "ask",
    "question": "ask",
    "finish": "done",
    "complete": "done",
    "success": "done",
}


def _coerce_kind(value: object, *, has_action: bool) -> str | None:
    if isinstance(value, str):
        key = value.strip().lower()
        if key in DECISION_KINDS:
            return key
        if key in _KIND_ALIASES:
            return _KIND_ALIASES[key]
    if has_action:
        return "act"
    return None


def parse_decision(text: str) -> Decision:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        raw = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        raw = None
    if not isinstance(raw, dict):
        raise DecisionError("not_json")
    has_action = isinstance(raw.get("action"), dict)
    kind = _coerce_kind(raw.get("kind"), has_action=has_action)
    if kind is None:
        raise DecisionError("bad_kind")
    raw = {**raw, "kind": kind}
    confidence = raw.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        confidence = 0.55  # small local models often omit confidence
    confidence = float(confidence)
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
    expect = str(raw.get("expect", "")).strip()[:300]
    if kind == "act" and not expect:
        raise DecisionError("missing_expect")
    return Decision(
        kind=str(kind),
        action=action,
        expect=expect,
        reason=reason,
        confidence=float(confidence),
        evidence=str(raw.get("evidence", ""))[:300],
        seen=seen,
        strategy=str(raw.get("strategy", "")).strip()[:200],
        scene=_scene_of(raw),
        energy=str(raw.get("energy", "")).strip()[:40],
        targets=str(raw.get("targets", "")).strip()[:200],
        uncertainty=str(raw.get("uncertainty", "")).strip()[:200],
    )


_JSON_SHAPE = (
    '{{"kind":"act|done|stuck|ask|wait","scene":"map|combat|shop|event|reward|pause|defeat|menu|unknown",'
    '"seen":"one short sentence","energy":"e.g. 2/3 or n/a","targets":"clickable controls",'
    '"uncertainty":"what is unreadable or empty","strategy":"",'
    '"action":{{"kind":"click","x":0,"y":0,"button":"left"}},'
    '"expect":"visible change to verify","reason":"why","confidence":0.8,"evidence":""}}'
)

DECISION_PROMPT = """Screenshot is attached ({w}x{h} px). It covers desktop rect {image_rect} (left,top,width,height).
Click/move x,y are SCREENSHOT pixels only: 0 <= x < {w}, 0 <= y < {h}. Never desktop coords.
Yellow/cyan grid labels on the image are screenshot pixel coords — read them when aiming.
Main-menu / centered lists (单人模式, Resume, etc.): click near horizontal center x≈{cx} unless the label is clearly elsewhere. Do not guess far-left x.

Goal: {goal}
Current strategy: {strategy}
Window "{title}" ({process}).
Recent (sent=delivered, visual_change=pixels moved, effective=expect confirmed, unconfirmed=尚未確認, ineffective=no progress):
{history}

Hard rules:
- Fill scene, energy, targets, uncertainty every turn. If UI text is unreadable, set uncertainty and prefer kind=wait (do not invent coords).
- Follow Current strategy with an immediate reaction to THIS screen.
- If strategy is "(none)" or the scene clearly changed, set "strategy" to a short plan (≤20 words). Otherwise "".
- "seen" MUST describe the screen in one short sentence (never empty).
- Every act MUST set "expect" to the visible change used to verify success.
- No repeats if last act was ineffective — pick a clearly different x,y (Δ≥80px) or wait.
- Wait if loading. Never ask. Never type secrets. Never spam Escape.
- Defeat/death/game over/retry/continue → click once (not done).
- Combat with 0 energy / no affordable cards → click End Turn / 结束回合 (bottom-right).
- Pause menu → click Resume/继续. Shop and not buying → click Leave/Proceed.
JSON only:
""" + _JSON_SHAPE  # noqa: E501

CLAUDE_DECISION_PROMPT = """Read {image} (only tool: Read). Screenshot is {w}x{h} px covering desktop rect {image_rect}.
Click/move x,y are SCREENSHOT pixels only: 0 <= x < {w}, 0 <= y < {h}. Grid labels are screenshot coords.
Centered menus: prefer x≈{cx}. After an ineffective click, change x,y by ≥80px.

Goal: {goal}
Current strategy: {strategy}
Window "{title}" ({process}).
Recent:
{history}

Hard rules:
- Fill scene, energy, targets, uncertainty. If unreadable, kind=wait — do not invent coords.
- Follow Current strategy. Refresh strategy on scene change; else "".
- "seen" required. Every act needs "expect" for verification.
- No repeats after ineffective. Never ask. Never spam Escape.
- 0 energy → End Turn. Pause → Resume. Shop leave → Leave/Proceed. Defeat → click continue once.
JSON only:
""" + _JSON_SHAPE  # noqa: E501


class CloudScreenNotAllowed(RuntimeError):
    """The owner has not allowed screenshots to leave the machine."""


def cloud_screen_allowed(env: dict[str, str] | None = None) -> bool:
    return (os.environ if env is None else env).get(CLOUD_SCREEN_FLAG, "0") == "1"


VERIFY_PROMPT = """Screenshot is attached ({w}x{h} px), desktop rect {image_rect}.
Previous action expected: {expect}
Previous description: {before_seen}

Judge ONLY whether that expectation is visibly true now (e.g. main menu gone, character select shown, combat started, shop closed).
Pixel motion alone is not enough.
JSON only:
{{"status":"confirmed|denied|unknown","seen":"what is on screen now","scene":"map|combat|shop|event|reward|pause|defeat|menu|unknown","detail":"short why"}}"""


def _history_text(history: Sequence[StepRecord]) -> str:
    if not history:
        return "(none yet)"
    lines: list[str] = []
    effective = [r for r in history if r.outcome == "effective"]
    if effective:
        last = effective[-1]
        lines.append(
            f"Last effective: step {last.step} {last.action} expect={last.expect or '-'} "
            f"scene={last.scene or '-'}"
        )
    fails = [
        r
        for r in history
        if r.outcome
        in {"ineffective", "unconfirmed", "visual_change"}
        or r.outcome.startswith(("invalid", "denied"))
        or (r.outcome in {"sent", "ok"} and r.screen_changed is False)
    ]
    if fails:
        last = fails[-1]
        lines.append(
            f"Last failure: step {last.step} {last.action} outcome={last.outcome} "
            f"detail={last.detail or last.expect or '-'}"
        )
    for r in history[-4:]:
        changed = "?" if r.screen_changed is None else r.screen_changed
        lines.append(
            f"{r.step}. scene={r.scene or '-'} saw={r.seen or '-'} | did={r.action} | "
            f"expect={r.expect or '-'} | outcome={r.outcome} | changed={changed}"
            + (f" | detail={r.detail}" if r.detail else "")
        )
    return "\n".join(lines)


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
    image_rect = observation.image_rect or (0, 0, *observation.screen)
    return {
        "goal": goal,
        "strategy": strategy.strip() or "(none)",
        "title": observation.window_title,
        "process": observation.process,
        "w": width,
        "h": height,
        "cx": width // 2,
        "image_rect": list(image_rect),
        "history": _history_text(history),
    }


class OllamaVisionDecider:
    """Local vision decider via Ollama /api/chat (screenshots stay on this machine)."""

    _transient = frozenset({"ollama_failed", "ollama_timeout", "ollama_bad_output", "ollama_empty"})

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
        self._num_predict = _ollama_num_predict(values)

    async def _chat(
        self, prompt: str, observation: Observation, *, num_predict: int | None = None
    ) -> str:
        if not observation.image_png_b64:
            raise DecisionError("no_image")
        vision = annotate_coord_grid(observation.image_png_b64, env=self._env)
        predict = self._num_predict if num_predict is None else num_predict
        payload = {
            "model": self._model,
            "stream": False,
            "think": False,
            "keep_alive": values_keep_alive(self._env),
            "options": {"temperature": 0.1, "num_predict": predict, "num_ctx": 2048},
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [vision],
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
        return content

    async def _decide_once(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision:
        fields = _prompt_fields(goal, history, observation, strategy=strategy)
        prompt = DECISION_PROMPT.format(**fields)
        if fields["strategy"] == "(none)" or "MUST set a non-empty \"strategy\"" in goal:
            prompt += '\nThis turn: you MUST set a non-empty "strategy" short plan.'
        return parse_decision(await self._chat(prompt, observation))

    async def verify(
        self,
        expect: str,
        before_seen: str,
        observation: Observation,
    ) -> VerifyResult:
        width, height = observation.image_size or (0, 0)
        image_rect = observation.image_rect or (0, 0, *observation.screen)
        prompt = VERIFY_PROMPT.format(
            w=width,
            h=height,
            image_rect=list(image_rect),
            expect=expect.strip()[:300] or "(none)",
            before_seen=before_seen.strip()[:200] or "-",
        )
        try:
            return parse_verify(await self._chat(prompt, observation, num_predict=min(80, self._num_predict)))
        except DecisionError as error:
            return VerifyResult("unknown", f"verify_failed:{error}")

    async def decide(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision:
        """Retry malformed JSON/action once; soft-recover to wait instead of killing the segment."""
        transient = self._transient
        format_errors = {
            "not_json",
            "bad_action",
            "incomplete_action",
            "bad_kind",
            "missing_expect",
            "bad_confidence",
        }
        last: DecisionError | None = None
        for attempt in range(2):
            try:
                return await self._decide_once(goal, history, observation, strategy=strategy)
            except DecisionError as error:
                last = error
                code = str(error)
                if code in format_errors and attempt == 0:
                    try:
                        return await self._decide_once(
                            goal, history, observation, strategy=strategy
                        )
                    except DecisionError as retry_error:
                        last = retry_error
                        break
                if code not in transient or attempt >= 1:
                    break
                await asyncio.sleep(0.2)
        assert last is not None
        # Weak local models often emit odd kinds/JSON; wait and re-observe rather than fail the run.
        if str(last) in format_errors or str(last) in transient:
            return Decision(
                "wait",
                None,
                "recover from bad model output",
                f"decider_soft:{last}",
                0.2,
                "",
                "model output invalid; re-observe",
                uncertainty="bad_model_output",
            )
        raise last


def values_keep_alive(env: Mapping[str, str] | None) -> str:
    values = os.environ if env is None else env
    return values.get("SIRO_OLLAMA_KEEP_ALIVE") or "30m"


def _ollama_num_predict(env: Mapping[str, str] | None) -> int:
    values = os.environ if env is None else env
    raw = (values.get(OLLAMA_NUM_PREDICT_ENV) or "").strip()
    if not raw:
        return DEFAULT_OLLAMA_NUM_PREDICT
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_OLLAMA_NUM_PREDICT
    if not 32 <= value <= 512:
        return DEFAULT_OLLAMA_NUM_PREDICT
    return value


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
            vision = annotate_coord_grid(observation.image_png_b64, env=self._env)
            (Path(scratch) / screen_name).write_bytes(base64.b64decode(vision))
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

    async def verify(
        self,
        expect: str,
        before_seen: str,
        observation: Observation,
    ) -> VerifyResult:
        # Avoid a second cloud round-trip by default; local Ollama owns verify.
        return VerifyResult("unknown", "claude_verify_not_used", before_seen, "unknown")

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
                if code in {
                    "not_json",
                    "bad_action",
                    "incomplete_action",
                    "bad_kind",
                    "missing_expect",
                }:
                    return await self._decide_once(
                        goal, history, observation, strategy=strategy
                    )
                if code not in transient or attempt >= 1:
                    raise
                await asyncio.sleep(0.25)
        assert last is not None
        raise last


def _shrink_for_groq(image_b64: str) -> str:
    """Re-encode smaller JPEG when the payload is near Groq's base64 limit (best effort)."""
    if len(image_b64) <= GROQ_MAX_IMAGE_B64:
        return image_b64
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
        quality = 70
        while True:
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=quality)
            encoded = base64.b64encode(out.getvalue()).decode("ascii")
            if len(encoded) <= GROQ_MAX_IMAGE_B64 or quality <= 30:
                return encoded
            quality -= 15
    except Exception:  # noqa: BLE001 — let Groq reject rather than crash the loop
        return image_b64


def _image_mime(image_b64: str) -> str:
    return "image/png" if image_b64.startswith("iVBOR") else "image/jpeg"


class GroqVisionDecider(OllamaVisionDecider):
    """Cloud vision via Groq OpenAI-compatible chat completions (screenshot leaves this machine)."""

    _transient = frozenset({"groq_failed", "groq_timeout", "groq_bad_output", "groq_empty"})

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        values = os.environ if env is None else env
        self._env = env
        self._model = model or values.get(GROQ_MODEL_ENV) or DEFAULT_GROQ_MODEL
        self._base_url = (
            base_url or values.get("SIRO_OPENAI_BASE_URL") or "https://api.groq.com/openai"
        ).rstrip("/")
        self._api_key = api_key if api_key is not None else values.get("SIRO_OPENAI_API_KEY", "")
        self._reasoning = values.get(GROQ_REASONING_ENV, "none").strip()
        self._timeout = timeout
        self._client = client
        self._num_predict = _ollama_num_predict(values)

    async def _chat(
        self, prompt: str, observation: Observation, *, num_predict: int | None = None
    ) -> str:
        if not cloud_screen_allowed(self._env):
            raise CloudScreenNotAllowed(CLOUD_SCREEN_FLAG)
        if not observation.image_png_b64:
            raise DecisionError("no_image")
        if not self._api_key:
            raise DecisionError("groq_no_key")
        predict = self._num_predict if num_predict is None else num_predict
        vision = _shrink_for_groq(annotate_coord_grid(observation.image_png_b64, env=self._env))
        payload: dict[str, object] = {
            "model": self._model,
            "stream": False,
            "temperature": 0.1,
            "max_completion_tokens": max(predict, 400),
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{_image_mime(vision)};base64,{vision}"},
                        },
                    ],
                }
            ],
        }
        if self._reasoning:
            payload["reasoning_effort"] = self._reasoning
        url = f"{self._base_url}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            if self._client is not None:
                response = await self._client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as error:
            raise DecisionError("groq_timeout") from error
        except httpx.HTTPError as error:
            raise DecisionError("groq_failed") from error
        if response.status_code in {401, 403}:
            raise DecisionError("groq_auth")
        if response.status_code == 429:
            # Free-tier RPM; soft-recover path will re-observe after a short wait.
            raise DecisionError("groq_timeout")
        if response.status_code >= 400:
            raise DecisionError("groq_failed")
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise DecisionError("groq_bad_output") from error
        if not isinstance(content, str) or not content.strip():
            raise DecisionError("groq_empty")
        return content


def make_decider(env: Mapping[str, str] | None = None) -> Decider:
    """Owner chooses the computer-use brain; default is local Ollama vision (no Claude)."""
    values = dict(os.environ if env is None else env)
    kind = values.get(DECIDER_ENV, "ollama").strip().lower() or "ollama"
    if kind in {"claude", "claude_cli", "cloud"}:
        return ClaudeVisionDecider(env=values)
    if kind == "groq":
        return GroqVisionDecider(env=values)
    return OllamaVisionDecider(env=values)
