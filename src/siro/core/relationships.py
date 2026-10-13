"""Provenance-backed, bounded relationship dynamics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


def _unit(value: float) -> float:
    return max(0.0, min(1.0, value))


class RelationshipEvent(StrEnum):
    SUPPORT = "support"
    CONFLICT = "conflict"
    REPAIR = "repair"
    SHARED_SUCCESS = "shared_success"
    BOUNDARY_RESPECTED = "boundary_respected"


@dataclass(frozen=True, slots=True)
class RelationshipState:
    trust: float = 0.50
    familiarity: float = 0.10
    attachment: float = 0.20
    rupture: float = 0.0
    repair_history: int = 0
    revision: int = 0

    def __post_init__(self) -> None:
        if any(
            not 0.0 <= value <= 1.0
            for value in (self.trust, self.familiarity, self.attachment, self.rupture)
        ):
            raise ValueError("relationship dimensions must be within [0, 1]")
        if self.repair_history < 0 or self.revision < 0:
            raise ValueError("relationship counters cannot be negative")

    @property
    def significance(self) -> float:
        return _unit(0.45 * self.attachment + 0.35 * self.familiarity + 0.20 * self.trust)


@dataclass(frozen=True, slots=True)
class RelationshipUpdate:
    state: RelationshipState
    event: RelationshipEvent
    source_id: str
    reason: str


class RelationshipRepository(Protocol):
    async def current(self, identity_id: str, person_id: str) -> RelationshipState: ...

    async def record(
        self, identity_id: str, person_id: str, update: RelationshipUpdate
    ) -> None: ...


class RelationshipSystem:
    """Update relationships slowly; ruptures are faster than repairs."""

    @staticmethod
    def update(
        state: RelationshipState,
        event: RelationshipEvent,
        source_id: str,
        *,
        intensity: float = 1.0,
    ) -> RelationshipUpdate:
        if not source_id:
            raise ValueError("relationship updates require provenance")
        if not 0.0 <= intensity <= 1.0:
            raise ValueError("relationship event intensity must be within [0, 1]")
        trust, familiarity = state.trust, state.familiarity
        attachment, rupture = state.attachment, state.rupture
        repairs = state.repair_history
        reason = event.value
        if event is RelationshipEvent.CONFLICT:
            trust -= 0.12 * intensity
            attachment -= 0.04 * intensity
            rupture += 0.18 * intensity
            reason = "conflict creates a rupture and reduces trust"
        elif event is RelationshipEvent.REPAIR:
            # Repair cannot instantly erase a rupture or restore all trust.
            trust += 0.035 * intensity
            rupture -= min(0.06 * intensity, rupture * 0.40)
            repairs += 1
            reason = "verified repair gradually restores trust"
        elif event is RelationshipEvent.SUPPORT:
            trust += 0.025 * intensity
            attachment += 0.02 * intensity
            familiarity += 0.01 * intensity
            reason = "support gradually strengthens connection"
        elif event is RelationshipEvent.SHARED_SUCCESS:
            trust += 0.02 * intensity
            attachment += 0.015 * intensity
            familiarity += 0.015 * intensity
            reason = "shared success strengthens familiarity"
        else:
            trust += 0.015 * intensity
            rupture -= 0.025 * intensity
            reason = "respecting a boundary supports trust"
        updated = RelationshipState(
            _unit(trust),
            _unit(familiarity),
            _unit(attachment),
            _unit(rupture),
            repairs,
            state.revision + 1,
        )
        return RelationshipUpdate(updated, event, source_id, reason)


def relationship_event_from_text(text: str) -> RelationshipEvent | None:
    """Detect only explicit relational evidence; absence causes no revision."""
    normalized = text.casefold()
    if any(word in normalized for word in ("對不起", "我錯了", "和好", "原諒")):
        return RelationshipEvent.REPAIR
    if any(word in normalized for word in ("討厭你", "騙人", "亂做", "你讓我生氣", "對你生氣")):
        return RelationshipEvent.CONFLICT
    if any(word in normalized for word in ("謝謝你", "支持你", "陪你", "幫你")):
        return RelationshipEvent.SUPPORT
    if any(word in normalized for word in ("一起成功", "我們完成", "做到了")):
        return RelationshipEvent.SHARED_SUCCESS
    return None
