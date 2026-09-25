"""Stable contracts shared across SIRO processes and languages."""

from siro.contracts.events import Event, validate_event_json

__all__ = ["Event", "validate_event_json"]
