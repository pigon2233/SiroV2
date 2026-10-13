"""Outcome reporting boundary shared by action executors."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

ActionOutcome = Literal["confirmed", "mismatch", "denied", "unavailable", "error"]


class ActionOutcomeReporter(Protocol):
    async def report_action(
        self,
        action_id: str,
        outcome: ActionOutcome,
        *,
        occurred_at: datetime,
        importance: float,
        controllability: float,
        expected: object | None = None,
        observed: object | None = None,
    ) -> None: ...
