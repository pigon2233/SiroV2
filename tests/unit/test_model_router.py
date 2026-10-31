"""Task routing, Claude's rolling budget, and fallback. No live provider is called."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from siro.adapters.models.claude_cli import (
    ClaudeCliModel,
    ClaudeRateLimited,
    interpret_cli_result,
    parse_tool_reply,
)
from siro.adapters.models.ollama import OllamaAdapter
from siro.adapters.models.router import (
    WINDOW,
    ClaudeBudget,
    ModelRouter,
    RouteProvider,
    RouteStatus,
    choose_conversation_model,
    classify_request,
    classify_user_text,
    router_enabled,
)
from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
    ToolDefinition,
)


class Script:
    def __init__(self, label: str, error: Exception | None = None) -> None:
        self.name = label
        self.error = error
        self.calls = 0

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        del request, cancellation
        self.calls += 1
        if self.error is not None:
            raise self.error
        yield ModelChunk("text", self.name)
        yield ModelChunk("finished")


class Partial:
    name = "partial-claude"

    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        del request, cancellation
        self.calls += 1
        yield ModelChunk("text", "已經開始")
        raise ConnectionError("after text")


def _request(
    text: str, *, privacy: Privacy = Privacy.CLOUD_ALLOWED, tokens: int = 1536
) -> ModelRequest:
    return ModelRequest(text, "gen-1", privacy, max_output_tokens=tokens)


def _collect(router: ModelRouter, request: ModelRequest) -> list[ModelChunk]:
    async def run() -> list[ModelChunk]:
        chunks: list[ModelChunk] = []
        async for chunk in router.stream(request, CancellationToken()):
            chunks.append(chunk)
        return chunks

    return asyncio.run(run())


def test_classifier_keeps_chat_local_and_sends_work_upward() -> None:
    assert classify_user_text("你好") == "local"
    assert classify_user_text("今天過得怎麼樣") == "local"
    assert classify_user_text("幫我寫一個 python 排序函式") == "reason"
    assert classify_user_text("請規劃三個步驟來重構這段程式") == "reason"
    assert classify_user_text("x" * 480) == "reason"
    assert classify_user_text("我的 api key 是 secret 幫我寫程式") == "local"
    coded = _request("幫我寫程式", privacy=Privacy.LOCAL_ONLY)
    assert classify_request(coded) == "local"
    short = _request("幫我寫程式", tokens=120)
    assert classify_request(short) == "local"
    continued = ModelRequest(
        "continue",
        "gen-2",
        Privacy.CLOUD_ALLOWED,
        max_output_tokens=1536,
        messages=(
            ModelMessage("user", "你好"),
            ModelMessage("assistant", "", tool_calls=(ToolCall("c1", "browser.read", {}),)),
            ModelMessage("tool", "page", tool_call_id="c1"),
        ),
    )
    assert classify_request(continued) == "reason"


def test_router_flag_keeps_the_historical_single_provider(tmp_path: Path) -> None:
    env = {
        "SIRO_OLLAMA_MODEL": "qwen3:4b",
        "SIRO_OPENAI_API_KEY": "synthetic-key",  # pragma: allowlist secret
        "SIRO_OPENAI_MODEL": "openai/gpt-oss-20b",
    }
    assert router_enabled(env) is False
    legacy = choose_conversation_model(env, data_dir=tmp_path)
    assert legacy.routed is False
    assert legacy.backend == "ollama:qwen3:4b"
    assert legacy.privacy is Privacy.LOCAL_ONLY
    assert isinstance(legacy.model, OllamaAdapter)
    with pytest.raises(ValueError, match="SIRO_MODEL_ROUTER"):
        router_enabled({"SIRO_MODEL_ROUTER": "2"})


def test_router_flag_uses_both_configured_providers(tmp_path: Path) -> None:
    env = {
        "SIRO_MODEL_ROUTER": "1",
        "SIRO_OLLAMA_MODEL": "qwen3:4b",
        "SIRO_OPENAI_API_KEY": "synthetic-key",  # pragma: allowlist secret
        "SIRO_OPENAI_MODEL": "openai/gpt-oss-20b",
        "SIRO_OPENAI_BASE_URL": "https://api.groq.com/openai",
    }
    choice = choose_conversation_model(env, data_dir=tmp_path)
    assert choice.routed is True
    assert choice.backend == "router"
    assert choice.privacy is Privacy.CLOUD_ALLOWED
    assert isinstance(choice.model, ModelRouter)
    assert choice.cloud_model == "openai/gpt-oss-20b"
    only_local = choose_conversation_model(
        {"SIRO_MODEL_ROUTER": "1", "SIRO_OLLAMA_MODEL": "qwen3:4b"}, data_dir=tmp_path
    )
    assert only_local.routed is False
    assert only_local.backend == "ollama:qwen3:4b"


def test_budget_window_persists_across_a_new_instance(tmp_path: Path) -> None:
    start = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)
    now = {"at": start}
    path = tmp_path / "claude-budget.json"
    first = ClaudeBudget(path, limit=2, clock=lambda: now["at"])

    async def fill() -> None:
        assert (await first.try_reserve()).allowed
        now["at"] = start + timedelta(minutes=1)
        assert (await first.try_reserve()).allowed
        blocked = await first.try_reserve()
        assert blocked.allowed is False
        assert blocked.reason == "budget"
        assert blocked.available_at == start + WINDOW

    asyncio.run(fill())
    restarted = ClaudeBudget(path, limit=2, clock=lambda: now["at"])
    assert restarted.peek().allowed is False
    now["at"] = start + WINDOW
    assert restarted.peek().allowed is True
    assert restarted.peek().remaining == 1
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["version"] == 1
    assert len(stored["calls"]) == 2


def test_unreadable_budget_does_not_call_claude(tmp_path: Path) -> None:
    path = tmp_path / "claude-budget.json"
    path.write_text("{", encoding="utf-8")
    budget = ClaudeBudget(path, limit=10)
    assert budget.peek().reason == "unreadable"
    claude, groq, local = Script("claude"), Script("groq"), Script("local")
    router = ModelRouter(
        (
            RouteProvider("local", "ollama:qwen", local),
            RouteProvider("groq", "groq:oss", groq),
            RouteProvider("claude", "claude:haiku", claude),
        ),
        budget=budget,
    )
    chunks = _collect(router, _request("幫我寫一個函式"))
    assert claude.calls == 0
    assert groq.calls == 1
    assert "".join(chunk.text for chunk in chunks) == "groq"
    assert router.turn_privacy("你好") is Privacy.LOCAL_ONLY
    assert router.turn_privacy("幫我寫一個函式") is Privacy.CLOUD_ALLOWED


def test_fallback_on_budget_rate_limit_and_provider_errors(tmp_path: Path) -> None:
    start = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)
    now = {"at": start}
    notices: list[str] = []
    statuses: list[RouteStatus] = []
    budget = ClaudeBudget(tmp_path / "budget.json", limit=1, clock=lambda: now["at"])
    claude = Script("claude")
    groq = Script("groq")
    local = Script("local")
    router = ModelRouter(
        (
            RouteProvider("local", "ollama:qwen", local),
            RouteProvider("groq", "groq:oss", groq),
            RouteProvider("claude", "claude:haiku", claude),
        ),
        budget=budget,
        on_status=statuses.append,
        on_notice=lambda _request, text: _record(notices, text),
        clock=lambda: now["at"],
    )
    assert _collect(router, _request("你好"))[-2].text == "local"
    assert claude.calls == 0
    assert budget.peek().remaining == 1
    first = _collect(router, _request("幫我除錯這段 python"))
    assert first[-2].text == "claude"
    assert statuses[-1].label == "claude:haiku"
    assert statuses[-1].notice == ""
    second = _collect(router, _request("請規劃重構步驟"))
    assert second[-2].text == "groq"
    assert claude.calls == 1
    assert "次數已用完" in notices[-1]
    assert "改用Groq" in notices[-1]
    assert statuses[-1].available_at == (start + WINDOW).isoformat()
    assert "可以再用" in notices[-1]

    limited = Script("claude", ClaudeRateLimited(start + timedelta(minutes=30)))
    fresh = ClaudeBudget(tmp_path / "rate.json", limit=5, clock=lambda: now["at"])
    groq_calls = Script("groq")
    limited_router = ModelRouter(
        (
            RouteProvider("local", "ollama:qwen", local),
            RouteProvider("groq", "groq:oss", groq_calls),
            RouteProvider("claude", "claude:haiku", limited),
        ),
        budget=fresh,
        on_notice=lambda _request, text: _record(notices, text),
        cooldown=timedelta(minutes=15),
        clock=lambda: now["at"],
    )
    assert _collect(limited_router, _request("幫我寫程式"))[-2].text == "groq"
    assert "被限流" in notices[-1]
    assert limited.calls == 1
    assert _collect(limited_router, _request("再寫一個函式"))[-2].text == "groq"
    assert limited.calls == 1

    broken = Script("groq", ConnectionError("down"))
    home = Script("local")
    cloud_router = ModelRouter(
        (RouteProvider("local", "ollama:qwen", home), RouteProvider("groq", "groq:oss", broken)),
        on_notice=lambda _request, text: _record(notices, text),
    )
    assert _collect(cloud_router, _request("幫我實作這個函式"))[-2].text == "local"
    assert "本機模型" in notices[-1]


async def _record(notices: list[str], text: str) -> None:
    notices.append(text)


def test_partial_output_is_not_retried_on_another_provider() -> None:
    claude = Partial()
    groq = Script("groq")
    router = ModelRouter(
        (RouteProvider("groq", "groq:oss", groq), RouteProvider("claude", "claude:haiku", claude))
    )
    with pytest.raises(ConnectionError):
        _collect(router, _request("幫我寫程式"))
    assert claude.calls == 1
    assert groq.calls == 0


def test_local_only_and_cloud_switch_never_leave_the_machine() -> None:
    claude, groq, local = Script("claude"), Script("groq"), Script("local")
    enabled = {"cloud": False}
    router = ModelRouter(
        (
            RouteProvider("local", "ollama:qwen", local),
            RouteProvider("groq", "groq:oss", groq),
            RouteProvider("claude", "claude:haiku", claude),
        ),
        cloud_enabled=lambda: enabled["cloud"],
    )
    _collect(router, _request("幫我寫一個 python 函式", privacy=Privacy.LOCAL_ONLY))
    _collect(router, _request("幫我寫一個 python 函式"))
    assert claude.calls == 0
    assert groq.calls == 0
    assert local.calls == 2
    enabled["cloud"] = True
    _collect(router, _request("幫我寫一個 python 函式"))
    assert claude.calls == 1


def test_secret_without_a_local_model_is_not_sent(tmp_path: Path) -> None:
    groq = Script("groq")
    router = ModelRouter((RouteProvider("groq", "groq:oss", groq),))
    chunks = _collect(router, _request("我的密碼是 hunter2 幫我寫登入"))
    assert groq.calls == 0
    assert "沒有送出" in "".join(chunk.text for chunk in chunks)
    del tmp_path


def test_claude_cli_result_and_tool_json() -> None:
    now = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)
    with pytest.raises(ClaudeRateLimited) as limited:
        interpret_cli_result(
            {"returncode": 1, "stdout": "", "stderr": "usage limit reached, retry in 30 seconds"},
            now=now,
        )
    assert limited.value.retry_at == now + timedelta(seconds=30)
    answer = interpret_cli_result(
        {
            "returncode": 0,
            "stdout": json.dumps({"is_error": False, "result": "好的"}),
            "stderr": "",
        },
        now=now,
    )
    assert answer == "好的"
    request = ModelRequest(
        "做",
        "gen",
        Privacy.CLOUD_ALLOWED,
        tools=(ToolDefinition("browser.read", "read", {"type": "object"}),),
    )
    raw = (
        '```json\n{"tool_calls":[{"name":"browser.read",'
        '"arguments":{"url":"https://example.test"}}]}\n```'
    )
    calls = parse_tool_reply(raw, request)
    assert calls is not None
    assert calls[0].name == "browser.read"
    assert calls[0].arguments["url"] == "https://example.test"


def test_claude_cli_refuses_local_only_before_the_runner(tmp_path: Path) -> None:
    binary = tmp_path / "claude"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")

    async def runner(*args: object, **kwargs: object) -> dict[str, object]:
        del args, kwargs
        raise AssertionError("runner must not start")

    model = ClaudeCliModel(model="haiku", binary=binary, runner=runner, timeout=30)

    async def run() -> None:
        with pytest.raises(PermissionError):
            async for _chunk in model.stream(
                _request("hi", privacy=Privacy.LOCAL_ONLY), CancellationToken()
            ):
                raise AssertionError("no chunk")

    asyncio.run(run())
