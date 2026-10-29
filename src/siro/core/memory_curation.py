# ruff: noqa: RUF001
"""Write-time memory curation (Mem0 ADD/UPDATE/DELETE/NOOP) and tier rules. Pure logic.

D80 / CONSOLE-REDESIGN-PLAN §5 D1: a new memory is compared with its nearest existing
memories and the local model picks one operation. Decisions here never write; the caller
decides whether to record (dry-run) or apply them.
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from siro.core.memory import Memory

# Mem0 retrieves the top s=10 similar memories before choosing an operation.
NEIGHBORS = 10
# Untrusted sources (web pages) may be archived but never promoted to the core tier.
UNTRUSTED_SOURCES = frozenset({"siro.self-research"})


class CurationOp(StrEnum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"  # applied as invalidation (valid_to), never a physical delete
    NOOP = "NOOP"
    UNKNOWN = "UNKNOWN"  # model unavailable or unparseable: no guess is made


class Tier(StrEnum):
    CORE = "core"
    ARCHIVE = "archive"


@dataclass(frozen=True, slots=True)
class CurationDecision:
    op: CurationOp
    target_ids: tuple[UUID, ...]
    reason: str
    importance: int | None
    tier: Tier
    method: str  # "exact", "model", "unavailable"


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in folded if ch.isalnum())


def _bigrams(text: str) -> set[str]:
    value = normalize(text)
    return {value[i : i + 2] for i in range(len(value) - 1)} or ({value} if value else set())


def similarity(left: str, right: str) -> float:
    """Character-bigram Jaccard; works for Chinese without a tokenizer or embeddings."""
    a, b = _bigrams(left), _bigrams(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def nearest(candidate: Memory, existing: Sequence[Memory], limit: int = NEIGHBORS) -> list[Memory]:
    others = [m for m in existing if m.memory_id != candidate.memory_id]
    ranked = sorted(others, key=lambda m: similarity(candidate.text, m.text), reverse=True)
    return [m for m in ranked[:limit] if similarity(candidate.text, m.text) > 0]


def tier_for(source: str, *, explicit: bool) -> Tier:
    """Explicit owner requests go straight to core; everything else waits for promotion gates."""
    if explicit and source not in UNTRUSTED_SOURCES:
        return Tier.CORE
    return Tier.ARCHIVE


def exact_duplicate(candidate: Memory, neighbors: Sequence[Memory]) -> Memory | None:
    key = normalize(candidate.text)
    return next((m for m in neighbors if normalize(m.text) == key), None)


PROMPT_VERSION = "v2"

# v2 follows Mem0's update rules (mem0/configs/prompts.py DEFAULT_UPDATE_MEMORY_PROMPT:
# same meaning -> NONE, same subject with more or changed detail -> UPDATE, contradiction ->
# DELETE) with its pizza examples, and the Generative Agents importance anchors (§4.1:
# 1 = brushing teeth / making bed, 10 = a break up / college acceptance). The research-note
# rule comes from the owner: repeated "I looked into X" notes are low-value duplicates.
_DECISION_RULES = (
    "你是 SIRO 的記憶整理。把「新記憶」和「既有記憶」逐筆比較，只選一種操作。\n"
    "先判斷：新記憶和哪一筆既有記憶講的是同一個對象或主題？\n"
    "- NOOP：某筆既有記憶已經表達同樣的意思（換句話說也算），或新記憶沒有保存價值。\n"
    "- UPDATE：和某筆既有記憶是同一對象或主題，但新記憶多了細節或內容有變，應合併成一筆。\n"
    "- DELETE：新記憶和某筆既有記憶互相矛盾，舊的不再成立。\n"
    "- ADD：沒有任何既有記憶講同一對象或主題。只有確定是全新的事才選 ADD。\n"
    "SIRO 自己的研究筆記（「我自己查過…」）只要主題相同或重疊，就選 UPDATE，不要 ADD。\n"
    "例子：既有「喜歡起司披薩」，新「很愛起司披薩」→ NOOP；"
    "既有「喜歡打板球」，新「喜歡和朋友打板球」→ UPDATE；"
    "既有「喜歡起司披薩」，新「不喜歡起司披薩」→ DELETE；"
    "既有「是軟體工程師」，新「名字是小明」→ ADD。\n"
    "importance：1 到 10 的整數，1 是完全瑣碎的日常（刷牙、鋪床），"
    "10 是非常深刻的事（分手、考上大學）。SIRO 自己的研究筆記通常是 1 到 3。\n"
    "UPDATE、DELETE 必須填 target（既有記憶編號）；NOOP 若是因為已有相同記憶，也填 target。"
    "只輸出 JSON："
    '{"op": "ADD|UPDATE|DELETE|NOOP", "target": [編號], '
    '"importance": 整數, "reason": "一句話"}\n'
)


def decision_prompt(candidate: Memory, neighbors: Sequence[Memory]) -> str:
    listed = "\n".join(f"[{index}] {m.text}" for index, m in enumerate(neighbors))
    return f"{_DECISION_RULES}既有記憶：\n{listed or '（沒有）'}\n新記憶：{candidate.text}"


def parse_decision(raw: str | None, neighbors: Sequence[Memory], tier: Tier) -> CurationDecision:
    reason = "模型沒有給出可用的判斷"
    unknown = CurationDecision(CurationOp.UNKNOWN, (), reason, None, tier, "model")
    if not raw:
        return unknown
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return unknown
    try:
        body = json.loads(raw[start : end + 1])
        op = CurationOp(str(body.get("op", "")).upper())
    except (ValueError, AttributeError):
        return unknown
    if op is CurationOp.UNKNOWN:
        return unknown
    raw_targets = body.get("target", [])
    raw_targets = raw_targets if isinstance(raw_targets, list) else [raw_targets]
    targets: list[UUID] = []
    for item in raw_targets:
        if isinstance(item, int) and not isinstance(item, bool) and 0 <= item < len(neighbors):
            targets.append(neighbors[item].memory_id)
    if op in {CurationOp.UPDATE, CurationOp.DELETE} and not targets:
        return unknown  # an edit with no valid target is not applied
    importance = body.get("importance")
    valid = isinstance(importance, int) and not isinstance(importance, bool)
    if not (valid and 1 <= importance <= 10):
        importance = None
    reason = str(body.get("reason", ""))[:200]
    return CurationDecision(op, tuple(dict.fromkeys(targets)), reason, importance, tier, "model")


def is_explicit(memory: Memory) -> bool:
    """Owner "記住…" memories have a deterministic id (MemoryService.ingest_owner_request)."""
    return any(
        memory.memory_id
        == uuid5(NAMESPACE_URL, f"siro:owner-memory:{memory.identity_id}:{source_id}")
        for source_id in memory.source_event_ids
    )


@dataclass(frozen=True, slots=True)
class Expiry:
    memory_id: UUID
    valid_to: datetime
    reason: str


def plan_apply(
    decision: CurationDecision, candidate: Memory, targets: Sequence[Memory], *, now: datetime
) -> list[Expiry]:
    """What applying a decision changes. Explicit owner memories are never touched, and an
    UNKNOWN or ADD decision changes nothing. Invalidation keeps text, sources and revisions."""
    if decision.method not in {"exact", "model"}:
        return []
    if decision.op is CurationOp.NOOP:
        if decision.target_ids and not is_explicit(candidate):
            return [Expiry(candidate.memory_id, now, "duplicate of an existing memory")]
        return []
    if decision.op in {CurationOp.UPDATE, CurationOp.DELETE}:
        reason = (
            "merged into a newer memory" if decision.op is CurationOp.UPDATE else "contradicted"
        )
        return [
            Expiry(target.memory_id, max(candidate.created_at, target.created_at), reason)
            for target in targets
            if target.memory_id in decision.target_ids and not is_explicit(target)
        ]
    return []
