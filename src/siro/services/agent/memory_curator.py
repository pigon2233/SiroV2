# ruff: noqa: RUF001
"""Memory curation: records what the write gate decides and, only in "apply" mode, invalidates
duplicates and superseded memories. Nothing is deleted; every change can be undone."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from siro.core.memory import Memory, MemoryKind, MemoryService
from siro.core.memory_curation import (
    PROMPT_VERSION,
    CurationDecision,
    CurationOp,
    Tier,
    decision_prompt,
    exact_duplicate,
    is_explicit,
    nearest,
    parse_decision,
    plan_apply,
    tier_for,
)

Ask = Callable[[str], Awaitable[str | None]]

MAX_RECORDS = 500
MODES = ("dry-run", "apply")
BUSY_WAIT_SECONDS = 120  # same bound as autonomous memory: never compete with a reply


class MemoryCurationDryRun:
    """Starts in dry-run; the owner switches to apply from the monitor page."""

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
        self._mode_path = log_path.parent / "mode"

    @property
    def mode(self) -> str:
        try:
            value = self._mode_path.read_text(encoding="utf-8").strip()
        except OSError:
            return "dry-run"
        return value if value in MODES else "dry-run"

    async def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError("unknown curation mode")
        self._mode_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._mode_path.write_text, mode, encoding="utf-8")

    async def undo(self, record_id: str) -> int:
        """Reopen every memory a record invalidated."""
        records = await self.records(MAX_RECORDS)
        record = next((r for r in records if r.get("record_id") == record_id), None)
        if record is None or record.get("undone"):
            return 0
        reopened = 0
        applied = record.get("applied")
        for item in applied if isinstance(applied, list) else []:
            memory_id = UUID(str(item["id"]))
            if await self._memory.expire(memory_id, None, reason="owner undid curation"):
                reopened += 1
        line = {"op": "UNDO", "of": record_id, "at": datetime.now(UTC).isoformat()}
        async with self._write:
            await asyncio.to_thread(self._write_line, line)
        return reopened

    async def observe(self, memory: Memory, source: str, *, explicit: bool = False) -> None:
        now = datetime.now(UTC)
        existing = [
            m
            for m in await self._memory.browse(memory.identity_id, limit=1000)
            if m.valid_to is None or m.valid_to > now
        ]
        await self._judge(memory, source, explicit, existing, "live")

    async def backfill(self) -> int:
        """Replay current memories oldest first, each against only the ones before it."""
        if self._lock.locked():
            return 0
        async with self._lock:
            self.backfill_state = "running"
            try:
                now = datetime.now(UTC)
                items = [
                    m
                    for m in await self._memory.browse("siro", limit=1000)
                    if m.valid_to is None or m.valid_to > now
                ]
                items.sort(key=lambda m: m.created_at)
                closed: set[UUID] = set()
                for index, memory in enumerate(items):
                    if memory.memory_id in closed:
                        continue
                    # Only self-research writes SELF memories (services/agent/self_notes.py).
                    source = "siro.self-research" if memory.kind is MemoryKind.SELF else "owner"
                    earlier = [m for m in items[:index] if m.memory_id not in closed]
                    applied = await self._judge(
                        memory, source, is_explicit(memory), earlier, "backfill"
                    )
                    closed.update(applied)
                return len(items)
            finally:
                self.backfill_state = "idle"

    async def _judge(
        self, memory: Memory, source: str, explicit: bool, existing: list[Memory], mode: str
    ) -> list[UUID]:
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
        texts[memory.memory_id] = memory.text
        applied: list[UUID] = []
        if self.mode == "apply":
            for expiry in plan_apply(decision, memory, neighbors, now=datetime.now(UTC)):
                if await self._memory.expire(
                    expiry.memory_id, expiry.valid_to, reason=f"curation: {expiry.reason}"
                ):
                    applied.append(expiry.memory_id)
        async with self._write:
            await asyncio.to_thread(self._append, memory, source, mode, decision, texts, applied)
        return applied

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
        applied: list[UUID],
    ) -> None:
        record = {
            "record_id": str(uuid4()),
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
            "prompt": PROMPT_VERSION if decision.method == "model" else None,
            "applied": [{"id": str(a), "text": texts.get(a, "")[:200]} for a in applied],
        }
        self._write_line(record)

    def _write_line(self, record: Mapping[str, object]) -> None:
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
        undone: set[object] = set()
        for line in self._path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("op") == "UNDO":
                undone.add(row.get("of"))
            else:
                out.append(row)
        for row in out:
            row["undone"] = row.get("record_id") in undone
        return out[-limit:]
