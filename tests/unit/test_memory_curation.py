# ruff: noqa: RUF001
"""D80 P2a: write-gate decisions are validated and the dry run never changes memories."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from siro.core.memory import Memory, MemoryKind
from siro.core.memory_curation import (
    CurationOp,
    Tier,
    exact_duplicate,
    nearest,
    parse_decision,
    similarity,
    tier_for,
)
from siro.services.agent.memory_curator import MemoryCurationDryRun

T0 = datetime(2026, 10, 29, tzinfo=UTC)


def memory(text: str, minutes: int = 0, kind: MemoryKind = MemoryKind.EPISODIC) -> Memory:
    return Memory(uuid4(), "siro", text, (uuid4(),), T0 + timedelta(minutes=minutes), kind=kind)


def test_similarity_ranks_the_same_topic_first() -> None:
    new = memory("我自己查過「環境干擾是多模態代理人的弱點」")
    same = memory("我自己查過「環境干擾在多模態代理人中的類型」")
    other = memory("主人喜歡喝無糖綠茶")
    assert similarity(new.text, same.text) > similarity(new.text, other.text)
    assert nearest(new, [other, same, new])[0] is same


def test_exact_duplicate_ignores_width_case_and_punctuation() -> None:
    old = memory("主人養了一隻貓，叫小黑。")
    assert exact_duplicate(memory("主人養了一隻貓 叫小黑"), [old]) is old


def test_untrusted_research_never_goes_to_core_and_explicit_owner_does() -> None:
    assert tier_for("siro.self-research", explicit=True) is Tier.ARCHIVE
    assert tier_for("siro.presentation", explicit=True) is Tier.CORE
    assert tier_for("siro.presentation", explicit=False) is Tier.ARCHIVE


def test_parse_accepts_valid_update_and_maps_index_to_id() -> None:
    neighbors = [memory("a"), memory("b")]
    decision = parse_decision(
        '說明 {"op": "update", "target": [1], "importance": 7, "reason": "同一件事"}',
        neighbors,
        Tier.ARCHIVE,
    )
    assert decision.op is CurationOp.UPDATE
    assert decision.target_ids == (neighbors[1].memory_id,)
    assert decision.importance == 7


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "not json",
        '{"op": "MERGE"}',
        '{"op": "DELETE", "target": [5]}',  # target outside the neighbor list
        '{"op": "UPDATE", "target": [true]}',
        '{"op": "UPDATE"}',
    ],
)
def test_parse_never_guesses(raw: str | None) -> None:
    decision = parse_decision(raw, [memory("a")], Tier.ARCHIVE)
    assert decision.op is CurationOp.UNKNOWN
    assert decision.target_ids == ()


def test_out_of_range_importance_is_dropped() -> None:
    decision = parse_decision('{"op": "ADD", "importance": 11}', [memory("a")], Tier.ARCHIVE)
    assert decision.op is CurationOp.ADD and decision.importance is None


class FakeMemoryService:
    def __init__(self, items: list[Memory]) -> None:
        self.items = items
        self.writes = 0

    async def browse(self, identity_id: str, *, person_id: str = "owner", limit: int = 100):
        return sorted(self.items, key=lambda m: m.created_at, reverse=True)[:limit]

    async def remember(self, *_args: object) -> None:  # pragma: no cover - must not be called
        self.writes += 1


@pytest.mark.asyncio
async def test_backfill_records_decisions_without_writing(tmp_path: Path) -> None:
    items = [
        memory("我自己查過「環境干擾是多模態代理人的弱點」", 0, MemoryKind.SELF),
        memory("我自己查過「環境干擾是多模態代理人的弱點」", 5, MemoryKind.SELF),
        memory("我自己查過「環境干擾對多模態代理人的影響案例」", 9, MemoryKind.SELF),
    ]
    prompts: list[str] = []

    async def ask(prompt: str) -> str:
        prompts.append(prompt)
        return '{"op": "UPDATE", "target": [0], "importance": 3, "reason": "同主題"}'

    service = FakeMemoryService(items)
    curator = MemoryCurationDryRun(service, ask, tmp_path / "log.jsonl")  # type: ignore[arg-type]
    assert await curator.backfill() == 3
    records = await curator.records()
    assert [r["op"] for r in records] == ["ADD", "NOOP", "UPDATE"]
    assert [r["method"] for r in records] == ["no-neighbors", "exact", "model"]
    assert all(r["tier"] == "archive" for r in records)  # research is untrusted
    assert len(prompts) == 1 and service.writes == 0
    assert len(service.items) == 3


@pytest.mark.asyncio
async def test_model_failure_is_recorded_as_unknown(tmp_path: Path) -> None:
    async def ask(_prompt: str) -> str:
        raise RuntimeError("model down")

    service = FakeMemoryService([memory("主人喜歡綠茶", 0)])
    curator = MemoryCurationDryRun(service, ask, tmp_path / "log.jsonl")  # type: ignore[arg-type]
    await curator.observe(memory("主人很喜歡喝綠茶", 1), "siro.presentation")
    (record,) = await curator.records()
    assert record["op"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_waits_for_foreground_then_gives_up(tmp_path: Path, monkeypatch) -> None:
    import siro.services.agent.memory_curator as module

    monkeypatch.setattr(module, "BUSY_WAIT_SECONDS", 0.02)

    async def ask(_prompt: str) -> str:  # pragma: no cover - must not be called while busy
        raise AssertionError("asked the model during a foreground turn")

    service = FakeMemoryService([memory("主人喜歡綠茶", 0)])
    curator = MemoryCurationDryRun(
        service,  # type: ignore[arg-type]
        ask,
        tmp_path / "log.jsonl",
        busy=lambda: True,
        poll_seconds=0.01,
    )
    await curator.observe(memory("主人很喜歡喝綠茶", 1), "siro.presentation")
    (record,) = await curator.records()
    assert record["op"] == "UNKNOWN" and record["method"] == "unavailable"


@pytest.mark.asyncio
async def test_log_is_bounded(tmp_path: Path, monkeypatch) -> None:
    import siro.services.agent.memory_curator as module

    monkeypatch.setattr(module, "MAX_RECORDS", 3)

    async def ask(_prompt: str) -> str:
        return '{"op": "ADD"}'

    service = FakeMemoryService([])
    curator = MemoryCurationDryRun(service, ask, tmp_path / "log.jsonl")  # type: ignore[arg-type]
    for index in range(5):
        await curator.observe(memory(f"第{index}件事", index), "siro.presentation")
    assert len(await curator.records()) == 3
