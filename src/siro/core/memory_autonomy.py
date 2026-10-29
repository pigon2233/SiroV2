"""Model-nominated memories from a user turn: screened, source-linked, revocable."""

# ruff: noqa: RUF001
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from siro.contracts.events import UserTextEvent
from siro.core.memory import Memory, MemoryService
from siro.core.memory_candidates import _CONTROL, _NONASSERTION, _SENSITIVE, _WITHHELD


@dataclass(frozen=True, slots=True)
class Nomination:
    """D80 D7b: `text` may reword or resolve pronouns; `quote` must be the owner's own
    words in this turn, so the memory still cites a real source."""

    text: str
    quote: str


# (user text) -> statements worth keeping: plain quotes (v1) or reworded with a quote (v2).
Nominator = Callable[[str], Awaitable[Sequence[str | Nomination]]]

MAX_PER_TURN = 3
MAX_CHARS = 200

# D80 D7: credentials are never kept, not even after the owner confirms. Other sensitive
# personal details (address, health, money...) are offered as a keep/discard card instead.
_CREDENTIAL = re.compile(
    r"密碼|口令|金鑰|密鑰|憑證|驗證碼|門禁|信用卡|帳號|賬號|"
    r"(?<![A-Za-z0-9_])(?:password|passwd|secret|token|cookie|authorization|bearer|"
    r"credential|private\s+key|api[ _-]?key)(?![A-Za-z0-9_])|"
    r"\d{7,}|[A-Za-z0-9_+/=-]{32,}|-----BEGIN|(?<![A-Za-z0-9_])(?:sk-|gsk_)",
    re.I,
)


class AutonomousMemory:
    """Writes only low-risk nominations quoted from the owner's own words; the rest is
    returned as `needs_confirmation` for the caller to ask about."""

    def __init__(self, service: MemoryService, nominate: Nominator) -> None:
        self._service = service
        self._nominate = nominate

    async def consider(
        self, identity_id: str, source: UserTextEvent
    ) -> tuple[list[Memory], list[str | Nomination]]:
        if source.source != "siro.presentation" or not source.session_id:
            raise PermissionError("autonomous memory requires the trusted user entry")
        text = source.payload.text.strip()
        if not text or _WITHHELD.search(text):
            return [], []
        saved: list[Memory] = []
        confirm: list[str | Nomination] = []
        for raw in list(await self._nominate(text))[:MAX_PER_TURN]:
            legacy = isinstance(raw, str)
            statement = (raw if isinstance(raw, str) else raw.text).strip()
            quote = (raw if isinstance(raw, str) else raw.quote).strip()
            if not statement or len(statement) > MAX_CHARS or len(quote) < 2:
                continue
            # Grounding: the quoted span must be the owner's actual words in this turn.
            if quote not in text:
                continue
            checked = f"{statement}\n{quote}"
            if _CONTROL.search(checked) or _CREDENTIAL.search(checked):
                continue
            # v1 quotes keep the word filter; v2 relies on the model skipping hypotheticals,
            # measured in docs/verification/MEM-AUTONOMY-D7b.
            if legacy and _NONASSERTION.search(statement):
                continue
            if _SENSITIVE.search(checked):
                confirm.append(statement if legacy else Nomination(statement, quote))
                continue
            saved.append(await self._write(identity_id, source, statement))
        return saved, confirm

    async def keep_confirmed(
        self, identity_id: str, source: UserTextEvent, statement: str, quote: str | None = None
    ) -> Memory:
        """The owner pressed 保留 on a sensitive nomination from this same source turn."""
        grounded = quote if quote is not None else statement
        if source.source != "siro.presentation" or grounded not in source.payload.text:
            raise PermissionError("confirmed memory must quote the owner's own words")
        if _CREDENTIAL.search(f"{statement}\n{grounded}"):
            raise PermissionError("credentials are never kept")
        return await self._write(identity_id, source, statement)

    async def _write(self, identity_id: str, source: UserTextEvent, statement: str) -> Memory:
        memory_id = uuid5(
            NAMESPACE_URL, f"siro:auto-memory:{identity_id}:{source.event_id}:{statement}"
        )
        memory = Memory(memory_id, identity_id, statement, (source.event_id,), source.occurred_at)
        await self._service.remember(memory, source)
        return memory

    async def undo(self, memory_id: UUID) -> bool:
        return await self._service._repository.delete(
            memory_id, reason="owner undid autonomous memory", deleted_at=datetime.now(UTC)
        )


_RULES = (
    "你是 SIRO 的記憶判斷。從使用者這句話挑出值得長期記住的個人事實（偏好、家人寵物、"
    "習慣、重要事件）。每項必須是使用者原話中的連續片段，逐字複製，不可改寫或推測。"
    "閒聊、問句、假設、一次性的事不要選。只輸出 JSON：{\"memories\": [\"片段\", ...]}，"
    "沒有就輸出 {\"memories\": []}。"
)


def memory_nomination_prompt(text: str) -> str:
    return f"{_RULES}\n使用者說：{text}"


# Mem0's extraction step sees recent messages plus the latest exchange (m=10 in the paper).
CONTEXT_MESSAGES = 10
_RULES_V2 = (
    "你是 SIRO 的記憶判斷。根據前後文，從主人「這一句」找出值得長期記住、關於主人本人的事實"
    "（偏好、家人寵物、習慣、計畫、重要事件）。前後文只用來理解代名詞和省略，"
    "不要從前後文另外產生記憶。可以改寫成清楚的一句話，以「主人」開頭，把「牠、他、那個」換成具體對象。"
    "每項都要附 quote：主人這一句裡逐字的連續片段，作為依據。"
    "不要選：閒聊、問句、假設（如果…）、玩笑、轉述別人的話或別人的事、一次性的瑣事、SIRO 說的話。"
    '只輸出 JSON：{"memories": [{"text": "改寫後的事實", "quote": "原話片段"}]}，'
    '沒有就輸出 {"memories": []}。'
)


def contextual_nomination_prompt(text: str, recent: Sequence[tuple[str, str]]) -> str:
    """`recent` is (role, text) oldest first, without the current message."""
    lines = "\n".join(
        f"{'主人' if role == 'user' else 'SIRO'}：{body[:200]}"
        for role, body in list(recent)[-CONTEXT_MESSAGES:]
    )
    return f"{_RULES_V2}\n前後文：\n{lines or '（沒有）'}\n主人這一句：{text}"


def parse_contextual_nominations(raw: str) -> list[Nomination]:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        items = json.loads(raw[start : end + 1]).get("memories", [])
    except (ValueError, AttributeError):
        return []
    if not isinstance(items, list):
        return []
    return [
        Nomination(item["text"], item["quote"])
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and isinstance(item.get("quote"), str)
    ]


def parse_nominations(raw: str) -> list[str]:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        items = json.loads(raw[start : end + 1]).get("memories", [])
    except (ValueError, AttributeError):
        return []
    return [i for i in items if isinstance(i, str)] if isinstance(items, list) else []
