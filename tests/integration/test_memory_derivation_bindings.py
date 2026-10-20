"""MEM-01: synthetic source-to-derived memory invalidation and atomic adoption."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryKind, MemoryService, MemoryStatus
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore, load_migrations
from siro.persistence.state import SQLiteIdentityRepository

NOW = datetime(2026, 10, 20, 4, tzinfo=UTC)


def source(text: str, privacy: Privacy = Privacy.LOCAL_ONLY) -> UserTextEvent:
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="synthetic",
        occurred_at=NOW,
        received_at=NOW,
        trace_id="synthetic",
        session_id="synthetic",
        turn_id=str(uuid4()),
        sequence=1,
        priority=Priority.INTERACTIVE,
        privacy=privacy,
        payload=UserTextPayload(text=text, language="en"),
    )


async def setup(path: Path) -> tuple[SQLiteStore, SQLiteMemoryRepository, MemoryService, Memory]:
    store = SQLiteStore(path)
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="synthetic",
            core_values=("honesty",),
            creator_relationship="synthetic owner",
        ),
        now=NOW,
    )
    repo = SQLiteMemoryRepository(store)
    service = MemoryService(repo)
    event = source("favorite blue")
    parent = Memory(uuid4(), "siro", "favorite blue", (event.event_id,), NOW)
    await service.remember(parent, event)
    return store, repo, service, parent


@pytest.mark.asyncio
async def test_correction_invalidates_existing_legacy_descendants(tmp_path: Path) -> None:
    store, repo, service, parent = await setup(tmp_path / "memory.sqlite")
    event = source("derived blue")
    child = Memory(uuid4(), "siro", "derived blue", (event.event_id,), NOW, kind=MemoryKind.SELF)
    await service.remember(child, event)
    await store.run_transaction(
        lambda c: c.execute(
            "INSERT INTO memory_derivations(parent_memory_id,child_memory_id,revision) "
            "VALUES(?,?,1)",
            (str(parent.memory_id), str(child.memory_id)),
        )
    )
    await service.correct(parent.memory_id, "favorite red", source("favorite red"))
    assert await service.recall("siro", "derived blue") == []
    await repo.rebuild_index()
    assert await service.recall("siro", "derived blue") == []
    assert (await service.revisions(child.memory_id))[-1].status is MemoryStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_stale_adoption_is_atomic_after_correction(tmp_path: Path) -> None:
    store, repo, service, parent = await setup(tmp_path / "stale.sqlite")
    snapshot = await repo.capture_sources(
        "siro",
        "owner",
        (parent.memory_id,),
        now=NOW,
        generator_version="synthetic-v1",
        policy_revision=1,
    )
    child = Memory(
        uuid4(), "siro", "derived blue", parent.source_event_ids, NOW, kind=MemoryKind.SELF
    )
    await service.correct(parent.memory_id, "favorite red", source("favorite red"))
    with pytest.raises(ValueError, match="source"):
        await repo.add_derived(child, snapshot, now=NOW, policy_revision=1)
    count = await store.run_transaction(
        lambda c: c.execute(
            "SELECT count(*) FROM memories WHERE memory_id=?", (str(child.memory_id),)
        ).fetchone()[0]
    )
    assert count == 0


@pytest.mark.asyncio
async def test_three_level_chain_revokes_and_cannot_refill(tmp_path: Path) -> None:
    path = tmp_path / "chain.sqlite"
    _store, repo, service, parent = await setup(path)
    descendants = []
    current = parent
    for index in range(2):
        snapshot = await repo.capture_sources(
            "siro",
            "owner",
            (current.memory_id,),
            now=NOW,
            generator_version="synthetic-v1",
            policy_revision=1,
        )
        current = Memory(
            uuid4(),
            "siro",
            f"derived blue {index}",
            parent.source_event_ids,
            NOW,
            kind=MemoryKind.SELF,
        )
        await repo.add_derived(current, snapshot, now=NOW, policy_revision=1)
        descendants.append(current)
    assert len(await service.recall("siro", "derived blue")) == 2
    assert await repo.revoke_source(parent.source_event_ids[0], reason="synthetic revoke", now=NOW)
    assert not await repo.revoke_source(parent.source_event_ids[0], reason="repeat", now=NOW)
    restarted = SQLiteMemoryRepository(SQLiteStore(path))
    await restarted.rebuild_index()
    assert await restarted.search("siro", "blue") == []
    for child in descendants:
        assert (await restarted.revisions(child.memory_id))[-1].status is MemoryStatus.SUPERSEDED
    with pytest.raises(ValueError, match="source"):
        await restarted.add_derived(
            Memory(uuid4(), "siro", "refill", parent.source_event_ids, NOW),
            snapshot,
            now=NOW,
            policy_revision=1,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["delete", "revoke", "policy", "event_changed"])
async def test_changed_sources_refuse_late_results(tmp_path: Path, mutation: str) -> None:
    import json

    store, repo, service, parent = await setup(tmp_path / "late.sqlite")
    snapshot = await repo.capture_sources(
        "siro", "owner", (parent.memory_id,), now=NOW, generator_version="v1", policy_revision=1
    )
    if mutation == "delete":
        await service.delete(parent.memory_id)
    elif mutation == "revoke":
        await repo.revoke_source(parent.source_event_ids[0], reason="synthetic", now=NOW)
    elif mutation == "event_changed":
        changed = source("synthetic replacement").model_dump(mode="json")
        await store.run_transaction(
            lambda c: c.execute(
                "UPDATE events SET envelope_json=? WHERE event_id=?",
                (json.dumps(changed), str(parent.source_event_ids[0])),
            )
        )
    child = Memory(uuid4(), "siro", "late result", parent.source_event_ids, NOW)
    with pytest.raises(ValueError, match="source"):
        await repo.add_derived(
            child, snapshot, now=NOW, policy_revision=2 if mutation == "policy" else 1
        )
    assert await service.recall("siro", "late result") == []
    count = await store.run_transaction(
        lambda c: c.execute("SELECT count(*) FROM memory_derivation_metadata").fetchone()[0]
    )
    assert count == 0


@pytest.mark.asyncio
async def test_cloud_capture_and_adopt_recheck_source_privacy(tmp_path: Path) -> None:
    import json

    store, repo, service, parent = await setup(tmp_path / "privacy.sqlite")
    with pytest.raises(ValueError, match="source"):
        await repo.capture_sources(
            "siro",
            "owner",
            (parent.memory_id,),
            now=NOW,
            generator_version="v1",
            policy_revision=1,
            route_privacy=Privacy.CLOUD_ALLOWED,
        )
    event = source("synthetic cloud", Privacy.CLOUD_ALLOWED)
    cloud = Memory(uuid4(), "siro", "synthetic cloud", (event.event_id,), NOW)
    await service.remember(cloud, event)
    snapshot = await repo.capture_sources(
        "siro",
        "owner",
        (cloud.memory_id,),
        now=NOW,
        generator_version="v1",
        policy_revision=1,
        route_privacy=Privacy.CLOUD_ALLOWED,
    )
    changed = event.model_dump(mode="json")
    changed["privacy"] = "local_only"
    await store.run_transaction(
        lambda c: c.execute(
            "UPDATE events SET envelope_json=? WHERE event_id=?",
            (json.dumps(changed), str(event.event_id)),
        )
    )
    child = Memory(uuid4(), "siro", "cloud derived", cloud.source_event_ids, NOW)
    with pytest.raises(ValueError, match="source"):
        await repo.add_derived(child, snapshot, now=NOW, policy_revision=1)
    assert (
        await service.recall("siro", "synthetic cloud", route_privacy=Privacy.CLOUD_ALLOWED) == []
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("error", ["person", "identity", "events", "expired", "candidate"])
async def test_invalid_derivations_never_write(tmp_path: Path, error: str) -> None:
    from dataclasses import replace

    store, repo, service, parent = await setup(tmp_path / "invalid.sqlite")
    if error == "candidate":
        await store.run_transaction(lambda c: c.execute("UPDATE memories SET status='candidate'"))
    if error == "expired":
        await store.run_transaction(
            lambda c: c.execute(
                "UPDATE memories SET valid_to=?", ((NOW + timedelta(minutes=1)).isoformat(),)
            )
        )
    snapshot = await repo.capture_sources(
        "siro", "owner", (parent.memory_id,), now=NOW, generator_version="v1", policy_revision=1
    )
    child = Memory(uuid4(), "siro", "invalid derived", parent.source_event_ids, NOW)
    if error == "person":
        child = replace(child, person_id="guest")
    if error == "identity":
        child = replace(child, identity_id="other")
    if error == "events":
        child = replace(child, source_event_ids=(uuid4(),))
    with pytest.raises(ValueError):
        await repo.add_derived(
            child,
            snapshot,
            now=NOW + timedelta(minutes=2) if error == "expired" else NOW,
            policy_revision=1,
        )
    assert await service.recall("siro", "invalid derived") == []


@pytest.mark.asyncio
async def test_candidate_chain_metadata_and_delete_survive_restart(tmp_path: Path) -> None:
    path = tmp_path / "candidate.sqlite"
    store, repo, service, parent = await setup(path)
    snap = await repo.capture_sources(
        "siro",
        "owner",
        (parent.memory_id,),
        now=NOW,
        generator_version="generator-v2",
        policy_revision=3,
    )
    child = Memory(
        uuid4(),
        "siro",
        "candidate blue",
        parent.source_event_ids,
        NOW,
        status=MemoryStatus.CANDIDATE,
    )
    await repo.add_derived(child, snap, now=NOW, policy_revision=3)
    metadata = await store.run_transaction(
        lambda c: tuple(
            c.execute(
                "SELECT generator_version,policy_revision,route_privacy "
                "FROM memory_derivation_metadata"
            ).fetchone()
        )
    )
    assert metadata == ("generator-v2", 3, "local_only")
    assert await service.recall("siro", "candidate blue") == []
    next_snap = await repo.capture_sources(
        "siro",
        "owner",
        (child.memory_id,),
        now=NOW,
        generator_version="summary-v1",
        policy_revision=3,
    )
    summary = Memory(
        uuid4(),
        "siro",
        "candidate summary",
        parent.source_event_ids,
        NOW,
        kind=MemoryKind.SELF,
        status=MemoryStatus.CANDIDATE,
    )
    await repo.add_derived(summary, next_snap, now=NOW, policy_revision=3)
    await service.delete(parent.memory_id)
    restarted = SQLiteMemoryRepository(SQLiteStore(path))
    await restarted.rebuild_index()
    assert (await restarted.revisions(summary.memory_id))[-1].status is MemoryStatus.DELETED


@pytest.mark.asyncio
async def test_write_queue_correction_before_adoption_is_rejected(tmp_path: Path) -> None:
    import asyncio

    store, repo, service, parent = await setup(tmp_path / "race.sqlite")
    snap = await repo.capture_sources(
        "siro", "owner", (parent.memory_id,), now=NOW, generator_version="v1", policy_revision=1
    )
    child = Memory(uuid4(), "siro", "racing blue", parent.source_event_ids, NOW)
    async with store._writer_lock:
        correction = asyncio.create_task(
            service.correct(parent.memory_id, "favorite red", source("red"))
        )
        await asyncio.sleep(0)
        adoption = asyncio.create_task(repo.add_derived(child, snap, now=NOW, policy_revision=1))
        await asyncio.sleep(0)
    await correction
    with pytest.raises(ValueError, match="source"):
        await adoption
    assert await service.recall("siro", "racing blue") == []


@pytest.mark.asyncio
async def test_upgrade_schema15_keeps_existing_memory_and_edge(tmp_path: Path) -> None:
    import sqlite3

    from siro.persistence.sqlite import apply_migrations, load_migrations

    path = tmp_path / "upgrade.sqlite"
    migrations = load_migrations()
    event = source("legacy blue")
    parent_id, child_id = uuid4(), uuid4()
    with sqlite3.connect(path) as connection:
        apply_migrations(connection, migrations[:15])
        connection.execute(
            "INSERT INTO identities(identity_id,core_json,core_version,created_at) "
            "VALUES('siro','{}',1,?)",
            (NOW.isoformat(),),
        )
        connection.execute(
            "INSERT INTO events(event_id,type,envelope_json,received_at,trace_id) "
            "VALUES(?,?,?,?,?)",
            (
                str(event.event_id),
                event.type,
                event.model_dump_json(),
                NOW.isoformat(),
                "synthetic",
            ),
        )
        for memory_id in (parent_id, child_id):
            connection.execute(
                "INSERT INTO memories(memory_id,identity_id,kind,text,status,confidence,"
                "valid_from,revision) VALUES(?,'siro','episodic','legacy blue','committed',1,?,1)",
                (str(memory_id), NOW.isoformat()),
            )
            connection.execute(
                "INSERT INTO memory_sources(memory_id,source_event_id) VALUES(?,?)",
                (str(memory_id), str(event.event_id)),
            )
        connection.execute(
            "INSERT INTO memory_derivations(parent_memory_id,child_memory_id,revision) "
            "VALUES(?,?,1)",
            (str(parent_id), str(child_id)),
        )
        old_checksums = connection.execute(
            "SELECT version,checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
    store = SQLiteStore(path)
    await store.initialize()
    repo = SQLiteMemoryRepository(store)
    assert len(await repo.search("siro", "legacy blue")) == 2
    current = await store.run_transaction(
        lambda c: [
            tuple(row)
            for row in c.execute("SELECT version,checksum FROM schema_migrations ORDER BY version")
        ]
    )
    assert current[: len(old_checksums)] == old_checksums
    assert len(old_checksums) == 15
    assert [version for version, _ in current[len(old_checksums) :]] == [16, 17]
    await repo.correct(parent_id, "legacy red", source("red"), reason="synthetic correction")
    assert await repo.search("siro", "legacy blue") == []


@pytest.mark.asyncio
async def test_revoked_event_cannot_refill_via_original_memory_or_consolidation(
    tmp_path: Path,
) -> None:
    from siro.core.consolidation import ConsolidationCandidate, Consolidator
    from siro.persistence.consolidation import SQLiteConsolidationRepository
    from siro.ports.models import CancellationToken

    store, repo, service, parent = await setup(tmp_path / "refill.sqlite")
    await repo.revoke_source(parent.source_event_ids[0], reason="synthetic", now=NOW)
    event_row = await store.run_transaction(
        lambda c: c.execute(
            "SELECT envelope_json FROM events WHERE event_id=?", (str(parent.source_event_ids[0]),)
        ).fetchone()[0]
    )
    event = UserTextEvent.model_validate_json(event_row)
    with pytest.raises(ValueError, match="source"):
        await service.remember(
            Memory(uuid4(), "siro", "raw refill", parent.source_event_ids, NOW), event
        )
    with pytest.raises(ValueError, match="source"):
        await Consolidator(SQLiteConsolidationRepository(store)).run(
            "refill",
            "siro",
            (
                ConsolidationCandidate(
                    "consolidation refill", MemoryKind.SELF, parent.source_event_ids, 0.8
                ),
            ),
            CancellationToken(),
            now=NOW,
        )
    assert await service.recall("siro", "refill") == []


@pytest.mark.asyncio
async def test_correction_after_adoption_hides_transitive_chain(tmp_path: Path) -> None:
    store, repo, service, root = await setup(tmp_path / "chain-correct.sqlite")
    current = root
    for index in range(2):
        snap = await repo.capture_sources(
            "siro",
            "owner",
            (current.memory_id,),
            now=NOW,
            generator_version="v1",
            policy_revision=1,
        )
        current = Memory(uuid4(), "siro", f"transitive blue {index}", root.source_event_ids, NOW)
        await repo.add_derived(current, snap, now=NOW, policy_revision=1)
    await service.correct(root.memory_id, "favorite red", source("red"))
    restarted = SQLiteMemoryRepository(SQLiteStore(store.path))
    await restarted.rebuild_index()
    assert await restarted.search("siro", "transitive blue") == []
    assert (await restarted.revisions(current.memory_id))[-1].reason == "source corrected"


@pytest.mark.asyncio
async def test_lan_recall_cannot_disclose_local_only_sources(tmp_path: Path) -> None:
    _, _repo, service, parent = await setup(tmp_path / "lan.sqlite")
    assert await service.recall("siro", "favorite blue", route_privacy=Privacy.TRUSTED_LAN) == []
    assert await service.recall("siro", "favorite blue") == [parent]


@pytest.mark.asyncio
async def test_expiring_sources_cannot_be_extended_by_derived_memory(tmp_path: Path) -> None:
    from dataclasses import replace

    store, repo, _service, parent = await setup(tmp_path / "expiry.sqlite")
    expiry = NOW + timedelta(hours=1)
    await store.run_transaction(
        lambda c: c.execute("UPDATE memories SET valid_to=?", (expiry.isoformat(),))
    )
    snap = await repo.capture_sources(
        "siro", "owner", (parent.memory_id,), now=NOW, generator_version="v1", policy_revision=1
    )
    child = Memory(uuid4(), "siro", "temporary blue", parent.source_event_ids, NOW)
    with pytest.raises(ValueError, match="expiry"):
        await repo.add_derived(child, snap, now=NOW, policy_revision=1)
    await repo.add_derived(replace(child, valid_to=expiry), snap, now=NOW, policy_revision=1)
    assert len(await repo.search("siro", "temporary blue", as_of=NOW)) == 1
    assert await repo.search("siro", "temporary blue", as_of=expiry + timedelta(seconds=1)) == []


@pytest.mark.asyncio
async def test_caller_cannot_replace_captured_event_set(tmp_path: Path) -> None:
    from dataclasses import replace

    _, repo, service, parent = await setup(tmp_path / "forged.sqlite")
    other_event = source("unrelated cloud event", Privacy.CLOUD_ALLOWED)
    other = Memory(uuid4(), "siro", "unrelated cloud event", (other_event.event_id,), NOW)
    await service.remember(other, other_event)
    captured = await repo.capture_sources(
        "siro", "owner", (parent.memory_id,), now=NOW, generator_version="v1", policy_revision=1
    )
    forged = replace(
        captured, parents=(replace(captured.parents[0], source_event_ids=other.source_event_ids),)
    )
    child = Memory(uuid4(), "siro", "forged event set", other.source_event_ids, NOW)
    with pytest.raises(ValueError, match="source"):
        await repo.add_derived(child, forged, now=NOW, policy_revision=1)
    assert await service.recall("siro", "forged event set") == []


@pytest.mark.asyncio
async def test_legacy_consolidation_cannot_regenerate_deleted_parent(tmp_path: Path) -> None:
    from siro.core.consolidation import ConsolidationCandidate, Consolidator
    from siro.persistence.consolidation import SQLiteConsolidationRepository
    from siro.ports.models import CancellationToken

    store, _, service, parent = await setup(tmp_path / "deleted-refill.sqlite")
    await service.delete(parent.memory_id)
    with pytest.raises(ValueError, match="source"):
        await Consolidator(SQLiteConsolidationRepository(store)).run(
            "deleted-refill",
            "siro",
            (
                ConsolidationCandidate(
                    "new text from deleted source", MemoryKind.SELF, parent.source_event_ids, 0.8
                ),
            ),
            CancellationToken(),
            now=NOW,
        )
    assert await service.recall("siro", "deleted source") == []


@pytest.mark.asyncio
async def test_current_schema_database_refuses_older_release_without_touching_data(
    tmp_path: Path,
) -> None:
    import hashlib
    import hmac
    import sys

    from siro.core.releases import ReleaseManager, ReleaseManifest

    path = tmp_path / "current-schema.sqlite"
    store, _, _, parent = await setup(path)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "app.txt").write_text("synthetic older release")
    signing_key = b"release-test-key"  # pragma: allowlist secret
    manager = ReleaseManager(
        tmp_path / "release",
        signing_key,
        current_schema=load_migrations()[-1].version,
        database=path,
    )
    artifact = ReleaseManifest(
        version="0.0.1",
        source_sha256=manager._digest_v2(bundle),
        signature="0" * 64,
        min_schema=1,
        max_schema=15,
        signing_format="siro-release-manifest-v2",
    )
    signed = artifact.model_copy(
        update={
            "signature": hmac.new(
                signing_key, artifact.signing_payload(), hashlib.sha256
            ).hexdigest()
        }
    )
    before = path.read_bytes()
    result = manager.stage_and_activate(
        bundle, signed, (sys.executable, "-c", "raise SystemExit(1)")
    )
    assert result.status == "incompatible_schema"
    assert manager.active_version() is None
    assert path.read_bytes() == before
    assert (
        await store.run_transaction(
            lambda c: c.execute(
                "SELECT text FROM memories WHERE memory_id=?", (str(parent.memory_id),)
            ).fetchone()[0]
        )
        == "favorite blue"
    )
