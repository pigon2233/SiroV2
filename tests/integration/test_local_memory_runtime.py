from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from siro import cli
from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.companion import CompanionCore
from siro.core.conversation import ConversationEngine, TurnState
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory
from siro.persistence.conversation import SQLiteConversationRepository
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore, apply_migrations, load_migrations
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.embeddings import RetrievalUnavailable
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest
from siro.services.agent.local_memory import LocalMemoryProfile, build_local_memory

TEXT = "The synthetic charger is in drawer seven."


class Capture:
    name = "synthetic-capture"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        yield ModelChunk("text", "synthetic reply")
        yield ModelChunk("finished")


def profile(mode: str = "relevance") -> LocalMemoryProfile:
    values: dict[str, Any] = {
        "mode": mode,
        "embedding_model": "synthetic-embedding",
        "embedding_digest": "a" * 64,
        "dimensions": 32,
    }
    if mode == "relevance":
        values.update(relevance_model="synthetic-judge", relevance_digest="b" * 64)
    return LocalMemoryProfile.model_validate(values)


async def seed(path: Path) -> tuple[SQLiteStore, Memory]:
    store = SQLiteStore(path)
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="synthetic",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        now=datetime.now(UTC),
    )
    now = datetime.now(UTC)
    event = UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="synthetic",
        occurred_at=now,
        received_at=now,
        trace_id="synthetic",
        session_id="source",
        turn_id="source",
        sequence=1,
        priority=Priority.INTERACTIVE,
        privacy=Privacy.LOCAL_ONLY,
        payload=UserTextPayload(text=TEXT, language="en"),
    )
    memory = Memory(uuid4(), "siro", TEXT, (event.event_id,), now)
    await SQLiteMemoryRepository(store).add(memory, event)
    return store, memory


def transport(seen: list[str], *, fail: bool = False) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if fail:
            return httpx.Response(500, text="PRIVATE provider failure")
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "synthetic-embedding", "digest": "a" * 64},
                        {"name": "synthetic-judge", "digest": "b" * 64},
                    ]
                },
            )
        body = json.loads(request.content)
        if request.url.path == "/api/embed":
            return httpx.Response(
                200,
                json={
                    "model": "synthetic-embedding",
                    "embeddings": [[1.0] + [0.0] * 31 for _ in body["input"]],
                },
            )
        assert request.url.path == "/api/chat"
        data = json.loads(body["messages"][1]["content"])
        assert data["memories"][0]["source_event_types"] == ["conversation.user_text.v1"]
        return httpx.Response(
            200,
            json={
                "model": "synthetic-judge",
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 100,
                "eval_count": 20,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {"decisions": {"0": {"match": True, "quote": data["memories"][0]["text"]}}}
                    ),
                },
            },
        )

    return httpx.MockTransport(handle)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["hybrid", "relevance"])
async def test_opt_in_composition_reaches_real_core_and_source_mutation(
    tmp_path: Path,
    mode: str,
) -> None:
    store, memory = await seed(tmp_path / "siro.db")
    seen: list[str] = []
    service = build_local_memory(store, profile(mode), transport=transport(seen))
    model = Capture()
    core = CompanionCore(
        SQLiteIdentityRepository(store),
        service,
        ConversationEngine(model, SQLiteConversationRepository(store)),
        memory_context_bytes=8192,
    )
    assert (
        await core.respond("query", "siro", "Where is the power adapter?")
    ).state is TurnState.COMPLETED
    assert TEXT in model.requests[0].prompt
    assert "/api/embed" in seen
    assert ("/api/chat" in seen) is (mode == "relevance")
    updated_text = "The synthetic charger is now in drawer nine."
    now = datetime.now(UTC)
    correction = UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="synthetic",
        occurred_at=now,
        received_at=now,
        trace_id="correction",
        session_id="source",
        turn_id="correction",
        sequence=2,
        priority=Priority.INTERACTIVE,
        privacy=Privacy.LOCAL_ONLY,
        payload=UserTextPayload(text=updated_text, language="en"),
    )
    assert await service.correct(memory.memory_id, updated_text, correction) is not None
    updated = await service.recall_context("siro", "Where is the power adapter?")
    assert len(updated) == 1 and updated[0].text == updated_text and updated[0].revision == 2
    await service.delete(memory.memory_id)
    restarted = build_local_memory(
        SQLiteStore(tmp_path / "siro.db"), profile(mode), transport=transport(seen)
    )
    before = len(seen)
    assert await restarted.recall_context("siro", "Where is the power adapter?") == []
    assert len(seen) == before


