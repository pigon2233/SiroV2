# ruff: noqa: RUF001
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, ToolCall
from siro.services.agent import tool_decision as td
from siro.services.tools.claude import CLAUDE_DEFINITION
from siro.services.tools.orchestrator import DEFAULT_MODEL_TOOLS
from siro.services.tools.workspace import WORKSPACE_TOOLS

EXECUTE = next(t for t in DEFAULT_MODEL_TOOLS if t.name == "computer.execute")
TOOLS = (EXECUTE, CLAUDE_DEFINITION, *WORKSPACE_TOOLS)
NOW = datetime(2026, 11, 17, 21, 0).astimezone()


class FakeChat:
    """Answers the category question, then the argument question."""

    def __init__(self, category: str, arguments: object = None, *, fail: bool = False) -> None:
        self.category = category
        self.arguments = arguments
        self.fail = fail
        self.calls: list[tuple[str, str, Mapping[str, Any], int]] = []

    async def __call__(
        self, system: str, user: str, schema: Mapping[str, Any], num_predict: int
    ) -> str:
        self.calls.append((system, user, schema, num_predict))
        if self.fail:
            raise TimeoutError
        if len(self.calls) == 1:
            return json.dumps({"tool": self.category})
        return json.dumps(self.arguments)


class FakeGroq:
    def __init__(self, category: str) -> None:
        self.category = category
        self.calls = 0

    async def __call__(self, system: str, user: str) -> str:
        self.calls += 1
        return '<think>x</think>{"tool": "' + self.category + '"}'


def decider(chat: FakeChat, groq: FakeGroq | None = None, log: Path | None = None):
    return td.ToolDecider(chat=chat, groq=groq, log_path=log, clock=lambda: NOW)


@pytest.mark.asyncio
async def test_decides_research_with_valid_arguments_and_logs(tmp_path: Path) -> None:
    chat = FakeChat("research", {"task": "查詢 2026-11-17 高雄的氣溫"})
    log = tmp_path / "decisions.jsonl"
    decision = await decider(chat, log=log).decide("高雄現在幾度？", TOOLS)
    assert decision.category == "research" and decision.args_ok is True
    assert decision.call is not None and decision.call.name == "claude.ask"
    assert decision.call.arguments == {"task": "查詢 2026-11-17 高雄的氣溫"}
    # The menu lists only the tools offered this turn and enforces them with an enum.
    system, _, schema, _ = chat.calls[0]
    assert "play" not in schema["properties"]["tool"]["enum"]
    assert "play：" not in system and "research：" in system
    # The argument step uses the tool's own schema and carries today's date.
    assert chat.calls[1][2] == CLAUDE_DEFINITION.input_schema
    assert "2026-11-17" in chat.calls[1][0]
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert record["choice"] == "research" and record["source"] == "local"
    assert record["args_ok"] is True and record["text"] == "高雄現在幾度？"


@pytest.mark.asyncio
async def test_none_and_failures_mean_no_call() -> None:
    assert (await decider(FakeChat("none")).decide("早安", TOOLS)).call is None
    failed = await decider(FakeChat("research", fail=True)).decide("查天氣", TOOLS)
    assert failed.call is None and failed.category == "error"
    # A category outside the offered menu is ignored.
    play = await decider(FakeChat("play", {"goal": "玩"})).decide("幫我玩", TOOLS)
    assert play.call is None and play.category == "invalid"
    # No tools offered: no model call at all.
    chat = FakeChat("research")
    assert (await decider(chat).decide("查天氣", ())).call is None
    assert chat.calls == []


@pytest.mark.asyncio
async def test_invalid_arguments_are_dropped() -> None:
    bad = await decider(FakeChat("files_read", {"file": "a.txt"})).decide("讀 a.txt", TOOLS)
    assert bad.call is None and bad.args_ok is False
    short = await decider(FakeChat("research", {"task": "x"})).decide("查", TOOLS)
    assert short.call is None  # claude.ask requires at least two characters


@pytest.mark.parametrize(
    ("argv", "blocked"),
    [
        (["top"], True),
        (["top", "-bn1"], False),
        (["top", "-b", "-n", "1"], False),
        (["htop"], True),
        (["/usr/bin/vim", "a"], True),
        (["less", "x"], True),
        (["python3"], True),
        (["python3", "-c", "print(1)"], False),
        (["ssh", "host"], True),
        (["df", "-h"], False),
        (["uptime"], False),
        ([], True),
    ],
)
def test_interactive_commands_are_blocked(argv: list[str], blocked: bool) -> None:
    assert td.interactive_argv(argv) is blocked


