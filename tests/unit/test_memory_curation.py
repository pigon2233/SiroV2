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

    async def expire(self, memory_id, valid_to, *, reason: str):  # type: ignore[no-untyped-def]
        self.writes += 1
        for index, item in enumerate(self.items):
            if item.memory_id == memory_id:
                from dataclasses import replace

                self.items[index] = replace(item, valid_to=valid_to)
                return self.items[index]
        return None


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


def explicit(text: str, minutes: int = 0) -> Memory:
    from uuid import NAMESPACE_URL, uuid5

    event = uuid4()
    return Memory(
        uuid5(NAMESPACE_URL, f"siro:owner-memory:siro:{event}"),
        "siro",
        text,
        (event,),
        T0 + timedelta(minutes=minutes),
    )


def test_explicit_owner_memories_are_recognised_and_never_expired() -> None:
    from siro.core.memory_curation import CurationDecision, is_explicit, plan_apply

    owner, auto = explicit("主人喜歡綠茶"), memory("主人喜歡綠茶", 1)
    assert is_explicit(owner) and not is_explicit(auto)
    noop = CurationDecision(CurationOp.NOOP, (auto.memory_id,), "", None, Tier.CORE, "exact")
    assert plan_apply(noop, owner, [auto], now=T0) == []  # the explicit candidate stays
    delete = CurationDecision(
        CurationOp.DELETE, (owner.memory_id,), "", None, Tier.ARCHIVE, "model"
    )
    assert plan_apply(delete, auto, [owner], now=T0) == []  # the explicit target stays


def test_plan_apply_expires_only_cited_non_explicit_memories() -> None:
    from siro.core.memory_curation import CurationDecision, plan_apply

    old, other, new = memory("a", 0), memory("b", 1), memory("c", 5)
    update = CurationDecision(CurationOp.UPDATE, (old.memory_id,), "", None, Tier.ARCHIVE, "model")
    (expiry,) = plan_apply(update, new, [old, other], now=T0)
    assert expiry.memory_id == old.memory_id and expiry.valid_to == new.created_at
    noop = CurationDecision(CurationOp.NOOP, (old.memory_id,), "", None, Tier.ARCHIVE, "model")
    assert [e.memory_id for e in plan_apply(noop, new, [old], now=T0)] == [new.memory_id]
    for op in (CurationOp.ADD, CurationOp.UNKNOWN):
        decision = CurationDecision(op, (old.memory_id,), "", None, Tier.ARCHIVE, "model")
        assert plan_apply(decision, new, [old], now=T0) == []
    unavailable = CurationDecision(
        CurationOp.NOOP, (old.memory_id,), "", None, Tier.ARCHIVE, "unavailable"
    )
    assert plan_apply(unavailable, new, [old], now=T0) == []


@pytest.mark.asyncio
async def test_apply_mode_expires_and_undo_reopens(tmp_path: Path) -> None:
    items = [
        memory("我自己查過「環境干擾」，看過：論文A", 0, MemoryKind.SELF),
        memory("我自己查過「環境干擾」，看過：論文A", 5, MemoryKind.SELF),
    ]
    service = FakeMemoryService(items)

    async def ask(_prompt: str) -> str:  # pragma: no cover - exact duplicates skip the model
        raise AssertionError

    curator = MemoryCurationDryRun(service, ask, tmp_path / "log.jsonl")  # type: ignore[arg-type]
    assert curator.mode == "dry-run"
    await curator.set_mode("apply")
    assert curator.mode == "apply"
    await curator.backfill()
    records = await curator.records()
    assert records[1]["op"] == "NOOP" and records[1]["applied"][0]["id"] == str(items[1].memory_id)
    assert service.items[1].valid_to is not None and service.items[0].valid_to is None
    assert await curator.undo(str(records[1]["record_id"])) == 1
    assert service.items[1].valid_to is None
    assert (await curator.records())[1]["undone"] is True
    assert await curator.undo(str(records[1]["record_id"])) == 0  # undo is not repeated


@pytest.mark.asyncio
async def test_dry_run_never_expires(tmp_path: Path) -> None:
    items = [memory("主人喜歡綠茶", 0), memory("主人喜歡綠茶", 5)]
    service = FakeMemoryService(items)

    async def ask(_prompt: str) -> str:  # pragma: no cover
        raise AssertionError

    curator = MemoryCurationDryRun(service, ask, tmp_path / "log.jsonl")  # type: ignore[arg-type]
    await curator.backfill()
    assert service.writes == 0 and all(m.valid_to is None for m in service.items)
    with pytest.raises(ValueError):
        await curator.set_mode("delete-everything")
