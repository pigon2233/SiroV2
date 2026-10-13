from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from siro.core.procedural import (
    ProceduralCandidate,
    ProceduralCandidateGenerator,
    RejectedTrace,
    SuccessfulTrace,
    TraceStep,
)
from siro.persistence.procedural import SQLiteProceduralCandidateRepository
from siro.persistence.sqlite import SQLiteStore


def trace(
    *, trusted: bool = True, succeeded: bool = True, token: str | None = None
) -> SuccessfulTrace:
    arguments: dict[str, object] = {"room": "entry"}
    if token is not None:
        arguments["api_token"] = token  # pragma: allowlist secret
    return SuccessfulTrace(
        trace_id=uuid4(),
        source_ids=("device:presence-entry",),
        trusted=trusted,
        completed_at=datetime(2026, 9, 26, 12, tzinfo=UTC),
        steps=(
            TraceStep(
                capability="device.light.set",
                arguments=arguments,
                result={"power": True},
                succeeded=succeeded,
            ),
        ),
    )


def test_t30_only_repeated_trusted_successes_become_redacted_candidates() -> None:
    generator = ProceduralCandidateGenerator()
    now = datetime(2026, 9, 26, 13, tzinfo=UTC)
    candidate = generator.generate(
        (trace(token="gsk_test_secret_12345"), trace(token="gsk_other_secret_67890")), now=now
    )  # pragma: allowlist secret
    assert isinstance(candidate, ProceduralCandidate)
    assert candidate.status == "candidate"
    assert candidate.capabilities == ("device.light.set",)
    assert candidate.fixture[0].arguments["api_token"] == "[REDACTED]"
    assert candidate.source_trace_ids

    for traces, reason in (
        ((trace(trusted=False), trace()), "untrusted_trace"),
        ((trace(succeeded=False), trace()), "failed_step"),
        ((trace(),), "insufficient_successes"),
    ):
        rejected = generator.generate(traces, now=now)
        assert isinstance(rejected, RejectedTrace)
        assert rejected.reason == reason


@pytest.mark.asyncio
async def test_t30_candidate_is_durable_review_data_not_an_enabled_skill(tmp_path: Path) -> None:
    generator = ProceduralCandidateGenerator()
    candidate = generator.generate((trace(), trace()), now=datetime(2026, 9, 26, 13, tzinfo=UTC))
    assert isinstance(candidate, ProceduralCandidate)
    store = SQLiteStore(tmp_path / "siro.sqlite3")
    await store.initialize()
    repository = SQLiteProceduralCandidateRepository(store)
    await repository.save(candidate)
    saved = await repository.candidates()
    assert saved == (candidate,)
    assert saved[0].status == "candidate"
    assert not hasattr(repository, "enable")
