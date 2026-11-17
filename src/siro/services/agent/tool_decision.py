# ruff: noqa: RUF001
"""A short local decision step that picks SIRO's tool before her persona model answers.

The local chat model often says it will use a tool without emitting the call, or claims it
has none (measured 2026-11-17: 22 of 30 needed calls missed). This module asks the same local
model two narrow questions instead: which tool category fits this message (JSON enum, no
persona), then the tool arguments (the tool's own input schema as the output format). A
decided call is handed to the conversation as if the model had emitted it, so approval,
safety checks and the persona reply after the tool result stay on the existing path.

Off unless ``SIRO_TOOL_DECISION=1``. Any failure, timeout or invalid argument means "no
decision" and the turn continues exactly as before. Groq is consulted only for likely
follow-ups that the local step answered with ``none``, and only when the turn may use cloud.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from siro.adapters.models import ollama_options
from siro.ports.models import (
    CancellationToken,
    LanguageModel,
    ModelChunk,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
    ToolDefinition,
)
from siro.services.tools.orchestrator import _valid_arguments

FLAG = "SIRO_TOOL_DECISION"
MODEL_ENV = "SIRO_TOOL_DECISION_MODEL"  # defaults to the chat model SIRO_OLLAMA_MODEL
GROQ_MODEL_ENV = "SIRO_COMPUTER_GROQ_MODEL"  # same Groq model as computer control
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
NUM_CTX = 8192
LOCAL_TIMEOUT = 20.0
GROQ_TIMEOUT = 8.0
MAX_TEXT = 300
CONTEXT_CHARS = 80
LOG_NAME = "tool_decisions.jsonl"

CATEGORY_TOOL = {
    "research": "claude.ask",
    "browser": "browser.navigate+read",
    "play": "computer.play",
    "status": "computer.status",
    "files_list": "filesystem.list",
    "files_read": "filesystem.read",
    "execute": "computer.execute",
}
_CATEGORY_TEXT = {
    "none": "none：閒聊、情緒、打招呼、常識或知識問答、建議，不需要即時資料或動作。",
    "research": (
        "research：需要上網查即時或最新資訊（天氣、新聞、股價、匯率、活動、新產品、版本更新），"
        "包括追問剛查到的即時資訊的原因或細節（例如「為什麼跌這麼多」），"
        "以及要求助理再查一次（例如「你不能查嗎」）。"
    ),
    "browser": "browser：使用者給了網址，要打開閱讀。",
    "play": "play：要求助理自己去玩、打開並遊玩、或繼續玩電腦上的遊戲（打開遊戲來玩也是 play）。",
    "status": "status：問助理目前或剛才玩遊戲／電腦任務的進度、結果、卡在哪裡。",
    "files_list": "files_list：查看工作資料夾裡有哪些檔案。",
    "files_read": "files_read：讀取某個指定檔案的內容（給了檔名，或指「第幾個檔案」）。",
    "execute": "execute：在電腦上執行指令查系統資訊（磁碟、記憶體、CPU、開機時間、程序等）。",
}
_RULES = (
    "規則：\n"
    "- 「那 X 呢」「再一個」這類短追問，延續上一句的需求類別，只換對象。\n"
    "- 即使助理上一句說做不到，使用者再次要求時仍照需求選工具。\n"
    "- 問助理剛剛查了什麼、質疑或確認助理之前做過什麼（例如「那不是你查的吧」）、"
    "評論剛才的結果，都是 none，答案已在對話裡。\n"
    "- 只是談論遊戲、否定句（不用查、不要）、抱怨天氣、講自己做了什麼，都是 none。"
)
_ARG_PROMPT = (
    "你是 SIRO 的工具參數產生器。根據對話，為工具 {name} 產生呼叫參數，只輸出 JSON。\n"
    "工具說明：{description}\n"
    "現在時間：{now}。SIRO 在 Linux 上執行。參數要具體，帶入對話中的主題、地點和時間"
    "（把「今天、昨天、本週」換成日期）。claude.ask 的 task 一律用繁體中文。"
    "computer.execute 只能用會自己結束的非互動指令（例如 df -h、uptime、top -bn1），"
    "不要開 shell、編輯器或互動程式。"
)
# Programs that wait for a terminal. top is allowed only in batch mode (-b).
_INTERACTIVE = frozenset(
    {
        "htop", "btop", "vim", "vi", "nvim", "nano", "emacs", "less", "more", "watch", "ssh",
        "telnet", "ftp", "sftp", "man", "tmux", "screen", "bash", "sh", "zsh", "fish", "dash",
        "su", "sudo", "passwd", "mysql", "psql", "sqlite3", "ipython",
    }
)  # fmt: skip
_REPLS = frozenset({"python", "python3", "node", "irb", "lua", "R"})
_REFUSAL = re.compile(r"沒有.{0,8}工具|無法|做不到|不能直接|沒辦法|沒有權限|不具備")
_SECRET = re.compile(r"(?i)(?:sk|gsk|ghp|xox[abp])[-_][A-Za-z0-9_-]{8,}|bearer\s+\S+")

JsonChat = Callable[[str, str, Mapping[str, Any], int], Awaitable[str]]
GroqChat = Callable[[str, str], Awaitable[str]]
log = logging.getLogger(__name__)


def enabled(env: Mapping[str, str] | None = None) -> bool:
    return (os.environ if env is None else env).get(FLAG, "0") == "1"


def categories(tools: Sequence[ToolDefinition]) -> tuple[str, ...]:
    """``none`` plus each category whose tool is offered this turn."""
    names = {t.name for t in tools}
    return ("none", *(c for c, tool in CATEGORY_TOOL.items() if tool in names))


def router_prompt(menu: Sequence[str]) -> str:
    lines = "\n".join(_CATEGORY_TEXT[c] for c in menu)
    return (
        "你是聊天助理的工具路由器。讀使用者這一句話（參考最近的對話），選出助理這回合該用的工具，"
        f'只輸出 JSON {{"tool": "..."}}，tool 只能是：{", ".join(menu)}。\n{lines}\n{_RULES}'
    )


def context_message(text: str, recent_user: Sequence[str], prev_reply: str) -> str:
    recent = " | ".join(_clean(u)[:CONTEXT_CHARS] for u in recent_user[-2:]) or "(無)"
    previous = _clean(prev_reply)[:CONTEXT_CHARS] or "(無)"
    return (
        f"最近的使用者訊息（舊到新）：{recent}\nSIRO 上一句回覆：{previous}\n"
        f"使用者現在說：{_clean(text)[:MAX_TEXT]}"
    )


def _clean(text: str) -> str:
    return _SECRET.sub("[redacted]", " ".join(str(text).split()))


def interactive_argv(argv: Sequence[str]) -> bool:
    """True when the command would wait for a terminal instead of finishing."""
    if not argv:
        return True
    program = os.path.basename(argv[0])
    if program == "top":
        return not any(a == "-b" or (a.startswith("-") and "b" in a[1:]) for a in argv[1:])
    if program in _REPLS:
        return len(argv) == 1 or argv[1] in {"-i", "-"}
    return program in _INTERACTIVE


def valid_arguments(definition: ToolDefinition, arguments: object) -> bool:
    if not isinstance(arguments, dict) or not _valid_arguments(arguments, definition.input_schema):
        return False
    properties = definition.input_schema.get("properties", {})
    for key, value in arguments.items():
        rule = properties.get(key, {}) if isinstance(properties, dict) else {}
        if isinstance(value, str) and not (
            int(rule.get("minLength", 0)) <= len(value.strip()) <= int(rule.get("maxLength", 1e9))
        ):
            return False
    if definition.name == "computer.execute":
        argv = arguments.get("argv")
        return isinstance(argv, list) and not interactive_argv([str(a) for a in argv])
    return True


def likely_followup(prev_reply: str, last_turn_used_tool: bool) -> bool:
    return last_turn_used_tool or bool(_REFUSAL.search(prev_reply or ""))


def _parse_category(content: str, menu: Sequence[str]) -> str | None:
    content = re.sub(r"<think>.*?</think>", "", content or "", flags=re.S)
    match = re.search(r"\{.*\}", content, re.S)
    try:
        value = json.loads(match.group(0)).get("tool") if match else None
    except (json.JSONDecodeError, AttributeError):
        return None
    return value if value in menu else None


@dataclass(frozen=True, slots=True)
class Decision:
    category: str
    source: str
    call: ToolCall | None
    args_ok: bool | None
    latency_s: float


class ToolDecider:
    def __init__(
        self,
        *,
        chat: JsonChat,
        groq: GroqChat | None = None,
        log_path: Path | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._chat = chat
        self._groq = groq
        self._log_path = log_path
        self._clock = clock or (lambda: datetime.now().astimezone())

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ToolDecider | None:
        values = os.environ if env is None else env
        model = values.get(MODEL_ENV) or values.get("SIRO_OLLAMA_MODEL")
        if not enabled(values) or not model:
            return None
        data = Path(values.get("SIRO_DATA_DIR", ".siro-data"))
        return cls(
            chat=ollama_json_chat(model, values),
            groq=groq_chat(values),
            log_path=data / LOG_NAME,
        )

    async def decide(
        self,
        text: str,
        tools: Sequence[ToolDefinition],
        *,
        recent_user: Sequence[str] = (),
        prev_reply: str = "",
        last_turn_used_tool: bool = False,
        cloud_allowed: bool = False,
    ) -> Decision:
        started = time.perf_counter()
        menu = categories(tools)
        decision = Decision("none", "local", None, None, 0.0)
        if len(menu) > 1 and text.strip():
            decision = await self._decide(
                text, tools, menu, recent_user, prev_reply, last_turn_used_tool, cloud_allowed
            )
        decision = replace(decision, latency_s=round(time.perf_counter() - started, 3))
        self._log(text, decision)
        return decision

    async def _decide(
        self,
        text: str,
        tools: Sequence[ToolDefinition],
        menu: Sequence[str],
        recent_user: Sequence[str],
        prev_reply: str,
        last_turn_used_tool: bool,
        cloud_allowed: bool,
    ) -> Decision:
        system = router_prompt(menu)
        user = context_message(text, recent_user, prev_reply)
        schema = {
            "type": "object",
            "properties": {"tool": {"type": "string", "enum": list(menu)}},
            "required": ["tool"],
        }
        try:
            category = _parse_category(await self._chat(system, user, schema, 30), menu)
        except Exception as error:  # any local failure means no decision
            log.info("tool decision unavailable: %s", type(error).__name__)
            return Decision("error", "local", None, None, 0.0)
        source = "local"
        if (
            category == "none"
            and self._groq is not None
            and cloud_allowed
            and likely_followup(prev_reply, last_turn_used_tool)
        ):
            try:
                reviewed = _parse_category(await self._groq(system, user), menu)
            except Exception as error:  # Groq is optional; keep the local answer
                log.info("tool decision review unavailable: %s", type(error).__name__)
                reviewed = None
            if reviewed is not None:
                category, source = reviewed, "groq"
        if category is None:
            return Decision("invalid", source, None, None, 0.0)
        if category == "none":
            return Decision("none", source, None, None, 0.0)
        definition = next(t for t in tools if t.name == CATEGORY_TOOL[category])
        arguments = await self._arguments(definition, user)
        ok = arguments is not None and valid_arguments(definition, arguments)
        call = (
            ToolCall(f"decision-{uuid4()}", definition.name, arguments)
            if ok and arguments is not None
            else None
        )
        return Decision(category, source, call, ok, 0.0)

    async def _arguments(self, definition: ToolDefinition, user: str) -> dict[str, object] | None:
        if not definition.input_schema.get("properties"):
            return {}
        system = _ARG_PROMPT.format(
            name=definition.name,
            description=definition.description,
            now=self._clock().strftime("%Y-%m-%d %H:%M %A"),
        )
        try:
            raw = await self._chat(system, user, definition.input_schema, 300)
            value = json.loads(raw)
        except Exception as error:  # invalid arguments mean no decision
            log.info("tool arguments unavailable: %s", type(error).__name__)
            return None
        return value if isinstance(value, dict) else None

    def _log(self, text: str, decision: Decision) -> None:
        if self._log_path is None:
            return
        record = {
            "at": self._clock().isoformat(timespec="seconds"),
            "text": _clean(text)[:120],
            "choice": decision.category,
            "tool": decision.call.name if decision.call else None,
            "source": decision.source,
            "args_ok": decision.args_ok,
            "latency_s": decision.latency_s,
        }
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            log.warning("tool decision log unavailable")


def ollama_json_chat(model: str, env: Mapping[str, str] | None = None) -> JsonChat:
    values = os.environ if env is None else env
    host = (values.get("OLLAMA_HOST") or "127.0.0.1:11434").strip()
    base = host.rstrip("/") if host.startswith(("http://", "https://")) else f"http://{host}"

    async def chat(system: str, user: str, schema: Mapping[str, Any], num_predict: int) -> str:
        options: dict[str, object] = {
            "temperature": 0,
            "num_predict": num_predict,
            "num_ctx": ollama_options.context_length(values, model, NUM_CTX),
        }
        if (layers := ollama_options.gpu_layers(values, model)) is not None:
            options["num_gpu"] = layers
        async with httpx.AsyncClient(trust_env=False, timeout=LOCAL_TIMEOUT) as client:
            response = await client.post(
                f"{base}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "think": False,
                    "format": dict(schema),
                    "options": options,
                    "keep_alive": ollama_options.keep_alive(values),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
        response.raise_for_status()
        body = response.json()
        if body.get("done") is not True or body.get("done_reason") != "stop":
            raise ValueError("incomplete decision response")
        return str(body["message"].get("content") or "")

    return chat


def groq_chat(env: Mapping[str, str] | None = None) -> GroqChat | None:
    """Groq through the existing OpenAI-compatible adapter; None without a key."""
    values = os.environ if env is None else env
    key = values.get("SIRO_OPENAI_API_KEY", "")
    if not key:
        return None
    from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter

    adapter = OpenAICompatibleAdapter(
        base_url=values.get("SIRO_OPENAI_BASE_URL") or "https://api.groq.com/openai",
        api_key=key,
        model=values.get(GROQ_MODEL_ENV) or DEFAULT_GROQ_MODEL,
        timeout=GROQ_TIMEOUT,
    )

    async def chat(system: str, user: str) -> str:
        request = ModelRequest(
            "",
            str(uuid4()),
            Privacy.CLOUD_ALLOWED,
            max_output_tokens=400,
            messages=(ModelMessage("system", system), ModelMessage("user", user)),
        )
        pieces: list[str] = []
        async with asyncio.timeout(GROQ_TIMEOUT):
            async for chunk in adapter.stream(request, CancellationToken()):
                if chunk.kind == "text":
                    pieces.append(chunk.text)
        return "".join(pieces)

    return chat


# ---- handing a decided call to the conversation ----

_FORCED: ContextVar[list[ToolCall] | None] = ContextVar("siro_decided_tool_call", default=None)


@contextmanager
def decided_tool_call(call: ToolCall | None) -> Iterator[None]:
    """Within this block the next model request offering the tool returns ``call`` instead."""
    token = _FORCED.set([call] if call is not None else None)
    try:
        yield
    finally:
        _FORCED.reset(token)


class DecidedToolModel:
    """Wraps the conversation model; emits a decided call once, otherwise delegates."""

    def __init__(self, inner: LanguageModel) -> None:
        self._inner = inner
        self.name = inner.name

    def __getattr__(self, attribute: str) -> Any:
        return getattr(self._inner, attribute)

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        pending = _FORCED.get()
        if pending and any(t.name == pending[0].name for t in request.tools):
            call = pending.pop()
            if not cancellation.cancelled:
                yield ModelChunk("tool_request", tool_call=call)
            return
        async for chunk in self._inner.stream(request, cancellation):
            yield chunk
