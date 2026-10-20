"""Regression probes for source and independent-trace guarantees; synthetic SQLite only."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from siro.core.consolidation import ConsolidationCandidate, Consolidator
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import MemoryKind
from siro.core.procedural import (
    ProceduralCandidate,
    ProceduralCandidateGenerator,
    RejectedTrace,
    SuccessfulTrace,
    TraceStep,
)
from siro.persistence.consolidation import SQLiteConsolidationRepository
from siro.persistence.procedural import SQLiteProceduralCandidateRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.models import CancellationToken

NOW = datetime(2026, 10, 20, tzinfo=UTC)


async def database(path: Path) -> tuple[SQLiteStore, SQLiteConsolidationRepository]:
    store = SQLiteStore(path)
    await store.initialize()
    service = IdentityService(SQLiteIdentityRepository(store))
    for identity in ("siro", "other"):
        await service.create(
            identity,
            ImmutableCore(
                name=identity,
                baseline_identity="synthetic",
                core_values=("honesty",),
                creator_relationship="synthetic owner",
            ),
            now=NOW,
        )
    return store, SQLiteConsolidationRepository(store)


@pytest.mark.asyncio
async def test_t18_run_key_cannot_resume_another_identity(tmp_path: Path) -> None:
    _, repository = await database(tmp_path / "scope.sqlite")
    await repository.start_or_resume("same-run", "siro", NOW)
    with pytest.raises(ValueError, match="identity"):
        await repository.start_or_resume("same-run", "other", NOW)


@pytest.mark.asyncio
async def test_t18_unknown_trait_sources_do_not_change_projection(tmp_path: Path) -> None:
    store, repository = await database(tmp_path / "trait.sqlite")
    with pytest.raises(ValueError, match="source"):
        await repository.apply_trait(
            "siro", "curiosity", 0.01, (uuid4(), uuid4(), uuid4()), now=NOW
        )
    count = await store.run_transaction(
        lambda c: c.execute("SELECT count(*) FROM trait_projections").fetchone()[0]
    )
    assert count == 0


@pytest.mark.asyncio
async def test_t18_unknown_relationship_sources_do_not_create_revision(tmp_path: Path) -> None:
    store, repository = await database(tmp_path / "relationship.sqlite")
    with pytest.raises(ValueError, match="source"):
        await repository.revise_relationship("siro", "owner", {"trust": 0.1}, (uuid4(),))
    count = await store.run_transaction(
        lambda c: c.execute("SELECT count(*) FROM relationships").fetchone()[0]
    )
    assert count == 0


@pytest.mark.asyncio
async def test_t18_duplicate_source_rejected_before_starting_run(tmp_path: Path) -> None:
    store, repository = await database(tmp_path / "duplicate.sqlite")
    source = uuid4()
    with pytest.raises(ValueError, match="source"):
        candidate = ConsolidationCandidate("synthetic", MemoryKind.SELF, (source, source), 0.8)
        await Consolidator(repository).run(
            "duplicate", "siro", (candidate,), CancellationToken(), now=NOW
        )
    count = await store.run_transaction(
        lambda c: c.execute("SELECT count(*) FROM consolidation_runs").fetchone()[0]
    )
    assert count == 0


def trace(*, data: dict[str, object] | None = None) -> SuccessfulTrace:
    return SuccessfulTrace(
        trace_id=uuid4(),
        source_ids=("synthetic:source",),
        trusted=True,
        completed_at=NOW,
        steps=(
            TraceStep(
                capability="filesystem.read",
                arguments=data or {"path": "synthetic"},
                result={"ok": True},
                succeeded=True,
            ),
        ),
    )


def test_t30_same_trace_replayed_is_not_two_successes() -> None:
    item = trace()
    candidate = ProceduralCandidateGenerator().generate((item, item), now=NOW)
    assert isinstance(candidate, RejectedTrace)
    assert candidate.reason == "duplicate_trace"


def test_t30_secrets_in_nested_containers_are_redacted() -> None:
    secret = "SYNTHETIC_PRIVATE_VALUE"  # pragma: allowlist secret
    items = {"headers": [{"api_token": secret}], "rows": ["Bearer synthetic123456"]}
    candidate = ProceduralCandidateGenerator().generate(
        (trace(data=items), trace(data=items)), now=NOW
    )
    assert isinstance(candidate, ProceduralCandidate)
    serialized = candidate.model_dump_json()
    assert secret not in serialized
    assert "synthetic123456" not in serialized
    assert "[REDACTED]" in serialized


def test_t30_candidate_cannot_claim_enabled_status() -> None:
    candidate = ProceduralCandidateGenerator().generate((trace(), trace()), now=NOW)
    assert isinstance(candidate, ProceduralCandidate)
    with pytest.raises(ValidationError):
        ProceduralCandidate.model_validate({**candidate.model_dump(), "status": "enabled"})


@pytest.mark.asyncio
async def test_t30_repeated_workflow_save_is_idempotent(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "procedural.sqlite")
    await store.initialize()
    repository = SQLiteProceduralCandidateRepository(store)
    generator = ProceduralCandidateGenerator()
    traces = (trace(), trace())
    first, second = generator.generate(traces, now=NOW), generator.generate(traces, now=NOW)
    assert isinstance(first, ProceduralCandidate) and isinstance(second, ProceduralCandidate)
    await repository.save(first)
    await repository.save(second)
    assert await repository.candidates() == (first,)


async def recorded_source(store: SQLiteStore) -> UUID:
    from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload

    event = UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="synthetic",
        occurred_at=NOW,
        received_at=NOW,
        trace_id="synthetic",
        session_id="synthetic",
        turn_id="synthetic",
        sequence=1,
        priority=Priority.BACKGROUND,
        privacy=Privacy.LOCAL_ONLY,
        payload=UserTextPayload(text="synthetic statement", language="en"),
    )
    await store.append_event_with_outbox(event, subject="test", payload=b"synthetic")
    return event.event_id


@pytest.mark.asyncio
async def test_t18_commit_checks_run_owner_before_writing(tmp_path: Path) -> None:

    store, repository = await database(tmp_path / "commit-owner.sqlite")
    source = await recorded_source(store)
    run_id, _ = await repository.start_or_resume("owned", "siro", NOW)
    candidate = ConsolidationCandidate("synthetic memory", MemoryKind.SELF, (source,), 0.8)
    with pytest.raises(ValueError, match="identity"):
        await repository.commit_candidate(run_id, "other", candidate, 1, NOW)
    count = await store.run_transaction(
        lambda c: c.execute("SELECT count(*) FROM memories").fetchone()[0]
    )
    assert count == 0


@pytest.mark.asyncio
async def test_t18_same_candidate_deduplicates_within_identity_not_across_it(
    tmp_path: Path,
) -> None:

    store, repository = await database(tmp_path / "scope-dedup.sqlite")
    source = await recorded_source(store)
    candidate = ConsolidationCandidate("same sourced text", MemoryKind.SELF, (source,), 0.8)
    first = await Consolidator(repository).run(
        "siro-run", "siro", (candidate,), CancellationToken(), now=NOW
    )
    second = await Consolidator(repository).run(
        "other-run", "other", (candidate,), CancellationToken(), now=NOW
    )
    assert first.created == second.created == 1
    again = await Consolidator(repository).run(
        "siro-new-run", "siro", (candidate,), CancellationToken(), now=NOW
    )
    assert again.created == 0 and again.duplicates == 1


@pytest.mark.asyncio
async def test_t18_legacy_output_keys_still_deduplicate(tmp_path: Path) -> None:
    store, repository = await database(tmp_path / "legacy-dedup.sqlite")
    source = await recorded_source(store)
    candidate = ConsolidationCandidate("legacy sourced text", MemoryKind.SELF, (source,), 0.8)
    await Consolidator(repository).run("legacy", "siro", (candidate,), CancellationToken(), now=NOW)
    await store.run_transaction(
        lambda c: c.execute("UPDATE consolidation_outputs SET candidate_key = ?", (candidate.key,))
    )
    repeated = await Consolidator(repository).run(
        "legacy-repeat", "siro", (candidate,), CancellationToken(), now=NOW
    )
    assert repeated.created == 0 and repeated.duplicates == 1


@pytest.mark.asyncio
async def test_t18_single_identity_writes_preserve_legacy_key_format(tmp_path: Path) -> None:
    from uuid import NAMESPACE_URL, uuid5

    store, repository = await database(tmp_path / "compatible-key.sqlite")
    source = await recorded_source(store)
    candidate = ConsolidationCandidate("legacy compatible", MemoryKind.SELF, (source,), 0.8)
    await Consolidator(repository).run(
        "compatible", "siro", (candidate,), CancellationToken(), now=NOW
    )
    row = await store.run_transaction(
        lambda c: tuple(
            c.execute("SELECT candidate_key, memory_id FROM consolidation_outputs").fetchone()
        )
    )
    assert row == (candidate.key, str(uuid5(NAMESPACE_URL, f"siro:consolidation:{candidate.key}")))
