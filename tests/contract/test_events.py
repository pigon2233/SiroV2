from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from siro.contracts.events import (
    EVENT_ADAPTER,
    MAX_EVENT_BYTES,
    TextDeltaEvent,
    ensure_same_session,
    validate_event_json,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "events"


def test_valid_golden_event() -> None:
    event = validate_event_json((FIXTURES / "user_text.valid.json").read_bytes())

    assert event.type == "conversation.user_text.v1"
    assert event.session_id == "session-001"
    assert event.payload.text.startswith("SIRO")


@pytest.mark.parametrize(
    "filename",
    ["user_text.missing_source.json", "user_text.unknown_version.json"],
)
def test_invalid_golden_events(filename: str) -> None:
    with pytest.raises(ValidationError):
        validate_event_json((FIXTURES / filename).read_bytes())


def test_unknown_event_type_is_rejected() -> None:
    raw = (FIXTURES / "user_text.valid.json").read_text(encoding="utf-8")
    raw = raw.replace("conversation.user_text.v1", "conversation.unknown.v1")

    with pytest.raises(ValidationError):
        validate_event_json(raw.encode())


def test_oversize_event_is_rejected_before_parsing() -> None:
    with pytest.raises(ValueError, match="byte limit"):
        validate_event_json(b"{" + b" " * MAX_EVENT_BYTES + b"}")


def test_timezone_is_required() -> None:
    raw = (FIXTURES / "user_text.valid.json").read_text(encoding="utf-8")
    raw = raw.replace("2026-09-23T06:00:00Z", "2026-09-23T06:00:00")

    with pytest.raises(ValidationError, match="timezone"):
        validate_event_json(raw.encode())


def test_cross_session_causation_is_rejected() -> None:
    cause = validate_event_json((FIXTURES / "user_text.valid.json").read_bytes())
    effect = TextDeltaEvent.model_validate(
        {
            "schema_version": 1,
            "event_id": "01900000-0000-7000-8000-000000000002",
            "type": "conversation.text_delta.v1",
            "source": "core",
            "occurred_at": datetime.now(UTC),
            "received_at": datetime.now(UTC),
            "trace_id": "trace-001",
            "causation_id": str(cause.event_id),
            "session_id": "different-session",
            "turn_id": "turn-001",
            "sequence": 2,
            "priority": "interactive",
            "privacy": "local_only",
            "payload": {"generation_id": "generation-1", "index": 0, "text": "hi"},
        }
    )

    with pytest.raises(ValueError, match="same session"):
        ensure_same_session(cause, effect)


def test_event_schema_is_discriminated() -> None:
    schema = EVENT_ADAPTER.json_schema()

    assert schema["discriminator"]["propertyName"] == "type"
    assert "conversation.user_text.v1" in schema["discriminator"]["mapping"]


def test_event_id_is_parsed_as_uuid() -> None:
    event = validate_event_json((FIXTURES / "user_text.valid.json").read_bytes())

    assert isinstance(event.event_id, UUID)
