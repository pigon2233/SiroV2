from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import (
    Memory,
    MemoryKind,
    MemoryService,
    MemoryStatus,
    SemanticFact,
    WorkingMemory,
)
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.services.presentation.gateway import create_app

pytestmark = pytest.mark.asyncio


def event(text: str, *, session_id: str = "memory-v2") -> UserTextEvent:
    now = datetime.now(UTC)
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="owner",
        occurred_at=now,
        received_at=now,
        trace_id=str(uuid4()),
        session_id=session_id,
        turn_id=str(uuid4()),
        sequence=1,
        priority=Priority.INTERACTIVE,
        privacy=Privacy.LOCAL_ONLY,
        payload=UserTextPayload(text=text, language="en"),
    )


async def service(path: Path) -> tuple[SQLiteStore, SQLiteMemoryRepository, MemoryService]:
    store = SQLiteStore(path)
    await store.initialize()
    identities = SQLiteIdentityRepository(store)
    for identity_id in ("siro", "other"):
        await IdentityService(identities).create(
            identity_id,
            ImmutableCore(
                name=identity_id,
                baseline_identity="test",
                core_values=("honesty",),
                creator_relationship="owner",
            ),
            now=datetime.now(UTC),
        )
    repository = SQLiteMemoryRepository(store)
    return store, repository, MemoryService(repository)


async def remember(
    memory_service: MemoryService,
    text: str,
    *,
    identity_id: str = "siro",
    person_id: str = "owner",
    kind: MemoryKind = MemoryKind.EPISODIC,
    created_at: datetime | None = None,
    valid_to: datetime | None = None,
) -> Memory:
    source = event(text)
    memory = Memory(
        uuid4(),
        identity_id,
        text,
        (source.event_id,),
        created_at or source.occurred_at,
        kind=kind,
        person_id=person_id,
        valid_to=valid_to,
    )
    await memory_service.remember(memory, source)
    return memory


async def test_five_memory_kinds_scope_time_and_kind_filters(tmp_path: Path) -> None:
    _, _, memories = await service(tmp_path / "memory.sqlite3")
    working = WorkingMemory(max_messages=2)
    working.append("session", "user", "working-only-token")
    assert working.recent("session")[0].text == "working-only-token"

    kinds = (
        MemoryKind.EPISODIC,
        MemoryKind.SEMANTIC,
        MemoryKind.PROCEDURAL,
        MemoryKind.SELF,
    )
    for kind in kinds:
        await remember(memories, f"shared-token {kind.value}", kind=kind)
    await remember(memories, "shared-token private-other-person", person_id="guest")
    await remember(memories, "shared-token other identity", identity_id="other")
    expired = datetime.now(UTC) - timedelta(days=2)
    await remember(
        memories,
        "shared-token expired",
        created_at=expired - timedelta(days=1),
        valid_to=expired,
    )

    found = await memories.recall("siro", "shared-token", as_of=datetime.now(UTC), limit=20)
    assert {memory.kind for memory in found} == set(kinds)
    assert all(memory.person_id == "owner" and memory.identity_id == "siro" for memory in found)
    semantic = await memories.recall("siro", "shared-token", kinds=(MemoryKind.SEMANTIC,), limit=20)
    assert [memory.kind for memory in semantic] == [MemoryKind.SEMANTIC]
    by_source = await memories.recall(
        "siro", "shared-token", source_event_id=semantic[0].source_event_ids[0], limit=20
    )
    assert by_source == semantic


async def test_a10_fixed_twenty_case_retrieval(tmp_path: Path) -> None:
    _, _, memories = await service(tmp_path / "memory.sqlite3")
    targets: dict[str, UUID] = {}
    for index in range(20):
        key = f"case-{index:02d} beacon-{index:02d}"
        target = await remember(memories, f"{key} correct-source", kind=MemoryKind.SEMANTIC)
        targets[key] = target.memory_id
        for distractor in range(3):
            await remember(
                memories,
                f"case-{index:02d} unrelated-{distractor} distractor",
                kind=MemoryKind.EPISODIC,
            )

    hits = 0
    for query, expected in targets.items():
        top_five = await memories.recall("siro", query, limit=5)
        hits += expected in {memory.memory_id for memory in top_five}
    assert hits >= 18


