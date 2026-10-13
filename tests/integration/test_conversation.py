from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from siro.adapters.models.mock import MockModel
from siro.core.conversation import (
    ConversationEngine,
    ConversationSignal,
    SignalHandler,
    TurnState,
)
from siro.core.identity import IdentityService, ImmutableCore
from siro.persistence.conversation import SQLiteConversationRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelRequest,
    ToolCall,
    ToolDefinition,
)


async def engine(
    tmp_path: Path,
    model: MockModel,
    timeout: float = 1,
    on_signal: SignalHandler | None = None,
) -> ConversationEngine:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="A persistent companion",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        now=datetime.now(UTC),
    )
    repository = SQLiteConversationRepository(store)
    if on_signal is None:
        return ConversationEngine(model, repository, timeout_seconds=timeout)
    return ConversationEngine(model, repository, timeout_seconds=timeout, on_signal=on_signal)


@pytest.mark.asyncio
async def test_stream_completes_in_order(tmp_path: Path) -> None:
    deltas: list[str] = []
    signals: list[ConversationSignal] = []

    async def capture(text: str) -> None:
        deltas.append(text)

    async def record(signal: ConversationSignal) -> None:
        signals.append(signal)

    subject = await engine(tmp_path, MockModel(("a", "b", "c")), on_signal=record)

    result = await subject.respond("session", "siro", "hello", on_delta=capture)
    assert result.state is TurnState.COMPLETED
    assert result.text == "abc"
    assert deltas == ["a", "b", "c"]
    assert [signal.kind for signal in signals] == [
        "started",
        "text_delta",
        "text_delta",
        "text_delta",
        "terminal",
    ]
    assert {signal.trace_id for signal in signals} == {result.trace_id}
    assert [signal.index for signal in signals if signal.kind == "text_delta"] == [0, 1, 2]
    assert sum(signal.kind == "terminal" for signal in signals) == 1


@pytest.mark.asyncio
async def test_model_tool_request_is_preserved_for_orchestration(tmp_path: Path) -> None:
    class ToolModel:
        name = "tool-model"

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            del cancellation
            assert [tool.name for tool in request.tools] == ["computer"]
            yield ModelChunk(
                "tool_request",
                tool_call=ToolCall(
                    "call-1",
                    "computer",
                    {"goal": "install and open VS Code"},
                ),
            )
            yield ModelChunk("finished")

    subject = await engine(tmp_path, ToolModel())  # type: ignore[arg-type]
    result = await subject.respond(
        "session",
        "siro",
        "下載安裝並開啟 VS Code",
        tools=(ToolDefinition("computer", "Operate the computer", {"type": "object"}),),
    )

    assert result.state is TurnState.COMPLETED
    assert result.text == ""
    assert result.tool_calls == (
        ToolCall("call-1", "computer", {"goal": "install and open VS Code"}),
    )


@pytest.mark.asyncio
async def test_new_input_cancels_old_and_drops_late_chunks(tmp_path: Path) -> None:
    subject = await engine(
        tmp_path, MockModel(("old-1", "old-2", "old-3"), delay=0.01, ignore_cancellation=True)
    )
    first = asyncio.create_task(subject.respond("session", "siro", "first"))
    await asyncio.sleep(0.015)
    second = asyncio.create_task(subject.respond("session", "siro", "second"))
    old, new = await asyncio.gather(first, second)
    assert old.state is TurnState.CANCELLED
    assert "old-3" not in old.text
    assert new.state is TurnState.COMPLETED


@pytest.mark.asyncio
async def test_explicit_cancel_and_timeout_are_terminal(tmp_path: Path) -> None:
    subject = await engine(tmp_path, MockModel(("slow",), delay=0.05), timeout=0.01)
    timeout = await subject.respond("timeout", "siro", "hello")
    assert timeout.state is TurnState.FAILED
    assert timeout.error == "timeout"

    subject = await engine(tmp_path / "cancel", MockModel(("slow",), delay=0.05))
    task = asyncio.create_task(subject.respond("cancel", "siro", "hello"))
    await asyncio.sleep(0.005)
    assert await subject.cancel("cancel")
    cancelled = await task
    assert cancelled.state is TurnState.CANCELLED


@pytest.mark.asyncio
async def test_cancel_race_is_generation_safe_100_times(tmp_path: Path) -> None:
    subject = await engine(
        tmp_path, MockModel(("a", "b", "c"), delay=0.001, ignore_cancellation=True)
    )
    for index in range(100):
        session = f"race-{index}"
        old_task = asyncio.create_task(subject.respond(session, "siro", "old"))
        await asyncio.sleep(0.0015)
        new_task = asyncio.create_task(subject.respond(session, "siro", "new"))
        old, new = await asyncio.gather(old_task, new_task)
        assert old.state is TurnState.CANCELLED
        assert old.text != "abc"
        assert new.state is TurnState.COMPLETED
