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
from enum import StrEnum
from uuid import UUID

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


def decision_prompt(candidate: Memory, neighbors: Sequence[Memory]) -> str:
    listed = "\n".join(f"[{index}] {m.text}" for index, m in enumerate(neighbors))
    return (
        "你是 SIRO 的記憶整理。比較「新記憶」和「既有記憶」，只選一種操作：\n"
        "ADD＝沒有相同意思的既有記憶；UPDATE＝和某筆既有記憶講同一件事，應合併成一筆；"
        "DELETE＝新記憶推翻了某筆既有記憶（舊的不再成立）；NOOP＝既有記憶已涵蓋，不需要存。\n"
        "UPDATE 和 DELETE 必須填 target（既有記憶編號）。importance 是 1 到 10 的整數，"
        "1 是瑣碎，10 是非常重要。只輸出 JSON："
        '{"op": "ADD|UPDATE|DELETE|NOOP", "target": [編號], '
        '"importance": 整數, "reason": "一句話"}\n'
        f"既有記憶：\n{listed or '（沒有）'}\n新記憶：{candidate.text}"
    )


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
