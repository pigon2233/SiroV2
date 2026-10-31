"""Per-request model routing: local companionship, cloud reasoning, Claude budget.

`SIRO_MODEL_ROUTER=0` (the default) keeps the historical single-provider choice:
Ollama wins when `SIRO_OLLAMA_MODEL` is set, otherwise the OpenAI-compatible
cloud model, otherwise the offline demo. Routing starts only when the flag is
`1` and at least two providers are configured.

Classifier is heuristic on purpose. A local-model classifier would occupy the
same 8GB GPU the 4B model already shares with speech, and it would add a
round trip before every reply. Keywords, length, privacy and tool history are
enough to keep small talk local and send coding, planning and tool
continuations upward. Ambiguous text stays local so Claude's budget is not
spent on companionship.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter

from siro.adapters.models.claude_cli import ClaudeCliModel, ClaudeRateLimited
from siro.ports.models import (
    CancellationToken,
    LanguageModel,
    ModelChunk,
    ModelRequest,
    Privacy,
)

_LOG = logging.getLogger(__name__)
WINDOW = timedelta(hours=5)
DEFAULT_BUDGET = 10
DEFAULT_COOLDOWN_SECONDS = 900
LOCAL_CALL_MAX_TOKENS = 512
_LONG_TEXT = 480
TaskKind = Literal["local", "reason"]
BudgetReason = Literal["ok", "budget", "rate_limit", "unreadable", "disabled"]

_SENSITIVE = re.compile(
    r"(?:密碼|密码|身分證|身份证|信用卡號|信用卡号|私鑰|私钥|"
    r"api[\s_-]?key|secret[\s_-]?key|BEGIN (?:RSA |OPENSSH )?PRIVATE)",
    re.IGNORECASE,
)
_REASON = re.compile(
    r"(?:"
    r"寫程式|寫代碼|寫代码|寫一個|写一个|程式碼|"
    r"函式|函數|函数|除錯|调试|重構|重构|實作|实现|"
    r"演算法|算法|架構|架构|"
    r"幫我規劃|請規劃|请规划|規劃一下|规划一下|做個計畫|做個計劃|"
    r"分步驟|分步骤|一步一步|列出步驟|列出步骤|"
    r"debug|refactor|implement|step[- ]by[- ]step|"
    r"python|javascript|typescript|"
    r"```|def |class "
    r")",
    re.IGNORECASE,
)


def router_enabled(env: Mapping[str, str]) -> bool:
    value = env.get("SIRO_MODEL_ROUTER", "0")
    if value not in {"0", "1"}:
        raise ValueError("SIRO_MODEL_ROUTER must be 0 or 1")
    return value == "1"


def _flag(env: Mapping[str, str], name: str, *, default: str = "1") -> bool:
    value = env.get(name, default)
    if value not in {"0", "1"}:
        raise ValueError(f"{name} must be 0 or 1")
    return value == "1"


def _bounded_int(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def user_text(request: ModelRequest) -> str:
    for message in reversed(request.messages):
        if message.role == "user" and message.content.strip():
            return message.content
    return request.prompt


def classify_user_text(text: str) -> TaskKind:
    """Cheap task/chat split. Sensitive text and ordinary chat stay local."""
    stripped = text.strip()
    if not stripped or _SENSITIVE.search(stripped):
        return "local"
    if _REASON.search(stripped) or len(stripped) >= _LONG_TEXT:
        return "reason"
    return "local"


def classify_request(request: ModelRequest) -> TaskKind:
    """Route decision for one model call. LOCAL_ONLY never leaves the machine."""
    if request.privacy is not Privacy.CLOUD_ALLOWED:
        return "local"
    if request.max_output_tokens <= LOCAL_CALL_MAX_TOKENS:
        return "local"
    if _SENSITIVE.search(user_text(request)):
        return "local"
    if any(message.role == "tool" or message.tool_calls for message in request.messages):
        return "reason"
    return classify_user_text(user_text(request))


@dataclass(frozen=True, slots=True)
class BudgetView:
    allowed: bool
    remaining: int
    limit: int
    available_at: datetime | None
    reason: BudgetReason


@dataclass(frozen=True, slots=True)
class RouteProvider:
    kind: Literal["local", "groq", "claude"]
    label: str
    model: LanguageModel


@dataclass(frozen=True, slots=True)
class RouteStatus:
    label: str
    notice: str
    available_at: str | None


class ClaudeBudget:
    """Rolling 5-hour Claude call count, persisted so a restart does not reset it."""

    def __init__(
        self,
        path: Path,
        *,
        limit: int = DEFAULT_BUDGET,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not 0 <= limit <= 200:
            raise ValueError("Claude budget must be between 0 and 200 calls")
        self._path = path
        self._limit = limit
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()

    @property
    def limit(self) -> int:
        return self._limit

    def peek(self) -> BudgetView:
        now = self._clock()
        calls, rate_until, problem = self._load(now)
        if problem == "unreadable":
            return BudgetView(False, 0, self._limit, None, "unreadable")
        if self._limit == 0:
            return BudgetView(False, 0, 0, None, "disabled")
        remaining = self._limit - len(calls)
        blockers: list[tuple[BudgetReason, datetime]] = []
        if remaining <= 0 and calls:
            blockers.append(("budget", min(calls) + WINDOW))
        if rate_until is not None and rate_until > now:
            blockers.append(("rate_limit", rate_until))
        if not blockers:
            return BudgetView(True, remaining, self._limit, None, "ok")
        reason, when = max(blockers, key=lambda item: item[1])
        return BudgetView(False, max(0, remaining), self._limit, when, reason)

    async def snapshot(self) -> BudgetView:
        async with self._lock:
            return self.peek()

    async def try_reserve(self) -> BudgetView:
        """Count one Claude attempt. A refused view does not consume a slot."""
        async with self._lock:
            view = self.peek()
            if not view.allowed:
                return view
            now = self._clock()
            calls, rate_until, _problem = self._load(now)
            self._write([*calls, now], rate_until)
            # The slot just taken still counts as allowed for this caller, even when it
            # was the last one in the window.
            updated = self.peek()
            return BudgetView(True, updated.remaining, self._limit, None, "ok")

    async def note_rate_limit(self, until: datetime) -> None:
        async with self._lock:
            now = self._clock()
            calls, current, problem = self._load(now)
            if problem == "unreadable":
                return
            later = until if current is None or until > current else current
            self._write(calls, later)

    def _load(self, now: datetime) -> tuple[list[datetime], datetime | None, str]:
        if not self._path.is_file():
            return [], None, ""
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return [], None, "unreadable"
        if not isinstance(raw, dict):
            return [], None, "unreadable"
        stored = raw.get("calls")
        if not isinstance(stored, list):
            return [], None, "unreadable"
        calls: list[datetime] = []
        for item in stored:
            if not isinstance(item, str):
                return [], None, "unreadable"
            try:
                parsed = datetime.fromisoformat(item)
            except ValueError:
                return [], None, "unreadable"
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            calls.append(parsed.astimezone(UTC))
        rate_raw = raw.get("rate_limited_until")
        rate_until: datetime | None = None
        if rate_raw is not None:
            if not isinstance(rate_raw, str):
                return [], None, "unreadable"
            try:
                rate_until = datetime.fromisoformat(rate_raw)
            except ValueError:
                return [], None, "unreadable"
            if rate_until.tzinfo is None:
                rate_until = rate_until.replace(tzinfo=UTC)
            rate_until = rate_until.astimezone(UTC)
        active = [call for call in calls if now < call + WINDOW]
        return active, rate_until, ""

    def _write(self, calls: list[datetime], rate_until: datetime | None) -> None:
        payload = {
            "version": 1,
            "calls": [call.astimezone(UTC).isoformat() for call in calls],
            "rate_limited_until": None
            if rate_until is None
            else rate_until.astimezone(UTC).isoformat(),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        os.chmod(temporary, 0o600)
        os.replace(temporary, self._path)


def _provider_phrase(label: str) -> str:
    if label.startswith("ollama:"):
        return "本機模型"
    if label.startswith("groq:"):
        return "Groq"
    if label.startswith("cloud:"):
        return "雲端模型"
    return label


def _when(moment: datetime | None) -> str:
    if moment is None:
        return ""
    return moment.astimezone().strftime("%Y-%m-%d %H:%M")


def fallback_notice(reason: str, label: str, available_at: datetime | None, *, limit: int) -> str:
    target = _provider_phrase(label)
    when = _when(available_at)
    if reason == "budget":
        follow = f"Claude 預計 {when} 可以再用。" if when else ""
        return (
            f"Claude 在這 5 小時內的次數已用完（上限 {limit} 次），這次回覆改用{target}。{follow}"  # noqa: RUF001
        )
    if reason == "rate_limit":
        follow = f"預計 {when} 之後可以再試 Claude。" if when else "稍後會再試 Claude。"
        return f"Claude 目前被限流，這次回覆改用{target}。{follow}"  # noqa: RUF001
    if reason == "unreadable":
        return f"Claude 的額度紀錄讀不到，這次回覆改用{target}。"  # noqa: RUF001
    if reason == "disabled":
        return f"Claude 次數上限是 0，這次回覆改用{target}。"  # noqa: RUF001
    return f"Claude 這次沒有回應，已改用{target}。"  # noqa: RUF001


class ModelRouter:
    """Pick Claude, then Groq, then local Ollama for one request."""

    def __init__(
        self,
        providers: tuple[RouteProvider, ...],
        *,
        budget: ClaudeBudget | None = None,
        cloud_enabled: Callable[[], bool] | None = None,
        on_status: Callable[[RouteStatus], None] | None = None,
        on_notice: Callable[[ModelRequest, str], Awaitable[None]] | None = None,
        cooldown: timedelta = timedelta(seconds=DEFAULT_COOLDOWN_SECONDS),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not providers:
            raise ValueError("at least one routed provider is required")
        if len({item.kind for item in providers}) != len(providers):
            raise ValueError("each routed provider kind can be configured once")
        self._providers = providers
        self._by_kind = {item.kind: item for item in providers}
        self._budget = budget
        self._cloud_enabled = cloud_enabled or (lambda: True)
        self._on_status = on_status
        self._on_notice = on_notice
        self._cooldown = cooldown
        self._clock = clock or (lambda: datetime.now(UTC))
        self.name = "router"
        self.last_model_name = providers[0].label

    def turn_privacy(self, text: str) -> Privacy:
        """Privacy for prompt assembly. Simple and sensitive turns stay local_only."""
        local = self._by_kind.get("local")
        if local is None:
            return Privacy.CLOUD_ALLOWED
        if not self._cloud_enabled():
            return Privacy.LOCAL_ONLY
        if classify_user_text(text) == "local":
            return Privacy.LOCAL_ONLY
        return Privacy.CLOUD_ALLOWED

    def claude_available_at(self) -> str | None:
        if self._budget is None:
            return None
        view = self._budget.peek()
        if view.allowed or view.available_at is None:
            return None
        return view.available_at.isoformat()

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        if cancellation.cancelled:
            return
        decision = classify_request(request)
        cloud_open = request.privacy is Privacy.CLOUD_ALLOWED and self._cloud_enabled()
        secret = bool(_SENSITIVE.search(user_text(request)))
        chain, skip_reason, _reserved = await self._chain(decision, cloud_open, secret)
        if not chain:
            notice = self._no_provider_notice(secret, skip_reason)
            if notice:
                await self._announce_text(request, notice)
                yield ModelChunk("text", notice)
                yield ModelChunk("finished")
                return
            raise PermissionError("cloud egress requires cloud_allowed privacy")
        groq_failed = False
        last_error: Exception | None = None
        for index, provider in enumerate(chain):
            if cancellation.cancelled:
                return
            emitted = False
            announced = False
            try:
                async for chunk in provider.model.stream(request, cancellation):
                    if cancellation.cancelled:
                        return
                    if not announced:
                        await self._announce(request, provider, skip_reason, groq_failed)
                        announced = True
                    if (chunk.kind == "text" and chunk.text) or chunk.kind in {
                        "tool_request",
                        "finished",
                    }:
                        emitted = True
                    yield chunk
                if not announced:
                    await self._announce(request, provider, skip_reason, groq_failed)
                return
            except PermissionError:
                raise
            except ClaudeRateLimited as error:
                if emitted or index == len(chain) - 1:
                    raise
                await self._remember_rate_limit(error)
                skip_reason = "rate_limit"
                last_error = error
            except Exception as error:
                if emitted or cancellation.cancelled or index == len(chain) - 1:
                    raise
                if provider.kind == "groq":
                    groq_failed = True
                if provider.kind == "claude":
                    skip_reason = skip_reason or "unavailable"
                last_error = error
                _LOG.warning("model provider %s failed before output", provider.kind)
        if last_error is not None:
            raise last_error
        raise PermissionError("cloud egress requires cloud_allowed privacy")

    async def _chain(
        self, decision: TaskKind, cloud_open: bool, secret: bool
    ) -> tuple[list[RouteProvider], str, bool]:
        local = self._by_kind.get("local")
        groq = self._by_kind.get("groq")
        claude = self._by_kind.get("claude")
        if secret and local is None:
            return [], "", False
        if decision == "local" or not cloud_open:
            if local is not None:
                return [local], "", False
            if not cloud_open:
                return [], "", False
            if groq is not None:
                return [groq], "", False
            if claude is not None:
                return [claude], "", False
            return [], "", False
        chain: list[RouteProvider] = []
        skip = ""
        reserved = False
        if claude is not None and self._budget is not None:
            view = await self._budget.try_reserve()
            if view.allowed:
                chain.append(claude)
                reserved = True
            else:
                skip = view.reason
        elif claude is not None:
            chain.append(claude)
        if groq is not None:
            chain.append(groq)
        if local is not None:
            chain.append(local)
        return chain, skip, reserved

    async def _remember_rate_limit(self, error: ClaudeRateLimited) -> None:
        if self._budget is None:
            return
        now = self._clock()
        until = (
            error.retry_at
            if error.retry_at is not None and error.retry_at > now
            else now + self._cooldown
        )
        await self._budget.note_rate_limit(until)

    async def _announce(
        self,
        request: ModelRequest,
        provider: RouteProvider,
        skip_reason: str,
        groq_failed: bool,
    ) -> None:
        notice = ""
        if skip_reason and provider.kind != "claude":
            view = self._budget.peek() if self._budget is not None else None
            notice = fallback_notice(
                skip_reason,
                provider.label,
                None if view is None else view.available_at,
                limit=0 if self._budget is None else self._budget.limit,
            )
        elif groq_failed and provider.kind == "local":
            notice = "雲端模型這次沒有回應，已改用本機模型。"  # noqa: RUF001
        self.last_model_name = provider.label
        if self._on_status is not None:
            self._on_status(RouteStatus(provider.label, notice, self.claude_available_at()))
        if notice and self._on_notice is not None:
            try:
                await self._on_notice(request, notice)
            except Exception:
                _LOG.warning("model route notice could not be delivered")

    def _no_provider_notice(self, secret: bool, skip_reason: str) -> str:
        if secret:
            return "這段內容含有密碼或私鑰，而且沒有本機模型可以處理，所以沒有送出。"  # noqa: RUF001
        if not skip_reason or self._budget is None:
            return ""
        view = self._budget.peek()
        when = _when(view.available_at)
        limit = self._budget.limit
        if skip_reason == "budget":
            follow = f"Claude 預計 {when} 可以再用。" if when else ""
            return (
                f"Claude 在這 5 小時內的次數已用完（上限 {limit} 次），"  # noqa: RUF001
                f"目前沒有其他模型可以接手。{follow}"
            )
        if skip_reason == "rate_limit":
            follow = f"預計 {when} 之後可以再試。" if when else ""
            return f"Claude 目前被限流，而且沒有其他模型可以接手。{follow}"  # noqa: RUF001
        if skip_reason == "disabled":
            return "Claude 次數上限是 0，而且沒有其他模型可以接手。"  # noqa: RUF001
        if skip_reason == "unreadable":
            return "Claude 的額度紀錄讀不到，而且沒有其他模型可以接手。"  # noqa: RUF001
        return ""

    async def _announce_text(self, request: ModelRequest, notice: str) -> None:
        self.last_model_name = "unavailable"
        if self._on_status is not None:
            self._on_status(RouteStatus("unavailable", notice, self.claude_available_at()))
        if self._on_notice is not None:
            try:
                await self._on_notice(request, notice)
            except Exception:
                _LOG.warning("model route notice could not be delivered")


@dataclass(frozen=True, slots=True)
class ModelChoice:
    """Startup model selection. `routed` is false for the historical single provider."""

    model: LanguageModel
    backend: str
    privacy: Privacy
    measurement: OpenAICompatibleAdapter | None
    cloud_model: str | None
    routed: bool


def _ollama(model_name: str, env: Mapping[str, str]) -> LanguageModel:
    # Import at call time so tests can replace the adapter class before startup.
    from siro.adapters.models.ollama import OllamaAdapter

    raw = env.get("SIRO_OLLAMA_CONTEXT_LENGTH")
    return OllamaAdapter(
        model=model_name,
        thinking=False,
        context_length=int(raw) if raw else None,
    )


def _legacy_choice(env: Mapping[str, str]) -> ModelChoice:
    from siro.adapters.models.mock import OfflineDemoModel
    from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter

    ollama_model = env.get("SIRO_OLLAMA_MODEL")
    cloud_key = env.get("SIRO_OPENAI_API_KEY")
    cloud_model = env.get("SIRO_OPENAI_MODEL")
    if ollama_model:
        return ModelChoice(
            _ollama(ollama_model, env),
            f"ollama:{ollama_model}",
            Privacy.LOCAL_ONLY,
            None,
            None,
            False,
        )
    if cloud_key and cloud_model:
        base_url = env.get("SIRO_OPENAI_BASE_URL", "https://api.groq.com/openai")
        adapter = OpenAICompatibleAdapter(base_url=base_url, api_key=cloud_key, model=cloud_model)
        return ModelChoice(
            adapter,
            f"cloud:{cloud_model}",
            Privacy.CLOUD_ALLOWED,
            adapter,
            cloud_model,
            False,
        )
    return ModelChoice(OfflineDemoModel(), "offline", Privacy.LOCAL_ONLY, None, None, False)


def choose_conversation_model(
    env: Mapping[str, str],
    *,
    data_dir: Path,
    on_status: Callable[[RouteStatus], None] | None = None,
    on_notice: Callable[[ModelRequest, str], Awaitable[None]] | None = None,
    cloud_enabled: Callable[[], bool] | None = None,
    claude_binary: Path | None = None,
    claude_model_name: str | None = None,
    claude_environment: Mapping[str, str] | None = None,
    claude_runner: Callable[..., Awaitable[Mapping[str, object]]] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ModelChoice:
    """Select the conversation model. Router flag 0 preserves the historical priority."""
    if not router_enabled(env):
        return _legacy_choice(env)
    providers: list[RouteProvider] = []
    measurement: OpenAICompatibleAdapter | None = None
    cloud_model: str | None = None
    ollama_model = env.get("SIRO_OLLAMA_MODEL") or env.get("SIRO_LOCAL_FALLBACK_OLLAMA_MODEL")
    if ollama_model:
        providers.append(
            RouteProvider("local", f"ollama:{ollama_model}", _ollama(ollama_model, env))
        )
    cloud_key = env.get("SIRO_OPENAI_API_KEY")
    configured_cloud = env.get("SIRO_OPENAI_MODEL")
    if cloud_key and configured_cloud:
        from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter

        base_url = env.get("SIRO_OPENAI_BASE_URL", "https://api.groq.com/openai")
        adapter = OpenAICompatibleAdapter(
            base_url=base_url, api_key=cloud_key, model=configured_cloud
        )
        host = urlsplit(base_url).hostname or ""
        label = (
            f"groq:{configured_cloud}" if host == "api.groq.com" else f"cloud:{configured_cloud}"
        )
        providers.append(RouteProvider("groq", label, adapter))
        measurement = adapter
        cloud_model = configured_cloud
    claude_on = _flag(env, "SIRO_CLAUDE_ENABLED")
    if claude_on and claude_binary is not None and claude_binary.is_file():
        model_name = claude_model_name or env.get("SIRO_CLAUDE_MODEL") or "claude-haiku-5-5"
        timeout = float(_bounded_int(env, "SIRO_CLAUDE_TIMEOUT_SECONDS", 120, 10, 240))
        cli = ClaudeCliModel(
            model=model_name,
            binary=claude_binary,
            environment=claude_environment,
            runner=claude_runner,
            timeout=timeout,
            clock=clock,
        )
        providers.append(RouteProvider("claude", cli.name, cli))
    claude_only = len(providers) == 1 and providers[0].kind == "claude"
    if len(providers) < 2 and not claude_only:
        return _legacy_choice(env)
    limit = _bounded_int(env, "SIRO_CLAUDE_BUDGET_CALLS", DEFAULT_BUDGET, 0, 200)
    cooldown = _bounded_int(
        env, "SIRO_CLAUDE_RATE_LIMIT_COOLDOWN_SECONDS", DEFAULT_COOLDOWN_SECONDS, 0, 5 * 60 * 60
    )
    budget = None
    if any(item.kind == "claude" for item in providers):
        budget = ClaudeBudget(data_dir / "claude-budget.json", limit=limit, clock=clock)
    router = ModelRouter(
        tuple(providers),
        budget=budget,
        cloud_enabled=cloud_enabled,
        on_status=on_status,
        on_notice=on_notice,
        cooldown=timedelta(seconds=cooldown),
        clock=clock,
    )
    has_local = any(item.kind == "local" for item in providers)
    return ModelChoice(
        router,
        "router" if has_local else "cloud:router",
        Privacy.CLOUD_ALLOWED,
        measurement,
        cloud_model,
        True,
    )
