from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.consolidation import (
    ConsolidationCandidate,
    ConsolidationScheduler,
    Consolidator,
)
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import MemoryKind
from siro.persistence.consolidation import SQLiteConsolidationRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.models import CancellationToken

pytestmark = pytest.mark.asyncio


def source(index: int, when: datetime) -> UserTextEvent:
    from uuid import uuid4

    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="synthetic-30-day",
        occurred_at=when,
        received_at=when,
        trace_id=f"day-{index}",
        session_id="consolidation",
        turn_id=f"turn-{index}",
        sequence=index,
        priority=Priority.BACKGROUND,
        privacy=Privacy.LOCAL_ONLY,
        payload=UserTextPayload(text=f"day {index} observation", language="en"),
    )


class CancelAfterFirst:
    def __init__(
        self, repository: SQLiteConsolidationRepository, cancellation: CancellationToken
    ) -> None:
        self.repository = repository
        self.cancellation = cancellation
        self.commits = 0

    async def start_or_resume(self, *args: object, **kwargs: object) -> tuple[str, int]:
        return await self.repository.start_or_resume(*args, **kwargs)  # type: ignore[arg-type]

    async def commit_candidate(self, *args: object, **kwargs: object) -> bool:
        result = await self.repository.commit_candidate(*args, **kwargs)  # type: ignore[arg-type]
        self.commits += 1
        if self.commits == 1:
            self.cancellation.cancel()
        return result

    async def finish_run(self, *args: object, **kwargs: object) -> None:
        await self.repository.finish_run(*args, **kwargs)  # type: ignore[arg-type]


async def setup(
    path: Path,
) -> tuple[SQLiteStore, SQLiteConsolidationRepository, tuple[UserTextEvent, ...]]:
    store = SQLiteStore(path)
    await store.initialize()
    identities = SQLiteIdentityRepository(store)
    await IdentityService(identities).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="immutable",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        now=datetime.now(UTC),
    )
    start = datetime.now(UTC) - timedelta(days=30)
    events = tuple(source(index, start + timedelta(days=index)) for index in range(30))
    for item in events:
        await store.append_event_with_outbox(item, subject="test", payload=b"source")
    return store, SQLiteConsolidationRepository(store), events


async def test_a12_cancel_resume_is_idempotent_and_preserves_identity(tmp_path: Path) -> None:
    store, repository, events = await setup(tmp_path / "siro.sqlite3")
    candidates = tuple(
        ConsolidationCandidate(
            f"week {index} reflection",
            MemoryKind.SELF,
            tuple(item.event_id for item in events[index * 3 : index * 3 + 3]),
            0.8,
        )
        for index in range(5)
    )
    token = CancellationToken()
    interrupted = await Consolidator(CancelAfterFirst(repository, token)).run(
        "month-1", "siro", candidates, token, now=datetime.now(UTC)
    )
    assert interrupted.state == "cancelled"
    assert interrupted.checkpoint == 1

    resumed = await Consolidator(repository).run(
        "month-1", "siro", candidates, CancellationToken(), now=datetime.now(UTC)
    )
    assert resumed.state == "completed"
    assert resumed.checkpoint == 5
    repeated = await Consolidator(repository).run(
        "month-1", "siro", candidates, CancellationToken(), now=datetime.now(UTC)
    )
    assert repeated.created == 0

    counts = await store.run_transaction(
        lambda connection: (
            int(connection.execute("SELECT count(*) FROM consolidation_outputs").fetchone()[0]),
            int(connection.execute("SELECT count(*) FROM memories").fetchone()[0]),
        )
    )
    assert counts == (5, 5)
    identity = await SQLiteIdentityRepository(store).get("siro")
    assert identity is not None and identity.core.baseline_identity == "immutable"


async def test_inference_trait_and_relationship_guards(tmp_path: Path) -> None:
    store, repository, events = await setup(tmp_path / "siro.sqlite3")
    weak = ConsolidationCandidate(
        "possible preference", MemoryKind.SEMANTIC, (events[0].event_id,), 0.4, inferred=True
    )
    await Consolidator(repository).run(
        "weak", "siro", (weak,), CancellationToken(), now=datetime.now(UTC)
    )
    status = await store.run_transaction(
        lambda connection: str(connection.execute("SELECT status FROM memories").fetchone()[0])
    )
    assert status == "candidate"

    with pytest.raises(ValueError, match="three independent"):
        await repository.apply_trait(
            "siro", "openness", 0.5, (events[0].event_id,), now=datetime.now(UTC)
        )
    sources = tuple(item.event_id for item in events[:3])
    values = [
        await repository.apply_trait("siro", "openness", 0.5, sources, now=datetime.now(UTC))
        for _ in range(6)
    ]
    assert values[0] == pytest.approx(0.01)
    assert values[-1] == pytest.approx(0.05)

    first = await repository.revise_relationship(
        "siro", "owner", {"trust": 0.6}, (events[0].event_id,)
    )
    second = await repository.revise_relationship(
        "siro", "owner", {"trust": 0.7}, (events[1].event_id,)
    )
    assert (first, second) == (1, 2)


async def test_scheduler_requires_idle_resources_and_cleans_up(tmp_path: Path) -> None:
    _, repository, events = await setup(tmp_path / "siro.sqlite3")
    candidate = ConsolidationCandidate(
        "scheduled reflection",
        MemoryKind.SELF,
        tuple(item.event_id for item in events[:3]),
        0.9,
    )
    scheduler = ConsolidationScheduler(Consolidator(repository))
    now = datetime.now(UTC)

    assert not await scheduler.schedule(
        "scheduled", "siro", (candidate,), now=now, idle=False, resources_available=True
    )
    assert not await scheduler.schedule(
        "scheduled", "siro", (candidate,), now=now, idle=True, resources_available=False
    )
    assert await scheduler.schedule(
        "scheduled", "siro", (candidate,), now=now, idle=True, resources_available=True
    )
    assert not await scheduler.schedule(
        "scheduled", "siro", (candidate,), now=now, idle=True, resources_available=True
    )
    result = await scheduler.wait("scheduled")
    assert result is not None and result.state == "completed"
    assert not scheduler.active("scheduled")
    await scheduler.close()


async def test_a12_real_process_crash_resumes_from_committed_checkpoint(tmp_path: Path) -> None:
    database = tmp_path / "crash.sqlite3"
    store, repository, events = await setup(database)
    source_ids = tuple(item.event_id for item in events[:3])
    helper = Path(__file__).parents[1] / "helpers" / "consolidation_crash.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        helper,
        database,
        json.dumps([str(value) for value in source_ids]),
    )
    assert await process.wait() == 91

    candidate = ConsolidationCandidate("crash candidate", MemoryKind.SELF, source_ids, 0.8)
    result = await Consolidator(repository).run(
        "real-crash", "siro", (candidate,), CancellationToken(), now=datetime.now(UTC)
    )
    assert result.state == "completed"
    assert result.checkpoint == 1
    counts = await store.run_transaction(
        lambda connection: (
            int(connection.execute("SELECT count(*) FROM consolidation_outputs").fetchone()[0]),
            int(connection.execute("SELECT count(*) FROM memories").fetchone()[0]),
        )
    )
    assert counts == (1, 1)
