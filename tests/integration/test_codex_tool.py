"""Codex as a read-only tool: only the task goes out, and its answer is labelled as Codex's."""

from __future__ import annotations

import asyncio
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
from siro.services.tools.codex import CodexUnavailable, ask_codex
from siro.services.tools.execution import ExecutionContext

pytestmark = pytest.mark.asyncio


async def test_codex_runs_read_only_with_only_the_task(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_OPENAI_API_KEY", "not-for-codex")  # pragma: allowlist secret
    seen: dict[str, object] = {}

    async def run(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        seen.update(argv=argv, **options)
        answer = Path(argv[argv.index("-o") + 1])
        answer.write_text("明天晚上台中多雲，23 度 https://www.cwa.gov.tw/x\n", encoding="utf-8")  # noqa: RUF001
        return {"returncode": 0}

    result = await ask_codex(
        {"task": "查明天晚上台中的天氣"}, binary=Path("/opt/codex"), model="gpt-6-luna", run=run
    )
    assert result == {
        "answer": "明天晚上台中多雲，23 度 https://www.cwa.gov.tw/x",  # noqa: RUF001
        "truncated": False,
        "model": "gpt-6-luna",
    }
    argv = seen["argv"]
    assert isinstance(argv, tuple)
    assert argv[:3] == ("/opt/codex", "--search", "exec")
    assert argv[argv.index("--sandbox") + 1] == "read-only" and "--ephemeral" in argv
    assert argv[-1].endswith("查明天晚上台中的天氣")
    environment = seen["environment"]
    assert isinstance(environment, dict) and "SIRO_OPENAI_API_KEY" not in environment


async def test_codex_without_an_answer_fails_honestly() -> None:
    async def run(argv: tuple[str, ...], **options: object) -> dict[str, object]:
        return {"returncode": 0}  # e.g. not logged in: exits but writes no answer

    with pytest.raises(CodexUnavailable):
        await ask_codex({"task": "查天氣"}, binary=Path("/opt/codex"), run=run)
    with pytest.raises(ValueError):
        await ask_codex({"task": "x"}, binary=Path("/opt/codex"), run=run)


def test_monitor_shows_the_task_and_says_codex_network_is_unseen() -> None:
    described = describe_tool("codex.ask", {"task": "查天氣"}, {"answer": "多雲"})
    assert described == {
        "target": {"task": "查天氣"},
        "network": {
            "coverage": "unobserved",
            "requests": [],
            "gaps": ["external_agent_network_not_monitored"],
        },
    }


async def test_her_note_lists_codex_links_apart_from_pages_she_read(tmp_path: Path) -> None:
    async def codex(arguments: dict[str, object], context: ExecutionContext) -> object:
        return {"answer": "M42 是恆星形成區 https://example.test/m42。", "truncated": False}

    model = ScriptedModel(
        [[ToolCall("c1", "codex.ask", {"task": "M42 是什麼"})], "筆記：M42 是恆星形成區"]  # noqa: RUF001
    )
    controller, store = await companion(tmp_path, model, {"codex.ask": codex})
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
    assert "Codex 提供的來源（我沒有直接打開）" in text  # noqa: RUF001
    [activity] = activities_of(await ActivityMonitor(store).snapshot())
    assert activity["tools"][0]["capability"] == "codex.ask"
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

    async def stream(self, request: Any, cancellation: Any) -> Any:  # type: ignore[override]
        if request.prompt.startswith("下面是一個說法"):
            self.judged.append(request.prompt)
            yield ModelChunk("text", self.verdict)
            yield ModelChunk("finished")
            return
        async for chunk in super().stream(request, cancellation):
            yield chunk


async def test_she_opens_codex_links_and_records_what_each_page_says(tmp_path: Path) -> None:
    read: list[object] = []

    async def codex(arguments: dict[str, object], context: ExecutionContext) -> object:
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
        [[ToolCall("c1", "codex.ask", {"task": "M42 是什麼"})], "筆記：M42 是恆星形成區"],  # noqa: RUF001
        "supported",
    )
    controller, store = await companion(
        tmp_path, model, {"codex.ask": codex, "browser.navigate+read": browse}
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
    assert [source["url"] for source in note["sources"]] == [{"url": "https://example.test/m42"}]
    assert len(model.judged) == 1
    text, _ = share_text(note)
    assert "M42 是恆星形成區：頁面支持" in text and "距離 1344 光年：打不開" in text  # noqa: RUF001
