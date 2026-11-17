from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy
from siro.services.agent import tool_decision
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


class ChattyModel:
    """A persona model that never emits tool calls on its own."""

    name = "chatty"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, _cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        yield ModelChunk("text", "磁碟還有很多空間喔。")
        yield ModelChunk("finished")


def make_decider(answers: list[object]) -> tool_decision.ToolDecider:
    async def chat(system: str, user: str, schema: Mapping[str, Any], num_predict: int) -> str:
        return json.dumps(answers.pop(0))

    return tool_decision.ToolDecider(chat=chat)


async def companion(
    tmp_path: Path, model: ChattyModel, executed: list[dict[str, object]]
) -> IntegratedCompanion:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()

    async def execute(arguments: dict[str, object]) -> object:
        executed.append(arguments)
        return {"stdout": "Filesystem 50G avail", "returncode": 0}

    return IntegratedCompanion(
        tmp_path,
        model,
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=ToolOrchestrator(
            SQLiteToolProposalRepository(store), {"computer.execute": execute}
        ),
        auto_authorize=lambda: True,
        runtime_profile="candidate",
    )


@pytest.mark.asyncio
async def test_decided_call_goes_through_proposal_path_with_paired_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decider = make_decider([{"tool": "execute"}, {"argv": ["df", "-h"]}])
    monkeypatch.setattr(tool_decision.ToolDecider, "from_env", classmethod(lambda cls: decider))
    model, executed = ChattyModel(), []
    controller = await companion(tmp_path, model, executed)
    await controller.respond("disk", "幫我看一下磁碟剩多少空間")
    # The approved tool ran with the decided arguments; the persona model only wrote the reply.
    assert executed == [{"argv": ["df", "-h"]}]
    assert len(model.requests) == 1
    messages = model.requests[0].messages
    assert [m.role for m in messages] == ["system", "user", "assistant", "tool"]
    assert messages[1].content == "幫我看一下磁碟剩多少空間"
    assert messages[2].tool_calls[0].name == "computer.execute"
    assert messages[2].tool_calls[0].call_id == messages[3].tool_call_id
    assert "50G avail" in messages[3].content


@pytest.mark.asyncio
async def test_flag_off_leaves_the_turn_unchanged(tmp_path: Path) -> None:
    model, executed = ChattyModel(), []
    controller = await companion(tmp_path, model, executed)
    assert controller._tool_decider is None
    await controller.respond("disk", "幫我看一下磁碟剩多少空間")
    assert executed == [] and len(model.requests) == 1
    assert [m.role for m in model.requests[0].messages] == ["system", "user"]


@pytest.mark.asyncio
async def test_none_decision_leaves_the_turn_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decider = make_decider([{"tool": "none"}])
    monkeypatch.setattr(tool_decision.ToolDecider, "from_env", classmethod(lambda cls: decider))
    model, executed = ChattyModel(), []
    controller = await companion(tmp_path, model, executed)
    await controller.respond("chat", "我今天好累")
    assert executed == [] and len(model.requests) == 1
    assert [m.role for m in model.requests[0].messages] == ["system", "user"]
