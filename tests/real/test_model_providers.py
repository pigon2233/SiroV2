from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import pytest

from siro.adapters.models.ollama import OllamaAdapter
from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.core.companion import CompanionCore
from siro.core.conversation import ConversationEngine, TurnState
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import MemoryService
from siro.persistence.conversation import SQLiteConversationRepository
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy


class StreamAdapter(Protocol):
    def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]: ...


async def text_from(adapter: StreamAdapter, request: ModelRequest) -> str:
    chunks: list[ModelChunk] = [
        chunk async for chunk in adapter.stream(request, CancellationToken())
    ]
    return "".join(chunk.text for chunk in chunks if chunk.kind == "text")


@pytest.mark.real_provider
@pytest.mark.asyncio
async def test_configured_openai_compatible_provider() -> None:
    if os.environ.get("SIRO_RUN_REAL_PROVIDERS") != "1":
        pytest.skip("set SIRO_RUN_REAL_PROVIDERS=1 to permit an external request")
    key = os.environ.get("SIRO_OPENAI_API_KEY")
    model = os.environ.get("SIRO_OPENAI_MODEL")
    if not key or not model:
        pytest.skip("set SIRO_OPENAI_API_KEY and SIRO_OPENAI_MODEL for real provider L2")
    adapter = OpenAICompatibleAdapter(
        base_url=os.environ.get("SIRO_OPENAI_BASE_URL", "https://api.openai.com"),
        api_key=key,
        model=model,
    )
    result = await text_from(
        adapter,
        ModelRequest("Reply with OK.", "real-openai", Privacy.CLOUD_ALLOWED, 128),
    )
    assert result.strip()


@pytest.mark.real_provider
@pytest.mark.asyncio
async def test_configured_ollama_provider() -> None:
    if os.environ.get("SIRO_RUN_REAL_PROVIDERS") != "1":
        pytest.skip("set SIRO_RUN_REAL_PROVIDERS=1 to run real provider tests")
    model = os.environ.get("SIRO_OLLAMA_MODEL")
    if not model:
        pytest.skip("set SIRO_OLLAMA_MODEL for real provider L2")
    adapter = OllamaAdapter(
        base_url=os.environ.get("SIRO_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        model=model,
    )
    result = await text_from(
        adapter, ModelRequest("Reply with OK.", "real-ollama", max_output_tokens=16)
    )
    assert result.strip()


@pytest.mark.real_provider
@pytest.mark.asyncio
async def test_identity_survives_real_backend_swap(tmp_path: Path) -> None:
    if os.environ.get("SIRO_RUN_REAL_PROVIDERS") != "1":
        pytest.skip("set SIRO_RUN_REAL_PROVIDERS=1 to run real provider tests")
    key = os.environ.get("SIRO_OPENAI_API_KEY")
    cloud_model = os.environ.get("SIRO_OPENAI_MODEL")
    local_model = os.environ.get("SIRO_OLLAMA_MODEL")
    if not key or not cloud_model or not local_model:
        pytest.skip("configure both cloud and local models for real A03")

    store = SQLiteStore(tmp_path / "real-a03.db")
    await store.initialize()
    identities = SQLiteIdentityRepository(store)
    created = await IdentityService(identities).create(
        "siro-real-a03",
        ImmutableCore(
            name="SIRO Test",
            baseline_identity="Synthetic provider integration identity",
            core_values=("honesty",),
            creator_relationship="test owner",
        ),
        now=datetime.now(UTC),
    )
    memory = MemoryService(SQLiteMemoryRepository(store))

    cloud = OpenAICompatibleAdapter(
        base_url=os.environ.get("SIRO_OPENAI_BASE_URL", "https://api.openai.com"),
        api_key=key,
        model=cloud_model,
    )
    cloud_core = CompanionCore(
        identities,
        memory,
        ConversationEngine(cloud, SQLiteConversationRepository(store)),
    )
    cloud_result = await cloud_core.respond(
        "cloud-session",
        created.identity_id,
        "Reply with OK to this synthetic integration test.",
        privacy=Privacy.CLOUD_ALLOWED,
    )

    local = OllamaAdapter(
        base_url=os.environ.get("SIRO_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        model=local_model,
    )
    local_core = CompanionCore(
        identities,
        memory,
        ConversationEngine(local, SQLiteConversationRepository(store)),
    )
    local_result = await local_core.respond("local-session", created.identity_id, "Reply with OK.")
    persisted = await identities.get(created.identity_id)

    assert cloud_result.state is TurnState.COMPLETED and cloud_result.text.strip()
    assert local_result.state is TurnState.COMPLETED and local_result.text.strip()
    assert persisted is not None
    assert persisted.identity_id == created.identity_id
    assert persisted.core == created.core
