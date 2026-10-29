# ruff: noqa: RUF001
"""Dry-run memory curation: records what the write gate would do, never changes memories."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from siro.core.memory import Memory, MemoryKind, MemoryService
from siro.core.memory_curation import (
    CurationDecision,
    CurationOp,
    Tier,
    decision_prompt,
    exact_duplicate,
    nearest,
    parse_decision,
    tier_for,
)

Ask = Callable[[str], Awaitable[str | None]]

MAX_RECORDS = 500
BUSY_WAIT_SECONDS = 120  # same bound as autonomous memory: never compete with a reply


class MemoryCurationDryRun:
    def __init__(
        self,
        memory: MemoryService,
        ask: Ask,
        log_path: Path,
        *,
        busy: Callable[[], bool] = lambda: False,
        poll_seconds: float = 0.5,
    ) -> None:
        self._memory, self._ask, self._path, self._busy = memory, ask, log_path, busy
        self._poll = poll_seconds
        self._lock = asyncio.Lock()
        self._write = asyncio.Lock()  # one appender at a time (live writes vs backfill)
        self.backfill_state = "idle"

    async def observe(self, memory: Memory, source: str, *, explicit: bool = False) -> None:
        existing = await self._memory.browse(memory.identity_id, limit=1000)
        await self._judge(memory, source, explicit, existing, "live")

    async def backfill(self) -> int:
        """Replay current memories oldest first, each against only the ones before it."""
        if self._lock.locked():
            return 0
        async with self._lock:
            self.backfill_state = "running"
            try:
                items = await self._memory.browse("siro", limit=1000)
                items.sort(key=lambda m: m.created_at)
                for index, memory in enumerate(items):
                    # Only self-research writes SELF memories (services/agent/self_notes.py).
                    source = "siro.self-research" if memory.kind is MemoryKind.SELF else "owner"
                    await self._judge(memory, source, False, items[:index], "backfill")
                return len(items)
            finally:
                self.backfill_state = "idle"

    async def _judge(
        self, memory: Memory, source: str, explicit: bool, existing: list[Memory], mode: str
    ) -> CurationDecision:
        tier = tier_for(source, explicit=explicit)
        neighbors = nearest(memory, existing)
        duplicate = exact_duplicate(memory, neighbors)
        if duplicate is not None:
            decision = CurationDecision(
                CurationOp.NOOP, (duplicate.memory_id,), "和既有記憶完全相同", None, tier, "exact"
            )
        elif not neighbors:
            reason = "沒有相近的既有記憶"
            decision = CurationDecision(CurationOp.ADD, (), reason, None, tier, "no-neighbors")
        else:
            decision = await self._model_decision(memory, neighbors, tier)
        texts = {m.memory_id: m.text for m in neighbors}
        async with self._write:
            await asyncio.to_thread(self._append, memory, source, mode, decision, texts)
        return decision

    async def _model_decision(
        self, memory: Memory, neighbors: list[Memory], tier: Tier
    ) -> CurationDecision:
        waited = 0.0
        while self._busy():
            if waited >= BUSY_WAIT_SECONDS:
                reason = "前景對話一直忙碌，這次沒有判斷"
                return CurationDecision(CurationOp.UNKNOWN, (), reason, None, tier, "unavailable")
            await asyncio.sleep(self._poll)
            waited += self._poll
        try:
            raw = await self._ask(decision_prompt(memory, neighbors))
        except Exception:
            logging.getLogger(__name__).exception("memory curation model call failed")
            raw = None
        return parse_decision(raw, neighbors, tier)

    def _append(
        self,
        memory: Memory,
        source: str,
        mode: str,
        decision: CurationDecision,
        texts: dict[UUID, str],
    ) -> None:
        record = {
            "at": datetime.now(UTC).isoformat(),
            "mode": mode,
            "memory_id": str(memory.memory_id),
            "text": memory.text[:200],
            "source": source,
            "op": decision.op.value,
            "targets": [
                {"id": str(t), "text": texts.get(t, "")[:200]} for t in decision.target_ids
            ],
            "reason": decision.reason,
            "importance": decision.importance,
            "tier": decision.tier.value,
            "method": decision.method,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lines = self._path.read_text(encoding="utf-8").splitlines() if self._path.exists() else []
        lines.append(json.dumps(record, ensure_ascii=False))
        self._path.write_text("\n".join(lines[-MAX_RECORDS:]) + "\n", encoding="utf-8")

    async def records(self, limit: int = 100) -> list[dict[str, object]]:
        return await asyncio.to_thread(self._read, limit)

    def _read(self, limit: int) -> list[dict[str, object]]:
        if not self._path.exists():
            return []
        out: list[dict[str, object]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out
