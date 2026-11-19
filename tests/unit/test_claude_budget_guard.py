"""One Claude budget for the router, tool, planner, profile, recap, and classifiers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from siro.adapters.models.claude_budget import (
    WINDOW,
    ClaudeBudget,
    reset_shared_claude_budget,
    shared_claude_budget,
)
from siro.adapters.models.router import ModelRouter, RouteProvider
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy
from siro.services.agent.addressee import Audience, Context, claude_classifier, judge
from siro.services.agent.auto_plan import claude_classifier as plan_classifier
from siro.services.agent.auto_plan import should_plan
from siro.services.agent.planning_adapters import ClaudePlannerModel
from siro.services.tools.claude import ClaudeUnavailable, ask_claude, complete_fallback

START = datetime(2026, 11, 16, 1, 0, tzinfo=UTC)


class Script:
    def __init__(self, label: str) -> None:
        self.name = label
        self.calls = 0

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        del request, cancellation
        self.calls += 1
        yield ModelChunk("text", self.name)
        yield ModelChunk("finished")


def _request(text: str) -> ModelRequest:
    return ModelRequest(text, "gen-1", Privacy.CLOUD_ALLOWED, max_output_tokens=1536)


@pytest.fixture(autouse=True)
def _fresh_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SIRO_CLAUDE_BUDGET_CALLS", raising=False)
    monkeypatch.delenv("SIRO_CLAUDE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("SIRO_CLAUDE_RATE_LIMIT_COOLDOWN_SECONDS", raising=False)
    for name in (
        "SIRO_OPENAI_API_KEY",
        "SIRO_OPENAI_MODEL",
        "SIRO_OLLAMA_MODEL",
        "SIRO_LOCAL_FALLBACK_OLLAMA_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    reset_shared_claude_budget()


def _binary(tmp_path: Path) -> Path:
    binary = tmp_path / "claude"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    return binary


def _ok(text: str = "DROP") -> dict[str, object]:
    return {"returncode": 0, "stdout": json.dumps({"is_error": False, "result": text})}


def test_callers_share_one_counter_and_block_without_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIRO_CLAUDE_BUDGET_CALLS", "6")
    now = {"at": START}
    budget = shared_claude_budget(clock=lambda: now["at"])
    assert shared_claude_budget() is budget
    binary = _binary(tmp_path)
    monkeypatch.setattr("siro.services.tools.claude.claude_binary", lambda: binary)
    spawns = {"n": 0}

    async def run(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        del argv, options
        spawns["n"] += 1
        return _ok()

    monkeypatch.setattr("siro.services.tools.claude.execute_bounded_argv", run)
    claude, groq, local = Script("claude"), Script("groq"), Script("local")
    router = ModelRouter(
        (
            RouteProvider("local", "ollama:qwen", local),
            RouteProvider("groq", "groq:oss", groq),
            RouteProvider("claude", "claude:haiku", claude),
        ),
        budget=budget,
        clock=lambda: now["at"],
    )

    async def exercise() -> None:
        chunks: list[ModelChunk] = []
        async for chunk in router.stream(_request("幫我寫一個 python 函式"), CancellationToken()):
            chunks.append(chunk)
        assert chunks[-2].text == "claude"
        await ask_claude({"task": "查天氣"}, binary=binary, caller="claude.ask")
        await ClaudePlannerModel("claude-haiku-5-5").complete("plan", "請規劃步驟")
        await ClaudePlannerModel("claude-haiku-5-5", caller="profile").complete(
            "profile", "整理偏好"
        )
        assert await claude_classifier("claude-haiku-5-5")("這句話", ()) is Audience.DROP
        assert await plan_classifier("claude-haiku-5-5")("先查") is False
        fallbacks = {"n": 0}

        async def fallback(prompt: str) -> tuple[str, str]:
            del prompt
            fallbacks["n"] += 1
            return "改用 Groq 的重點", "groq:test"

        blocked = await ask_claude(
            {"task": "今天的重點"}, binary=binary, caller="recap", fallback=fallback
        )
        assert blocked["fallback"] is True
        assert blocked["model"] == "groq:test"
        assert fallbacks["n"] == 1

    asyncio.run(exercise())
    assert claude.calls == 1
    assert spawns["n"] == 5
    assert groq.calls == 0
    stored = json.loads((tmp_path / "claude-budget.json").read_text(encoding="utf-8"))
    assert stored["version"] == 1
    assert stored["callers"] == [
        "router",
        "claude.ask",
        "planner",
        "profile",
        "addressee",
        "auto_plan",
    ]
    assert len(stored["calls"]) == 6
    assert (tmp_path / "claude-budget.json").stat().st_mode & 0o777 == 0o600
    blocked_view = budget.peek()
    assert blocked_view.allowed is False
    assert blocked_view.reason == "budget"
    assert blocked_view.available_at == START + WINDOW


def test_over_budget_uses_groq_then_ollama_without_spawning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIRO_CLAUDE_BUDGET_CALLS", "0")
    monkeypatch.setenv("SIRO_OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setenv("SIRO_OPENAI_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("SIRO_OPENAI_BASE_URL", "https://api.groq.com/openai")
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "qwen3:4b")
    seen: list[str] = []

    async def complete(kind: str, label: str, prompt: str, env: object) -> str:
        del prompt, env
        seen.append(f"{kind}:{label}")
        if kind == "openai":
            raise ConnectionError("groq down")
        return "本機接手"

    monkeypatch.setattr("siro.services.tools.claude._complete_target", complete)

    async def run(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        del argv, options
        raise AssertionError("cli must not start")

    result = asyncio.run(
        ask_claude({"task": "查天氣"}, binary=_binary(tmp_path), caller="claude.ask", run=run)
    )
    assert seen == ["openai:groq:openai/gpt-oss-20b", "ollama:ollama:qwen3:4b"]
    assert result["answer"] == "本機接手"
    assert result["model"] == "ollama:qwen3:4b"
    assert not (tmp_path / "claude-budget.json").exists()


def test_no_fallback_model_is_a_clear_unavailable_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIRO_CLAUDE_BUDGET_CALLS", "0")

    async def run(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        del argv, options
        raise AssertionError("cli must not start")

    async def blocked() -> None:
        with pytest.raises(ClaudeUnavailable, match="claude unavailable: budget is 0"):
            await ask_claude(
                {"task": "規劃一下"}, binary=_binary(tmp_path), caller="planner", run=run
            )

    asyncio.run(blocked())


def test_addressee_and_auto_plan_keep_their_local_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del tmp_path
    monkeypatch.setenv("SIRO_CLAUDE_BUDGET_CALLS", "0")
    spawns = {"n": 0}

    async def run(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        del argv, options
        spawns["n"] += 1
        return _ok("SIRO")

    monkeypatch.setattr("siro.services.tools.claude.execute_bounded_argv", run)

    async def exercise() -> None:
        verdict = await judge(
            "下午那件事要不要改到明天",
            Context(seconds_since_spoke=100),
            claude_classifier("claude-haiku-5-5"),
        )
        assert verdict.reason == "fallback"
        text = "先查三個公開來源 然後比較它們的說法 最後整理成一份研究筆記"
        assert await should_plan(text, plan_classifier("claude-haiku-5-5")) is True

    asyncio.run(exercise())
    assert spawns["n"] == 0


def test_rate_limit_cooldown_is_shared_with_the_router(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIRO_CLAUDE_BUDGET_CALLS", "10")
    now = {"at": START}
    budget = shared_claude_budget(clock=lambda: now["at"])
    binary = _binary(tmp_path)
    spawns = {"n": 0}

    async def limited(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        del argv, options
        spawns["n"] += 1
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "usage limit reached, retry in 30 seconds",
        }

    async def fallback(prompt: str) -> tuple[str, str]:
        del prompt
        return "groq answer", "groq:test"

    async def exercise() -> None:
        first = await ask_claude(
            {"task": "查天氣"}, binary=binary, caller="recap", run=limited, fallback=fallback
        )
        assert first["model"] == "groq:test"
        assert spawns["n"] == 1
        view = budget.peek()
        assert view.reason == "rate_limit"
        assert view.available_at == START + timedelta(seconds=30)
        claude, groq, local = Script("claude"), Script("groq"), Script("local")
        router = ModelRouter(
            (
                RouteProvider("local", "ollama:qwen", local),
                RouteProvider("groq", "groq:oss", groq),
                RouteProvider("claude", "claude:haiku", claude),
            ),
            budget=budget,
            clock=lambda: now["at"],
        )
        chunks: list[ModelChunk] = []
        async for chunk in router.stream(_request("幫我寫一個函式"), CancellationToken()):
            chunks.append(chunk)
        assert chunks[-2].text == "groq"
        assert claude.calls == 0

        async def boom(argv: tuple[str, ...], **options: object) -> dict[str, object]:
            del argv, options
            raise AssertionError("cli must stay cooled down")

        second = await ask_claude(
            {"task": "再查一次"}, binary=binary, caller="claude.ask", run=boom, fallback=fallback
        )
        assert second["fallback"] is True

    asyncio.run(exercise())
    assert spawns["n"] == 1


def test_unguarded_rate_limit_still_starts_the_shared_cooldown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = _binary(tmp_path)

    async def limited(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        del argv, options
        return {"returncode": 1, "stdout": "", "stderr": "429 too many requests"}

    async def exercise() -> None:
        with pytest.raises(ClaudeUnavailable):
            await ask_claude({"task": "查天氣"}, binary=binary, run=limited)
        assert shared_claude_budget().peek().reason == "rate_limit"

        async def boom(argv: tuple[str, ...], **options: object) -> dict[str, object]:
            del argv, options
            raise AssertionError("cli must stay cooled down")

        async def fallback(prompt: str) -> tuple[str, str]:
            del prompt
            return "later", "groq:test"

        cooled = await ask_claude(
            {"task": "再問一次"}, binary=binary, caller="planner", run=boom, fallback=fallback
        )
        assert cooled["model"] == "groq:test"

    asyncio.run(exercise())


def test_ask_claude_timeout_reads_the_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = _binary(tmp_path)
    seen: list[float] = []

    async def run(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        del argv
        timeout = options["timeout"]
        assert isinstance(timeout, int | float)
        seen.append(float(timeout))
        return _ok("ok")

    async def once() -> None:
        await ask_claude({"task": "hello"}, binary=binary, run=run)

    monkeypatch.setenv("SIRO_CLAUDE_TIMEOUT_SECONDS", "37")
    asyncio.run(once())
    monkeypatch.setenv("SIRO_CLAUDE_TIMEOUT_SECONDS", "10")
    asyncio.run(ask_claude({"task": "hello"}, binary=binary, caller="claude.ask", run=run))
    monkeypatch.delenv("SIRO_CLAUDE_TIMEOUT_SECONDS", raising=False)
    asyncio.run(once())
    assert seen == [37.0, 10.0, 120.0]
    monkeypatch.setenv("SIRO_CLAUDE_TIMEOUT_SECONDS", "9")

    async def rejected() -> None:
        with pytest.raises(ValueError, match="SIRO_CLAUDE_TIMEOUT_SECONDS"):
            await ask_claude({"task": "hello"}, binary=binary, run=run)

    asyncio.run(rejected())
    assert seen == [37.0, 10.0, 120.0]


def test_old_budget_file_without_callers_still_counts(tmp_path: Path) -> None:
    path = tmp_path / "claude-budget.json"
    path.write_text(
        json.dumps(
            {"version": 1, "calls": [START.isoformat()], "rate_limited_until": None},
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    budget = ClaudeBudget(path, limit=2, clock=lambda: START)

    async def fill() -> None:
        reserved = await budget.try_reserve("claude.ask")
        assert reserved.allowed is True
        assert reserved.remaining == 0

    asyncio.run(fill())
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["callers"] == ["", "claude.ask"]
    assert len(stored["calls"]) == 2


def test_threads_and_tasks_cannot_overshoot_the_limit(tmp_path: Path) -> None:
    path = tmp_path / "threads.json"
    limit = 25

    def burst(index: int) -> None:
        budget = ClaudeBudget(path, limit=limit)

        async def go() -> None:
            for _ in range(limit):
                await budget.try_reserve(f"t{index}")

        asyncio.run(go())

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(burst, range(4)))
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert len(stored["calls"]) == limit
    assert len(stored["callers"]) == limit

    async def gathered() -> int:
        other = tmp_path / "tasks.json"
        budget = ClaudeBudget(other, limit=20)
        views = await asyncio.gather(*[budget.try_reserve("async") for _ in range(40)])
        return sum(1 for view in views if view.allowed)

    assert asyncio.run(gathered()) == 20


def test_fallback_without_providers_raises() -> None:
    async def missing() -> None:
        with pytest.raises(ClaudeUnavailable, match="claude unavailable"):
            await complete_fallback("hello")

    asyncio.run(missing())
