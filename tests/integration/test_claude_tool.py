"""Claude as a read-only tool: only the task goes out, and its answer is labelled as Claude's."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_activity_monitor import ScriptedModel, activities_of, companion

from siro.ports.models import ModelChunk, ToolCall
from siro.services.activity.monitor import ActivityMonitor, describe_tool
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.agent.self_activity import SelfActivityOwner
from siro.services.agent.self_notes import SelfNotes, share_text
from siro.services.tools.claude import ClaudeUnavailable, ask_claude
from siro.services.tools.execution import ExecutionContext

pytestmark = pytest.mark.asyncio


async def test_claude_runs_with_only_the_task_and_a_restricted_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_OPENAI_API_KEY", "not-for-claude")  # pragma: allowlist secret
    seen: dict[str, object] = {}

    async def run(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        seen.update(argv=argv, **options)
        stdout = json.dumps(
            {"is_error": False, "result": "明天晚上台中多雲，23 度 https://www.cwa.gov.tw/x\n"}  # noqa: RUF001
        )
        return {"returncode": 0, "stdout": stdout}

    result = await ask_claude({"task": "查明天晚上台中的天氣"}, binary=Path("/opt/claude"), run=run)
    assert result == {
        "answer": "明天晚上台中多雲，23 度 https://www.cwa.gov.tw/x",  # noqa: RUF001
        "truncated": False,
        "model": "claude-haiku-5-5",
    }
    argv = seen["argv"]
    assert isinstance(argv, tuple)
    assert (
        argv[:2] == ("/opt/claude", "-p") and argv[argv.index("--model") + 1] == "claude-haiku-5-5"
    )
    assert argv[argv.index("--tools") + 1] == "WebSearch" and argv[-1].endswith(
        "查明天晚上台中的天氣"
    )
    environment = seen["environment"]
    assert isinstance(environment, dict) and "SIRO_OPENAI_API_KEY" not in environment

    async def quiet(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        seen["argv"] = argv
        return {"returncode": 0, "stdout": '{"result": "YES"}'}

    await ask_claude({"task": "分類"}, binary=Path("/opt/claude"), run=quiet, search=False)
    quiet_argv = seen["argv"]
    assert isinstance(quiet_argv, tuple) and quiet_argv[quiet_argv.index("--tools") + 1] == ""
    assert "--allowedTools" not in quiet_argv


async def test_claude_without_an_answer_fails_honestly() -> None:
    async def failing(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        return {"returncode": 1, "stdout": ""}

    async def errored(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        return {"returncode": 0, "stdout": '{"is_error": true, "result": "Not logged in"}'}

    for run in (failing, errored):
        with pytest.raises(ClaudeUnavailable):
            await ask_claude({"task": "查天氣"}, binary=Path("/opt/claude"), run=run)
    with pytest.raises(ValueError):
        await ask_claude({"task": "x"}, binary=Path("/opt/claude"), run=failing)


def test_monitor_shows_the_task_and_says_claude_network_is_unseen() -> None:
    described = describe_tool("claude.ask", {"task": "查天氣"}, {"answer": "多雲"})
    assert described == {
        "target": {"task": "查天氣"},
        "network": {
            "coverage": "unobserved",
            "requests": [],
            "gaps": ["external_agent_network_not_monitored"],
        },
    }


async def test_her_note_lists_claude_links_apart_from_pages_she_read(tmp_path: Path) -> None:
    async def claude(arguments: dict[str, object], context: ExecutionContext) -> object:
        return {"answer": "M42 是恆星形成區 https://example.test/m42。", "truncated": False}

    model = ScriptedModel(
        [[ToolCall("c1", "claude.ask", {"task": "M42 是什麼"})], "筆記：M42 是恆星形成區"]  # noqa: RUF001
    )
    controller, store = await companion(tmp_path, model, {"claude.ask": claude})
    orchestrator = controller._tool_orchestrator
    assert orchestrator is not None
    owner = SelfActivityOwner(
        SQLiteAgentRunRepository(store), orchestrator, model, allowed=lambda: True
    )
    run_id = await owner.start("M42 是什麼", "想知道", "self_preference")
    assert run_id is not None
    for _ in range(200):
        if not owner.busy:
            break
        await asyncio.sleep(0.01)
    notes = SelfNotes(store, tmp_path / "shared.json")
    [note] = await notes.notes()
    assert note["sources"] == []
    assert note["reported_by_codex"] == [{"url": "https://example.test/m42"}]
    assert await notes.unshared(datetime.now(UTC) + timedelta(minutes=1)) == [run_id]
    text, _ = share_text(note)
    assert "Claude 提供的來源（我沒有直接打開）" in text  # noqa: RUF001
    [activity] = activities_of(await ActivityMonitor(store).snapshot())
    assert activity["tools"][0]["capability"] == "claude.ask"
    assert activity["tools"][0]["target"] == {"task": "M42 是什麼"}


def test_claims_pair_each_linked_line_with_its_first_new_link() -> None:
    from siro.services.agent.self_activity import claims_with_urls

    answer = (
        "**明天台中多雲**，23–29°C。[氣象署](https://www.cwa.gov.tw/a)\n"  # noqa: RUF001
        "沒有連結的句子\n"
        "- 晚上可能下雨 https://news.example.test/b，請帶傘\n"  # noqa: RUF001
        "重複 https://www.cwa.gov.tw/a\n"
    )
    assert claims_with_urls(answer) == [
        ("明天台中多雲，23–29°C。氣象署", "https://www.cwa.gov.tw/a"),  # noqa: RUF001
        ("晚上可能下雨 ，請帶傘", "https://news.example.test/b"),  # noqa: RUF001
    ]


class JudgingModel(ScriptedModel):
    """Scripted rounds for the run; claim checks get a fixed verdict."""

    def __init__(self, rounds: list[object], verdict: str) -> None:
        super().__init__(rounds)  # type: ignore[arg-type]
        self.verdict = verdict
        self.judged: list[str] = []

    async def stream(self, request: Any, cancellation: Any) -> Any:
        if request.prompt.startswith("下面是一個說法"):
            self.judged.append(request.prompt)
            yield ModelChunk("text", self.verdict)
            yield ModelChunk("finished")
            return
        async for chunk in super().stream(request, cancellation):
            yield chunk


async def test_she_opens_claude_links_and_records_what_each_page_says(tmp_path: Path) -> None:
    read: list[object] = []

    async def claude(arguments: dict[str, object], context: ExecutionContext) -> object:
        return {
            "answer": "M42 是恆星形成區 https://example.test/m42\n距離 1344 光年 https://down.test/x",
            "truncated": False,
        }

    async def browse(arguments: dict[str, object], context: ExecutionContext) -> object:
        read.append(arguments["url"])
        if "down.test" in str(arguments["url"]):
            raise ConnectionError("synthetic outage")
        return {"url": arguments["url"], "title": "M42", "text": "獵戶座大星雲是恆星形成區"}

    model = JudgingModel(
        [[ToolCall("c1", "claude.ask", {"task": "M42 是什麼"})], "筆記：M42 是恆星形成區"],  # noqa: RUF001
        "supported",
    )
    controller, store = await companion(
        tmp_path, model, {"claude.ask": claude, "browser.navigate+read": browse}
    )
    orchestrator = controller._tool_orchestrator
    assert orchestrator is not None
    owner = SelfActivityOwner(
        SQLiteAgentRunRepository(store), orchestrator, model, allowed=lambda: True
    )
    assert await owner.start("M42 是什麼") is not None
    for _ in range(300):
        if not owner.busy:
            break
        await asyncio.sleep(0.01)
    [note] = await SelfNotes(store, tmp_path / "shared.json").notes()
    assert read == ["https://example.test/m42", "https://down.test/x"]
    assert note["checks"] == [
        {
            "url": {"url": "https://example.test/m42"},
            "claim": "M42 是恆星形成區",
            "verdict": "supported",
        },
        {
            "url": {"url": "https://down.test/x"},
            "claim": "距離 1344 光年",
            "verdict": "unreachable",
        },
    ]
    # The page she opened herself now counts as read; the unreachable one does not.
    sources = note["sources"]
    assert isinstance(sources, list)
    assert [source["url"] for source in sources] == [{"url": "https://example.test/m42"}]
    assert len(model.judged) == 1
    text, _ = share_text(note)
    assert "M42 是恆星形成區：頁面支持" in text and "距離 1344 光年：打不開" in text  # noqa: RUF001
