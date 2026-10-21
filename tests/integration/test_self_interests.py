"""CP-P04 stage 2: she picks her own topics from what she already has, and only when away."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_activity_monitor import ScriptedModel, activities_of, companion

from siro.ports.models import ToolCall
from siro.services.activity.monitor import ActivityMonitor
from siro.services.agent.interests import InterestPicker, SelfActivityScheduler, parse_choice
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.agent.self_activity import SelfActivityOwner
from siro.services.tools.execution import ExecutionContext

pytestmark = pytest.mark.asyncio
READ = "browser.navigate+read"


def choice(topic: object, why: str = "上次聊到時沒說清楚", source: str = "conversation") -> str:
    return "好的\n" + json.dumps({"topic": topic, "why": why, "source": source}, ensure_ascii=False)


def test_choice_parsing_rejects_waiting_repeats_and_made_up_sources() -> None:
    picked = parse_choice(choice("獵戶座星雲為什麼是粉紅色"), ())
    assert picked is not None and picked.source == "conversation"
    assert parse_choice(choice(None), ()) is None  # she may choose to wait
    assert parse_choice(choice("獵戶座星雲為什麼是粉紅色"), ("獵戶座星雲為什麼是粉紅色",)) is None
    assert parse_choice(choice("x" * 81), ()) is None
    assert parse_choice(choice("題目", source="owner_said_so"), ()) is None
    assert parse_choice("not json", ()) is None


async def setup(
    tmp_path: Path, picks: list[str], clock: list[datetime]
) -> tuple[SelfActivityScheduler, SelfActivityOwner, ScriptedModel, object, object]:
    async def read(arguments: dict[str, object], context: ExecutionContext) -> object:
        return {"url": arguments["url"], "title": "synthetic"}

    research = ScriptedModel(
        ["筆記：粉紅色來自氫原子發光 [https://example.test/m42]\n待查：為什麼有暗帶"]  # noqa: RUF001
    )
    controller, store = await companion(tmp_path, research, {READ: read})
    await controller.respond("s1", "今晚想看獵戶座")
    orchestrator = controller._tool_orchestrator
    assert orchestrator is not None
    owner = SelfActivityOwner(
        SQLiteAgentRunRepository(store), orchestrator, research, allowed=lambda: True
    )
    picker_model = ScriptedModel(picks)  # type: ignore[arg-type]

    async def preferences() -> tuple[str, ...]:
        return ("探索與理解新事物",)

    picker = InterestPicker(store, picker_model, preferences)
    foreground = [False]
    scheduler = SelfActivityScheduler(
        owner, picker, store, foreground=lambda: foreground[0], clock=lambda: clock[0]
    )
    return scheduler, owner, picker_model, store, foreground


async def settle(owner: SelfActivityOwner) -> None:
    for _ in range(200):
        if not owner.busy:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("self activity did not finish")


async def test_she_waits_while_the_owner_was_just_here_then_picks_with_a_visible_reason(
    tmp_path: Path,
) -> None:
    clock = [datetime.now(UTC)]
    scheduler, owner, picker_model, store, _ = await setup(
        tmp_path, [choice("獵戶座星雲為什麼是粉紅色", "主人今晚想看獵戶座")], clock
    )
    assert await scheduler.tick() is None and picker_model.requests == 0
    clock[0] += timedelta(minutes=11)
    run_id = await scheduler.tick()
    assert run_id is not None
    await settle(owner)
    self_run = next(
        item
        for item in activities_of(await ActivityMonitor(store).snapshot())  # type: ignore[arg-type]
        if item["activity_id"] == run_id
    )
    assert (self_run["origin"], self_run["reason"]) == ("self_interest", "獵戶座星雲為什麼是粉紅色")
    assert self_run["why"] == "主人今晚想看獵戶座"


async def test_cooldown_daily_limit_foreground_and_choosing_to_wait(tmp_path: Path) -> None:
    clock = [datetime.now(UTC) + timedelta(minutes=11)]
    picks = [choice("A 題目"), choice(None), choice("B 題目"), choice("C 題目")]
    scheduler, owner, picker_model, _, foreground = await setup(tmp_path, picks, clock)
    assert await scheduler.tick() is not None
    await settle(owner)
    clock[0] += timedelta(minutes=10)
    assert await scheduler.tick() is None  # cooldown after her own run, even a short one
    assert picker_model.requests == 1
    clock[0] += timedelta(minutes=40)
    foreground[0] = True
    assert await scheduler.tick() is None and picker_model.requests == 1
    foreground[0] = False
    assert await scheduler.tick() is None  # the model chose to wait
    assert picker_model.requests == 2
    await owner.set_paused(True)
    assert await scheduler.tick() is None and picker_model.requests == 2


async def test_open_questions_from_her_notes_become_clues(tmp_path: Path) -> None:
    clock = [datetime.now(UTC) + timedelta(minutes=11)]
    scheduler, owner, _, store, _ = await setup(tmp_path, [choice("M42 的顏色")], clock)
    assert await scheduler.tick() is not None
    await settle(owner)

    async def preferences() -> tuple[str, ...]:
        return ()

    clues = await InterestPicker(store, ScriptedModel(["x"]), preferences).clues(clock[0])  # type: ignore[arg-type]
    assert clues.conversation == ("今晚想看獵戶座",)
    assert clues.open_questions == ("待查：為什麼有暗帶",)  # noqa: RUF001
    assert clues.recent_topics == ("M42 的顏色",)


async def test_notes_list_only_pages_she_read_and_remember_what_was_told(tmp_path: Path) -> None:
    from siro.services.agent.self_notes import SelfNotes, share_text

    clock = [datetime.now(UTC) + timedelta(minutes=11)]
    scheduler, owner, _, store, _ = await setup(tmp_path, [choice("M42 的顏色")], clock)
    research = owner._model
    assert isinstance(research, ScriptedModel)
    research.rounds = [
        [ToolCall("r1", READ, {"url": "https://example.test/m42?utm=SECRET"})],
        "筆記：粉紅色來自氫 [https://made-up.test/]\n待查：為什麼有暗帶",  # noqa: RUF001
    ]
    research.requests = 0
    run_id = await scheduler.tick()
    assert run_id is not None
    await settle(owner)
    path = tmp_path / "shared.json"
    notes = SelfNotes(store, path)  # type: ignore[arg-type]
    [note] = await notes.notes()
    # The made-up link the model wrote is not a source; only the page the journal shows read.
    assert note["sources"] == [
        {"url": {"url": "https://example.test/m42", "redacted": True}, "title": "synthetic"}
    ]
    assert note["open_questions"] == ["待查：為什麼有暗帶"]  # noqa: RUF001
    assert await notes.unshared() == [run_id]
    text, spoken = share_text(note)
    assert "https://example.test/m42" in text and "SECRET" not in text
    assert spoken.startswith("我剛剛查了M42 的顏色")
    notes.mark_shared(run_id)
    assert await SelfNotes(store, path).unshared() == []  # type: ignore[arg-type]
    [activity] = [
        item
        for item in activities_of(await ActivityMonitor(store).snapshot())  # type: ignore[arg-type]
        if item["activity_id"] == run_id
    ]
    assert activity["note"]["sources"] == note["sources"]
