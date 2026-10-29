"""D80 D7 B: reflection needs repeated evidence and stays inferred until it has three sources."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from siro.contracts.events import Priority, UserTextEvent, UserTextPayload
from siro.contracts.events import Privacy as EventPrivacy
from siro.core.consolidation import Consolidator
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import MemoryService
from siro.persistence.consolidation import SQLiteConsolidationRepository
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.services.agent.reflection import Reflection, parse_patterns, reflection_prompt


def owner(text: str, minutes: int, source: str = "siro.presentation") -> UserTextEvent:
    when = datetime.now(UTC) - timedelta(hours=2) + timedelta(minutes=minutes)
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source=source,
        occurred_at=when,
        received_at=when,
        trace_id="r",
        session_id="browser",
        turn_id=f"t{minutes}",
        sequence=minutes,
        priority=Priority.INTERACTIVE,
        privacy=EventPrivacy.LOCAL_ONLY,
        payload=UserTextPayload(text=text, language="zh"),
    )


def test_parser_requires_two_distinct_valid_messages_and_screens_text() -> None:
    raw = json.dumps(
        {
            "patterns": [
                {"text": "主人早上會跑步", "evidence": [0, 2]},
                {"text": "主人喜歡貓", "evidence": [1, 1]},  # one message twice
                {"text": "主人喝咖啡", "evidence": [0, 99]},  # out of range
                {"text": "主人的密碼是 abc", "evidence": [0, 1]},  # credential
                {"text": "主人住院做了診斷", "evidence": [0, 1]},  # sensitive
                {"text": "主人愛看電影", "evidence": [True, 1]},
            ]
        },
        ensure_ascii=False,
    )
    assert [(p.text, p.evidence) for p in parse_patterns(raw, 3)] == [("主人早上會跑步", (0, 2))]
    assert parse_patterns(None, 3) == [] and parse_patterns("nope", 3) == []
    assert "[1] 第二則" in reflection_prompt(["第一則", "第二則"])


@pytest.mark.asyncio
async def test_reflection_keeps_two_source_patterns_as_unrecalled_candidates(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO", baseline_identity="c", core_values=("h",), creator_relationship="owner"
        ),
        now=datetime.now(UTC),
    )
    texts = ["今天早上去跑步了", "午餐吃拉麵", "早上跑完步好舒服", "晚上看電影", "又看了一部電影"]
    texts += ["今天也看電影"] + [f"閒聊第{i}句" for i in range(16)]
    for index, text in enumerate(texts):
        await store.record_event(owner(text, index))
    await store.record_event(owner("工具結果不是主人說的", 99, source="tool.result"))
    prompts: list[str] = []

    async def ask(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps(
            {
                "patterns": [
                    {"text": "主人早上有跑步的習慣", "evidence": [0, 2]},
                    {"text": "主人常在晚上看電影", "evidence": [3, 4, 5]},
                ]
            },
            ensure_ascii=False,
        )

    reflection = Reflection(
        store,
        Consolidator(SQLiteConsolidationRepository(store)),
        ask,
        tmp_path / "reflection.jsonl",
    )
    assert await reflection.due()
    record = await reflection.run()
    assert record["state"] == "done" and record["messages"] == len(texts)
    assert "工具結果" not in prompts[0]
    statuses = {p["text"]: p["status"] for p in record["patterns"]}  # type: ignore[union-attr]
    assert statuses == {"主人早上有跑步的習慣": "candidate", "主人常在晚上看電影": "committed"}
    memory = MemoryService(SQLiteMemoryRepository(store))
    recalled = [m.text for m in await memory.recall("siro", "主人", as_of=datetime.now(UTC))]
    assert "主人常在晚上看電影" in recalled and "主人早上有跑步的習慣" not in recalled

    # Nothing new: the idle loop skips; a forced run is idempotent (no duplicate memories).
    assert not await reflection.due()
    assert (await reflection.run())["state"] == "skipped"
    before = len(await memory.browse("siro"))
    again = await reflection.run(force=True)
    assert again["created"] == 0 and len(await memory.browse("siro")) == before


@pytest.mark.asyncio
async def test_busy_foreground_or_model_failure_writes_nothing(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    for index in range(25):
        await store.record_event(owner(f"訊息{index}", index))

    async def ask(_prompt: str) -> str:
        raise RuntimeError("model down")

    busy = Reflection(
        store,
        Consolidator(SQLiteConsolidationRepository(store)),
        ask,
        tmp_path / "r.jsonl",
        busy=lambda: True,
    )
    assert (await busy.run())["state"] == "skipped"
    failing = Reflection(
        store, Consolidator(SQLiteConsolidationRepository(store)), ask, tmp_path / "r2.jsonl"
    )
    record = await failing.run()
    assert record["state"] == "model_unavailable" and record["created"] == 0
