"""Local, review-only drafts from revalidated persisted owner statements; no writer."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from siro.contracts.events import Privacy
from siro.core.memory import MemoryStatus
from siro.core.memory_sources import MemorySourceGate, PreparedSource, SourceReason, SourceScope

GENERATOR_VERSION = "owner-statement-rules-v1"
MAX_SOURCE_CHARS = 2048
DRAFT_TTL = timedelta(hours=24)


class CandidateKind(StrEnum):
    PREFERENCE = "preference"
    EPISODE = "episode"
    TODO = "todo"


# A conservative screening baseline, not a universal secret detector or a write grant.
_WITHHELD = re.compile(
    r"不要.{0,8}(記|存)|別.{0,4}(記|存)|不准.{0,4}(記|存)|不想.{0,4}(記|存)|"
    r"\b(?:do not|don't|never)\s+(?:remember|store|save|record)\b",
    re.I,
)
_EXPLICIT = re.compile(r"記住|幫我記|\bremember\b", re.I)
_SENSITIVE = re.compile(
    r"密碼|口令|金鑰|密鑰|憑證|驗證碼|門禁|身分證|身份證|護照|住址|地址|定位|"
    r"病歷|診斷|醫療|疾病|信用卡|銀行|帳號|賬號|薪資|收入|性向|宗教|政治|"
    r"(?<![A-Za-z0-9_])(?:password|passwd|secret|token|cookie|authorization|bearer|credential|"
    r"private\s+key|api[ _-]?key|medical|diagnosis|address|passport|salary)(?![A-Za-z0-9_])|"
    r"https?://|[\w.+-]+@[\w.-]+|\d{7,}|[A-Za-z0-9_+/=-]{32,}|"
    r"-----BEGIN|(?<![A-Za-z0-9_])(?:sk-|gsk_)",
    re.I,
)
_NONASSERTION = re.compile(
    r"假設|如果|可能|也許|玩笑|範例|例如|文件|引用|聽說|據說|他說|她說|助理|工具結果|"
    r"更正|改為|不再|並非|其實不是|\b(?:if|might|maybe|hypothetical\w*|jok\w*|"
    r"example|quote\w*|said|correction|no longer|instead)\b",
    re.I,
)
_CONTROL = re.compile(
    r"忽略|規則|授權|權限|啟用|自動保存|刪除|執行|你現在|系統指令|"
    r"\b(?:ignor\w*|system|instruction\w*|grant|enable|delete|execute|run\s+command)\b",
    re.I,
)
_MULTI_OR_QUOTED = re.compile(
    r"[\n\r\"'`「」『』“”\u2018\u2019{}<>;,:?]|但是|不過|也喜歡|\b(?:and|but)\b", re.I
)
_UNRESOLVED = re.compile(r"那個|這個|那件|這件|它|\b(?:it|that|this)\b", re.I)
_PATTERNS = (
    (
        CandidateKind.PREFERENCE,
        re.compile(
            r"(?:我(?:一直|平常)?(?:喜歡|不喜歡|偏好|習慣)|"
            r"I\s+(?:usually\s+)?(?:prefer|like|dislike)\s+)(?P<value>.+)",
            re.I,
        ),
    ),
    (
        CandidateKind.EPISODE,
        re.compile(
            r"(?:我確認我們(?:已經|剛剛|已)完成|I\s+confirm\s+we\s+completed\s+)(?P<value>.+)", re.I
        ),
    ),
    (
        CandidateKind.TODO,
        re.compile(r"(?:我(?:需要|打算|要)|I\s+(?:need|plan)\s+to\s+)(?P<value>.+)", re.I),
    ),
)


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    kind: CandidateKind
    text: str = field(repr=False)
    start: int
    end: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.kind, CandidateKind)
            or not isinstance(self.text, str)
            or not 1 <= len(self.text) <= MAX_SOURCE_CHARS
            or type(self.start) is not int
            or type(self.end) is not int
            or not 0 <= self.start < self.end <= MAX_SOURCE_CHARS
            or self.end - self.start != len(self.text)
        ):
            raise ValueError("candidate selection requires a typed, bounded exact span")


def classify_source_text(text: str) -> CandidateSelection | None:
    """Select exact original spans only; no persistence, inference, or identity decisions."""
    if not isinstance(text, str):
        raise TypeError("candidate source must be text")
    if not 1 <= len(text) <= MAX_SOURCE_CHARS:
        return None
    if any(unicodedata.category(char) in {"Cf", "Cc"} for char in text):
        return None
    normalized = unicodedata.normalize("NFKC", text)
    if any(
        pattern.search(normalized)
        for pattern in (
            _WITHHELD,
            _EXPLICIT,
            _SENSITIVE,
            _NONASSERTION,
            _CONTROL,
            _MULTI_OR_QUOTED,
            _UNRESOLVED,
        )
    ):
        return None
    stripped = text.strip()
    sentence = stripped.rstrip("。.!\uff01")
    if not sentence or re.search(r"[。.!\uff01]", sentence):
        return None
    for kind, pattern in _PATTERNS:
        match = pattern.fullmatch(sentence)
        if match and len(match["value"].strip()) >= 2:
            start = len(text) - len(text.lstrip())
            return CandidateSelection(kind, stripped, start, start + len(stripped))
    return None


@dataclass(frozen=True, slots=True)
class CandidateDraft:
    candidate_id: UUID
    selection: CandidateSelection = field(repr=False)
    source: PreparedSource = field(repr=False)
    created_at: datetime
    valid_until: datetime
    generator_version: str = GENERATOR_VERSION
    status: MemoryStatus = field(default=MemoryStatus.CANDIDATE, init=False)
    review_required: Literal[True] = field(default=True, init=False)
    is_owner_fact: Literal[False] = field(default=False, init=False)
    verified_tool_completion: Literal[False] = field(default=False, init=False)
    authorizes_memory_write: Literal[False] = field(default=False, init=False)
    authorizes_execution: Literal[False] = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.candidate_id, UUID)
            or not isinstance(self.selection, CandidateSelection)
            or not isinstance(self.source, PreparedSource)
            or not isinstance(self.generator_version, str)
            or not 1 <= len(self.generator_version) <= 128
            or any(
                not isinstance(value, datetime) or value.utcoffset() is None
                for value in (self.created_at, self.valid_until)
            )
            or self.valid_until <= self.created_at
        ):
            raise ValueError("candidate draft requires typed provenance and aware expiry")

    def metadata(self) -> dict[str, object]:
        return {
            "candidate_id": str(self.candidate_id),
            "kind": self.selection.kind,
            "status": self.status,
            "generator_version": self.generator_version,
            "event_id": str(self.source.source.event_id),
            "source_hash": self.source.source_hash,
            "policy_revision": self.source.policy_revision,
            "policy_hash": self.source.policy_hash,
            "created_at": self.created_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "review_required": True,
            "is_owner_fact": False,
            "verified_tool_completion": False,
            "authorizes_memory_write": False,
            "authorizes_execution": False,
        }


class CandidateReason(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    NOT_SELECTED = "not_selected"
    SOURCE_REJECTED = "source_rejected"
    DRAFT_CHANGED = "draft_changed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    reason: CandidateReason
    draft: CandidateDraft | None = field(default=None, repr=False)
    source_reason: SourceReason | None = None

    def __post_init__(self) -> None:
        if (self.reason is CandidateReason.READY_FOR_REVIEW) != (self.draft is not None):
            raise ValueError("only reviewable decisions may carry private drafts")


def _draft(source: PreparedSource, selection: CandidateSelection) -> CandidateDraft:
    key = f"{source.source.event_id}:{source.source_hash}:{GENERATOR_VERSION}:{selection.kind}"
    until = source.captured_at + DRAFT_TTL
    if source.valid_until is not None:
        until = min(until, source.valid_until)
    return CandidateDraft(uuid5(NAMESPACE_URL, key), selection, source, source.captured_at, until)


class MemoryCandidateGenerator:
    def __init__(self, gate: MemorySourceGate) -> None:
        self._gate = gate

    async def prepare(self, event_id: UUID, scope: SourceScope) -> CandidateDecision:
        checked = await self._gate.prepare(event_id, scope, route_privacy=Privacy.LOCAL_ONLY)
        if checked.snapshot is None:
            return CandidateDecision(CandidateReason.SOURCE_REJECTED, source_reason=checked.reason)
        source = checked.snapshot
        selected = classify_source_text(source.source.payload.text)
        if selected is None:
            return CandidateDecision(CandidateReason.NOT_SELECTED)
        fresh = await self._gate.revalidate(source, route_privacy=Privacy.LOCAL_ONLY)
        if fresh.snapshot is None:
            return CandidateDecision(CandidateReason.SOURCE_REJECTED, source_reason=fresh.reason)
        return CandidateDecision(CandidateReason.READY_FOR_REVIEW, _draft(fresh.snapshot, selected))

    async def revalidate(self, draft: CandidateDraft) -> CandidateDecision:
        if not isinstance(draft, CandidateDraft):
            raise TypeError("candidate review requires typed draft")
        fresh = await self._gate.revalidate(draft.source, route_privacy=Privacy.LOCAL_ONLY)
        if fresh.snapshot is None:
            return CandidateDecision(CandidateReason.SOURCE_REJECTED, source_reason=fresh.reason)
        if fresh.snapshot.captured_at >= draft.valid_until:
            return CandidateDecision(CandidateReason.EXPIRED)
        selection = classify_source_text(draft.source.source.payload.text)
        if selection is None or _draft(draft.source, selection) != draft:
            return CandidateDecision(CandidateReason.DRAFT_CHANGED)
        return CandidateDecision(CandidateReason.READY_FOR_REVIEW, draft)