@pytest.mark.asyncio
async def test_no_profile_never_calls_models_and_preserves_lexical_recall(tmp_path: Path) -> None:
    store, memory = await seed(tmp_path / "siro.db")

    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("default path must not call a model")

    service = build_local_memory(store, transport=httpx.MockTransport(forbidden))
    assert memory in await service.recall_context("siro", "synthetic charger")


@pytest.mark.asyncio
async def test_retrieval_failure_does_not_fallback_or_dispatch_answer(tmp_path: Path) -> None:
    store, _ = await seed(tmp_path / "siro.db")
    model = Capture()
    core = CompanionCore(
        SQLiteIdentityRepository(store),
        build_local_memory(store, profile(), transport=transport([], fail=True)),
        ConversationEngine(model, SQLiteConversationRepository(store)),
    )
    with pytest.raises(RetrievalUnavailable):
        await core.respond("query", "siro", "charger")
    assert model.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [15, 16, 17])
async def test_existing_schema_upgrade_and_reopen_preserves_old_checksums(
    tmp_path: Path,
    version: int,
) -> None:
    path = tmp_path / "siro.db"
    with sqlite3.connect(path) as c:
        apply_migrations(c, load_migrations()[:version])
        before = c.execute("SELECT * FROM schema_migrations ORDER BY version").fetchall()
    await SQLiteStore(path).initialize()
    await SQLiteStore(path).initialize()
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 18
        assert (
            c.execute(
                "SELECT * FROM schema_migrations WHERE version<=? ORDER BY version", (version,)
            ).fetchall()
            == before
        )


@pytest.mark.asyncio
async def test_cli_invalid_profile_does_not_create_database(tmp_path: Path, capsys: Any) -> None:
    config = tmp_path / "profile.json"
    config.write_text('{"PRIVATE":"PRIVATE"}', encoding="utf-8")
    args = cli.build_parser().parse_args(
        [
            "demo",
            "--data",
            str(tmp_path / "data"),
            "--once",
            "synthetic",
            "--memory-profile",
            str(config),
        ]
    )
    assert await cli._run_demo(args) == 2
    assert not (tmp_path / "data" / "siro.db").exists()
    assert "PRIVATE" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_cli_opt_in_success_failure_and_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    import siro.services.agent.local_memory as composition

    await seed(tmp_path / "siro.db")
    config = tmp_path / "profile.json"
    config.write_text(profile().model_dump_json(), encoding="utf-8")
    seen: list[str] = []
    fail = False
    original = composition.build_local_memory

    def build(store: SQLiteStore, settings: LocalMemoryProfile | None = None) -> Any:
        return original(store, settings, transport=transport(seen, fail=fail))

    monkeypatch.setattr(composition, "build_local_memory", build)
    args = cli.build_parser().parse_args(
        ["demo", "--data", str(tmp_path), "--once", "charger", "--memory-profile", str(config)]
    )
    assert await cli._run_demo(args) == 0
    assert "離線示範模型" in capsys.readouterr().out
    fail = True
    assert await cli._run_demo(args) == 1
    output = capsys.readouterr().out
    assert "沒有送出回答" in output and "PRIVATE" not in output
    args.memory_profile = None
    before = len(seen)
    assert await cli._run_demo(args) == 0
    assert len(seen) == before


@pytest.mark.asyncio
async def test_composed_retrieval_cancellation_releases_owner(tmp_path: Path) -> None:
    store, _ = await seed(tmp_path / "siro.db")
    started = asyncio.Event()

    async def handle(request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    service = build_local_memory(store, profile(), transport=httpx.MockTransport(handle))
    task = asyncio.create_task(service.recall_context("siro", "charger"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not store._writer_lock.locked()
