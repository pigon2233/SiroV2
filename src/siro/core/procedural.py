"""Extract review-only procedural-memory candidates from successful trusted traces."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from siro.core.authorization import argument_hash

_SECRET_KEY = re.compile(r"(?:token|secret|password|api[_-]?key|authorization)", re.IGNORECASE)
_SECRET_VALUE = re.compile(r"(?:sk-|gsk_|bearer\s+)[A-Za-z0-9._-]{8,}", re.IGNORECASE)


class TraceStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: str = Field(min_length=1, max_length=128)
    arguments: dict[str, object]
    result: dict[str, object]
    succeeded: bool


class SuccessfulTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: UUID
    source_ids: tuple[str, ...] = Field(min_length=1)
    trusted: bool
    completed_at: datetime
    steps: tuple[TraceStep, ...] = Field(min_length=1, max_length=16)


class ProceduralCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: UUID
    source_trace_ids: tuple[UUID, ...]
    workflow_hash: str
    capabilities: tuple[str, ...]
    fixture: tuple[TraceStep, ...]
    status: str = "candidate"
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RejectedTrace:
    trace_id: UUID
    reason: str


class ProceduralCandidateGenerator:
    """Requires repeated, successful trusted traces and never creates an enabled skill."""

    def generate(
        self, traces: tuple[SuccessfulTrace, ...], *, now: datetime
    ) -> ProceduralCandidate | RejectedTrace:
        if len(traces) < 2:
            return RejectedTrace(
                traces[0].trace_id if traces else uuid4(), "insufficient_successes"
            )
        if any(not trace.trusted for trace in traces):
            return RejectedTrace(traces[0].trace_id, "untrusted_trace")
        if any(not all(step.succeeded for step in trace.steps) for trace in traces):
            return RejectedTrace(traces[0].trace_id, "failed_step")
        signatures = [self._signature(trace) for trace in traces]
        if len(set(signatures)) != 1:
            return RejectedTrace(traces[0].trace_id, "workflow_mismatch")
        redacted = tuple(self._redact_step(step) for step in traces[0].steps)
        if any(
            self._contains_secret(step.arguments) or self._contains_secret(step.result)
            for step in redacted
        ):
            return RejectedTrace(traces[0].trace_id, "secret_in_trace")
        return ProceduralCandidate(
            candidate_id=uuid4(),
            source_trace_ids=tuple(trace.trace_id for trace in traces),
            workflow_hash=argument_hash({"signature": signatures[0]}),
            capabilities=tuple(step.capability for step in redacted),
            fixture=redacted,
            created_at=now,
        )

    @staticmethod
    def _signature(trace: SuccessfulTrace) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return tuple((step.capability, tuple(sorted(step.arguments))) for step in trace.steps)

    def _redact_step(self, step: TraceStep) -> TraceStep:
        return TraceStep(
            capability=step.capability,
            arguments=self._redact_object(step.arguments),
            result=self._redact_object(step.result),
            succeeded=True,
        )

    def _redact_object(self, value: dict[str, object]) -> dict[str, object]:
        redacted: dict[str, object] = {}
        for key, item in value.items():
            if _SECRET_KEY.search(key) or (isinstance(item, str) and _SECRET_VALUE.search(item)):
                redacted[key] = "[REDACTED]"
            elif isinstance(item, dict):
                redacted[key] = self._redact_object({str(k): v for k, v in item.items()})
            else:
                redacted[key] = item
        return redacted

    def _contains_secret(self, value: dict[str, object]) -> bool:
        for key, item in value.items():
            if _SECRET_KEY.search(key) and item != "[REDACTED]":
                return True
            if isinstance(item, str) and _SECRET_VALUE.search(item):
                return True
            if isinstance(item, dict) and self._contains_secret(
                {str(k): v for k, v in item.items()}
            ):
                return True
        return False
