"""Leased compute jobs that fence late worker results by attempt epoch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class JobAttempt:
    job_id: UUID
    epoch: int
    node_id: str
    expires_at: datetime


class JobLeases:
    def __init__(self, *, max_input_bytes: int = 1_000_000) -> None:
        self._max_input_bytes = max_input_bytes
        self._attempts: dict[UUID, JobAttempt] = {}
        self._completed: set[UUID] = set()
        self._cancelled: set[UUID] = set()

    def submit(
        self, payload: bytes, node_id: str, *, now: datetime, lease_seconds: int = 30
    ) -> JobAttempt:
        if len(payload) > self._max_input_bytes:
            raise ValueError("job input exceeds limit")
        job_id = uuid4()
        attempt = JobAttempt(job_id, 1, node_id, now + timedelta(seconds=lease_seconds))
        self._attempts[job_id] = attempt
        return attempt

    def retry(
        self, job_id: UUID, node_id: str, *, now: datetime, lease_seconds: int = 30
    ) -> JobAttempt:
        previous = self._attempts[job_id]
        if now < previous.expires_at:
            raise ValueError("lease has not expired")
        attempt = JobAttempt(
            job_id, previous.epoch + 1, node_id, now + timedelta(seconds=lease_seconds)
        )
        self._attempts[job_id] = attempt
        return attempt

    def accept_result(self, attempt: JobAttempt, *, now: datetime) -> bool:
        current = self._attempts.get(attempt.job_id)
        if (
            current != attempt
            or now >= attempt.expires_at
            or attempt.job_id in self._completed
            or attempt.job_id in self._cancelled
        ):
            return False
        self._completed.add(attempt.job_id)
        return True

    def cancel(self, job_id: UUID) -> bool:
        if job_id not in self._attempts or job_id in self._completed:
            return False
        self._cancelled.add(job_id)
        return True
