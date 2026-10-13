"""Versioned SIRO event contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

MAX_EVENT_BYTES = 64 * 1024


class Priority(StrEnum):
    URGENT = "urgent"
    INTERACTIVE = "interactive"
    BACKGROUND = "background"
    TELEMETRY = "telemetry"


class Privacy(StrEnum):
    LOCAL_ONLY = "local_only"
    TRUSTED_LAN = "trusted_lan"
    CLOUD_ALLOWED = "cloud_allowed"


class StrictModel(BaseModel):
    """Contract base that rejects accidental fields and mutations."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class EventEnvelope(StrictModel):
    """Fields shared by every v1 event."""

    schema_version: Literal[1] = 1
    event_id: UUID
    type: str
    source: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:-]+$")
    subject_id: str | None = Field(default=None, max_length=128)
    occurred_at: datetime
    received_at: datetime
    trace_id: str = Field(min_length=1, max_length=128)
    causation_id: UUID | None = None
    session_id: str | None = Field(default=None, max_length=128)
    turn_id: str | None = Field(default=None, max_length=128)
    sequence: int = Field(ge=0)
    priority: Priority
    ttl_ms: int | None = Field(default=None, gt=0, le=86_400_000)
    privacy: Privacy

    @field_validator("occurred_at", "received_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event timestamps must include a timezone")
        return value


class UserTextPayload(StrictModel):
    text: str = Field(min_length=1, max_length=32_768)
    language: str = Field(min_length=2, max_length=32)


class UserTextEvent(EventEnvelope):
    type: Literal["conversation.user_text.v1"]
    payload: UserTextPayload

    @model_validator(mode="after")
    def require_conversation_scope(self) -> UserTextEvent:
        if self.session_id is None or self.turn_id is None:
            raise ValueError("user text requires session_id and turn_id")
        return self


class TurnStartedPayload(StrictModel):
    generation_id: str = Field(min_length=1, max_length=128)


class TurnStartedEvent(EventEnvelope):
    type: Literal["conversation.turn_started.v1"]
    payload: TurnStartedPayload


class TextDeltaPayload(StrictModel):
    generation_id: str = Field(min_length=1, max_length=128)
    index: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=8192)


class TextDeltaEvent(EventEnvelope):
    type: Literal["conversation.text_delta.v1"]
    payload: TextDeltaPayload


class TurnFinishedPayload(StrictModel):
    generation_id: str = Field(min_length=1, max_length=128)
    reason: Literal["completed", "cancelled", "failed"]


class TurnFinishedEvent(EventEnvelope):
    type: Literal["conversation.turn_finished.v1"]
    payload: TurnFinishedPayload


class CancelRequestedPayload(StrictModel):
    target_turn_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=512)


class CancelRequestedEvent(EventEnvelope):
    type: Literal["conversation.cancel_requested.v1"]
    payload: CancelRequestedPayload


class TurnCancelledPayload(StrictModel):
    target_turn_id: str = Field(min_length=1, max_length=128)
    generation_id: str = Field(min_length=1, max_length=128)


class TurnCancelledEvent(EventEnvelope):
    type: Literal["conversation.turn_cancelled.v1"]
    payload: TurnCancelledPayload


class WorldObservedPayload(StrictModel):
    entity_id: str = Field(min_length=1, max_length=128)
    property: str = Field(min_length=1, max_length=128)
    value: object
    confidence: float = Field(ge=0, le=1)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def require_expiry_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("expires_at must include a timezone")
        return value


class WorldObservedEvent(EventEnvelope):
    type: Literal["world.observed.v1"]
    payload: WorldObservedPayload


class ActionRequestedPayload(StrictModel):
    action_id: UUID
    capability: str = Field(min_length=1, max_length=128)
    arguments: dict[str, object]
    deadline: datetime

    @field_validator("deadline")
    @classmethod
    def require_deadline_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("deadline must include a timezone")
        return value


class ActionRequestedEvent(EventEnvelope):
    type: Literal["action.requested.v1"]
    payload: ActionRequestedPayload


class ActionResultPayload(StrictModel):
    action_id: UUID
    outcome: Literal["confirmed", "mismatch", "denied", "unavailable", "error"]
    goal_id: str | None = Field(default=None, max_length=128)
    importance: float = Field(default=0.5, ge=0, le=1)
    controllability: float = Field(default=0.5, ge=0, le=1)
    expected: object | None = None
    observed: object | None = None


class ActionResultEvent(EventEnvelope):
    type: Literal["action.result.v1"]
    payload: ActionResultPayload


class GoalTransitionPayload(StrictModel):
    goal_id: str = Field(min_length=1, max_length=128)
    previous_state: str = Field(min_length=1, max_length=64)
    state: Literal["completed", "failed", "cancelled"]
    importance: float = Field(default=0.5, ge=0, le=1)


class GoalTransitionEvent(EventEnvelope):
    type: Literal["goal.transition.v1"]
    payload: GoalTransitionPayload


class MemoryCorrectedPayload(StrictModel):
    memory_id: UUID
    revision: int = Field(ge=2)
    reason: str = Field(min_length=1, max_length=512)
    importance: float = Field(default=0.7, ge=0, le=1)


class MemoryCorrectedEvent(EventEnvelope):
    type: Literal["memory.corrected.v1"]
    payload: MemoryCorrectedPayload


class SystemHealthPayload(StrictModel):
    component: str = Field(min_length=1, max_length=128)
    state: Literal["healthy", "degraded", "unavailable"]
    reason: str | None = Field(default=None, max_length=1024)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def require_observed_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class SystemHealthEvent(EventEnvelope):
    type: Literal["system.health.v1"]
    payload: SystemHealthPayload


Event = Annotated[
    UserTextEvent
    | TurnStartedEvent
    | TextDeltaEvent
    | TurnFinishedEvent
    | CancelRequestedEvent
    | TurnCancelledEvent
    | WorldObservedEvent
    | ActionRequestedEvent
    | ActionResultEvent
    | GoalTransitionEvent
    | MemoryCorrectedEvent
    | SystemHealthEvent,
    Field(discriminator="type"),
]

EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)


def validate_event_json(data: bytes) -> Event:
    """Validate a bounded JSON event and return its typed contract."""

    if len(data) > MAX_EVENT_BYTES:
        raise ValueError(f"event exceeds {MAX_EVENT_BYTES} byte limit")
    return EVENT_ADAPTER.validate_json(data)


def ensure_same_session(cause: EventEnvelope, effect: EventEnvelope) -> None:
    """Reject causal links that silently cross conversation sessions."""

    if effect.causation_id != cause.event_id:
        raise ValueError("effect does not reference the supplied cause")
    if cause.session_id != effect.session_id:
        raise ValueError("causal conversation events must remain in the same session")
