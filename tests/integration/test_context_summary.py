from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from siro.ports.models import CancellationToken, ModelChunk, ModelMessage, ModelRequest, ToolCall
from siro.services.agent.context import ContextBudgetExceeded, ContextBudgetModel
from siro.services.agent.summary import summarize_completed


class Provider:
    name = "summary-fixture"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        yield ModelChunk("text", "continued")


@pytest.mark.asyncio
async def test_budget_compaction_preserves_goals_sources_and_pending_pairs() -> None:
    provider = Provider()
    pending = ToolCall("pending", "filesystem.read", {"path": "x"})
    messages = (
        ModelMessage("system", "policy"),
        ModelMessage("user", "original goal"),
        ModelMessage("assistant", "start " + "x" * 9000 + " end"),
        ModelMessage("user", "continue"),
        ModelMessage("assistant", "", (pending,)),
        ModelMessage("tool", "latest result", tool_call_id="pending"),
    )
    request = ModelRequest("original goal", "g", messages=messages)
    model = ContextBudgetModel(provider, max_bytes=3000, summary_enabled=True)
    assert [c.text async for c in model.stream(request, CancellationToken())] == ["continued"]
    sent = provider.requests[0]
    assert sent.messages[:2] == messages[:2]
    assert sent.messages[-3:] == messages[-3:]
    assert "sha256:" in sent.messages[2].content
    assert request.messages == messages
    assert model.summarized_requests == 1
    assert summarize_completed(messages)[2] != messages[2]


@pytest.mark.asyncio
async def test_summary_never_trims_goal_or_latest_tool_observation() -> None:
    provider = Provider()
    call = ToolCall("c", "filesystem.read", {"path": "x"})
    request = ModelRequest(
        "goal",
        "g",
        messages=(
            ModelMessage("user", "goal"),
            ModelMessage("assistant", "", (call,)),
            ModelMessage("tool", "x" * 9000, tool_call_id="c"),
        ),
    )
    model = ContextBudgetModel(provider, max_bytes=3000, summary_enabled=True)
    with pytest.raises(ContextBudgetExceeded):
        _ = [c async for c in model.stream(request, CancellationToken())]
    assert not provider.requests