@pytest.mark.asyncio
async def test_execute_decision_rejects_interactive_program() -> None:
    top = await decider(FakeChat("execute", {"argv": ["top"]})).decide("CPU 用量", TOOLS)
    assert top.call is None and top.args_ok is False
    batch = await decider(FakeChat("execute", {"argv": ["top", "-bn1"]})).decide("CPU", TOOLS)
    assert batch.call is not None and batch.call.arguments == {"argv": ["top", "-bn1"]}


@pytest.mark.asyncio
async def test_groq_reviews_only_likely_followups_when_cloud_allowed() -> None:
    groq = FakeGroq("research")
    plain = await decider(FakeChat("none"), groq).decide("我好累", TOOLS, cloud_allowed=True)
    assert plain.call is None and groq.calls == 0
    # Follow-up after a tool turn, but cloud not allowed: Groq stays unused.
    local_only = await decider(FakeChat("none"), groq).decide(
        "為什麼跌這麼多", TOOLS, last_turn_used_tool=True, cloud_allowed=False
    )
    assert local_only.call is None and groq.calls == 0
    reviewed = await decider(FakeChat("none", {"task": "查台積電下跌原因"}), groq).decide(
        "為什麼跌這麼多", TOOLS, last_turn_used_tool=True, cloud_allowed=True
    )
    assert groq.calls == 1 and reviewed.source == "groq"
    assert reviewed.call is not None and reviewed.call.name == "claude.ask"
    # A refusal in SIRO's previous reply also counts as a likely follow-up.
    refusal = FakeGroq("none")
    await decider(FakeChat("none"), refusal).decide(
        "你不能查嗎", TOOLS, prev_reply="我無法取得即時資料。", cloud_allowed=True
    )
    assert refusal.calls == 1


@pytest.mark.asyncio
async def test_groq_failure_keeps_local_answer() -> None:
    async def broken(system: str, user: str) -> str:
        raise TimeoutError

    decision = await td.ToolDecider(chat=FakeChat("none"), groq=broken).decide(
        "那高雄呢", TOOLS, last_turn_used_tool=True, cloud_allowed=True
    )
    assert decision.category == "none" and decision.source == "local"


def test_context_message_carries_recent_dialogue_and_redacts_secrets() -> None:
    message = td.context_message(
        "那高雄呢", ["一", "今天台北天氣怎樣"], "我幫你查台北 gsk_abcdefghijklmnop"
    )
    assert "今天台北天氣怎樣" in message and "那高雄呢" in message
    assert "gsk_abcdefghijklmnop" not in message


def test_flag_off_builds_no_decider() -> None:
    assert td.ToolDecider.from_env({"SIRO_OLLAMA_MODEL": "gemma4:e4b"}) is None
    assert td.ToolDecider.from_env({"SIRO_TOOL_DECISION": "1"}) is None  # no local model
    built = td.ToolDecider.from_env({"SIRO_TOOL_DECISION": "1", "SIRO_OLLAMA_MODEL": "m"})
    assert built is not None


class Inner:
    name = "inner"

    def __init__(self) -> None:
        self.requests = 0

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests += 1
        yield ModelChunk("text", "hi")


async def collect(model: td.DecidedToolModel, request: ModelRequest) -> list[ModelChunk]:
    return [chunk async for chunk in model.stream(request, CancellationToken())]


@pytest.mark.asyncio
async def test_decided_call_is_emitted_once_then_delegates() -> None:
    inner = Inner()
    model = td.DecidedToolModel(inner)
    request = ModelRequest("x", "g1", tools=TOOLS)
    call = ToolCall("decision-1", "computer.execute", {"argv": ["uptime"]})
    with td.decided_tool_call(call):
        first = await collect(model, request)
        second = await collect(model, request)
    assert [c.tool_call for c in first] == [call] and inner.requests == 1
    assert [c.text for c in second] == ["hi"]
    # Outside the block, or when the tool is not offered, the inner model answers.
    assert [c.text for c in await collect(model, request)] == ["hi"]
    with td.decided_tool_call(call):
        assert [c.text for c in await collect(model, ModelRequest("x", "g2"))] == ["hi"]
    assert model.name == "inner"
