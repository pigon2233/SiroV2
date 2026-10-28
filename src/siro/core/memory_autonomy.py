"""Model-nominated memories from a user turn: screened, source-linked, revocable."""

# ruff: noqa: RUF001
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from siro.contracts.events import UserTextEvent
from siro.core.memory import Memory, MemoryService
from siro.core.memory_candidates import _CONTROL, _NONASSERTION, _SENSITIVE, _WITHHELD

# (user text) -> short third-person-free statements the model judged worth keeping.
Nominator = Callable[[str], Awaitable[list[str]]]

MAX_PER_TURN = 3
MAX_CHARS = 200


class AutonomousMemory:
    """Writes only low-risk nominations quoted from the owner's own words; the rest is
    returned as `needs_confirmation` for the caller to ask about."""

    def __init__(self, service: MemoryService, nominate: Nominator) -> None:
        self._service = service
        self._nominate = nominate

    async def consider(
        self, identity_id: str, source: UserTextEvent
    ) -> tuple[list[Memory], list[str]]:
        if source.source != "siro.presentation" or not source.session_id:
            raise PermissionError("autonomous memory requires the trusted user entry")
        text = source.payload.text.strip()
        if not text or _WITHHELD.search(text):
            return [], []
        saved: list[Memory] = []
        confirm: list[str] = []
        for raw in (await self._nominate(text))[:MAX_PER_TURN]:
            statement = raw.strip()
            if not statement or len(statement) > MAX_CHARS:
                continue
            # Grounding: the nomination must come from the owner's actual words.
            if statement not in text:
                continue
            if _CONTROL.search(statement) or _NONASSERTION.search(statement):
                continue
            if _SENSITIVE.search(statement):
                confirm.append(statement)
                continue
            memory_id = uuid5(
                NAMESPACE_URL, f"siro:auto-memory:{identity_id}:{source.event_id}:{statement}"
            )
            memory = Memory(
                memory_id, identity_id, statement, (source.event_id,), source.occurred_at
            )
            await self._service.remember(memory, source)
            saved.append(memory)
        return saved, confirm

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


def parse_nominations(raw: str) -> list[str]:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        items = json.loads(raw[start : end + 1]).get("memories", [])
    except (ValueError, AttributeError):
        return []
    return [i for i in items if isinstance(i, str)] if isinstance(items, list) else []