async def test_a11_correction_deletion_scope_and_index_rebuild(tmp_path: Path) -> None:
    store, repository, memories = await service(tmp_path / "memory.sqlite3")
    original = await remember(memories, "favorite color is red", kind=MemoryKind.SEMANTIC)
    correction = event("favorite color is blue")
    corrected = await memories.correct(original.memory_id, "favorite color is blue", correction)
    assert corrected.revision == 2
    assert await memories.recall("siro", "favorite color red") == []
    assert [item.memory_id for item in await memories.recall("siro", "favorite color blue")] == [
        original.memory_id
    ]
    versions = await memories.revisions(original.memory_id)
    assert [version.text for version in versions] == [
        "favorite color is red",
        "favorite color is blue",
    ]
    assert set(versions[1].source_event_ids) == {original.source_event_ids[0], correction.event_id}

    summary = await remember(memories, "summary says favorite blue", kind=MemoryKind.SELF)
    await store.run_transaction(
        lambda connection: connection.execute(
            "INSERT INTO memory_derivations(parent_memory_id, child_memory_id, revision) "
            "VALUES (?, ?, 1)",
            (str(original.memory_id), str(summary.memory_id)),
        )
    )
    assert await memories.delete(original.memory_id)
    assert await memories.recall("siro", "favorite color blue") == []
    assert await memories.recall("siro", "summary favorite blue") == []

    await repository.rebuild_index()
    assert await memories.recall("siro", "favorite color blue") == []
    deleted_versions = await memories.revisions(original.memory_id)
    assert deleted_versions[-1].status is MemoryStatus.DELETED

    backup = tmp_path / "memory.backup.sqlite3"
    await store.backup_to(backup)
    await remember(memories, "post-backup transient")
    await store.restore_from(backup)
    restored_repository = SQLiteMemoryRepository(store)
    await restored_repository.rebuild_index()
    restored = MemoryService(restored_repository)
    assert await restored.recall("siro", "favorite color blue") == []
    assert await restored.recall("siro", "post-backup transient") == []

    guest = await remember(restored, "scope-secret", person_id="guest")
    assert await restored.recall("siro", "scope-secret") == []
    assert await restored.recall("siro", "scope-secret", person_id="guest") == [guest]


async def test_authenticated_memory_management_api(tmp_path: Path) -> None:
    _, _, memories = await service(tmp_path / "memory.sqlite3")
    stored = await remember(memories, "api visible memory", kind=MemoryKind.SELF)
    origin = "http://testserver"
    corrections: list[tuple[UserTextEvent, Memory]] = []

    async def record_correction(source: UserTextEvent, memory: Memory) -> None:
        corrections.append((source, memory))

    app = create_app(
        allowed_origins={origin},
        memory_service=memories,
        on_memory_correction=record_correction,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url=origin) as client:
        session = await client.post("/v1/session", headers={"origin": origin})
        assert session.status_code == 200
        headers = {"authorization": f"Bearer {session.json()['token']}"}

        listed = await client.get("/v1/memories", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["items"][0]["memory_id"] == str(stored.memory_id)

        corrected = await client.post(
            f"/v1/memories/{stored.memory_id}/correct",
            headers=headers,
            json={"text": "api corrected memory", "reason": "owner fixed it"},
        )
        assert corrected.status_code == 200
        assert corrected.json()["revision"] == 2
        assert corrections[0][0].type == "conversation.user_text.v1"
        assert corrections[0][1].revision == 2

        revisions = await client.get(f"/v1/memories/{stored.memory_id}/revisions", headers=headers)
        assert [item["text"] for item in revisions.json()["items"]] == [
            "api visible memory",
            "api corrected memory",
        ]

        deleted = await client.delete(f"/v1/memories/{stored.memory_id}", headers=headers)
        assert deleted.status_code == 200
        assert (await client.get("/v1/memories", headers=headers)).json()["items"] == []


async def test_conflicting_semantic_facts_are_retained_with_sources(tmp_path: Path) -> None:
    _, _, memories = await service(tmp_path / "memory.sqlite3")
    for color, verification in (("red", "user_stated"), ("blue", "inferred")):
        source = event(f"favorite color {color}")
        memory = Memory(
            uuid4(),
            "siro",
            f"favorite color is {color}",
            (source.event_id,),
            source.occurred_at,
            kind=MemoryKind.SEMANTIC,
        )
        await memories.remember_fact(
            memory,
            source,
            SemanticFact(memory.memory_id, "owner", "favorite_color", color, verification),
        )

    facts = await memories.conflicting_facts("siro", "owner", "favorite_color")
    assert {(fact.value, fact.verification) for fact in facts} == {
        ("red", "user_stated"),
        ("blue", "inferred"),
    }
    assert len({fact.memory_id for fact in facts}) == 2
