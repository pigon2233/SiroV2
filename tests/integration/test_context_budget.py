from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import asdict
from pathlib import Path
from typing import cast

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.adapters.models.failover import FailoverModel
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import (
    CancellationToken,
    ModelChunk,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
    ToolDefinition,
)
from siro.services.agent.context import (
    ContextBudgetExceeded,
    ContextBudgetModel,
    request_size_bytes,
)
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


class CaptureModel:
    name = "selected-provider"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        yield ModelChunk("text", "done")
        yield ModelChunk("finished")


@pytest.mark.asyncio
async def test_explicit_generation_budget_is_checked_before_provider_dispatch() -> None:
    provider = CaptureModel()
    seen: list[int] = []

    class Budget:
        def validate(self, request: ModelRequest) -> int:
            seen.append(request.max_output_tokens)
            if request.max_output_tokens > 2048:
                raise ContextBudgetExceeded("synthetic total context capacity")
            return 1

    model = ContextBudgetModel(
        provider, max_bytes=10000, token_budget=Budget(), max_output_tokens=4096
    )
    request = ModelRequest("unchanged original input", "g", max_output_tokens=512)
    with pytest.raises(ContextBudgetExceeded):
        _ = [chunk async for chunk in model.stream(request, CancellationToken())]
    assert seen == [4096] and provider.requests == []
    assert request.max_output_tokens == 512  # Caller request is immutable.


@pytest.mark.asyncio
async def test_explicit_generation_budget_preserves_native_messages_and_pending_tools() -> None:
    provider = CaptureModel()
    messages = (
        ModelMessage("assistant", "", (ToolCall("pending", "synthetic", {}),)),
        ModelMessage("tool", "synthetic readback", tool_call_id="pending"),
    )
    request = ModelRequest("original", "g", messages=messages)
    model = ContextBudgetModel(provider, max_bytes=10000, max_output_tokens=4096)
    _ = [chunk async for chunk in model.stream(request, CancellationToken())]
    assert provider.requests[0].max_output_tokens == 4096
    assert provider.requests[0].messages == messages
    assert request.max_output_tokens == 512


@pytest.mark.parametrize("value", [0, True, 32769, 1.5])
def test_generation_budget_is_bounded(value: object) -> None:
    with pytest.raises(ValueError):
        ContextBudgetModel(CaptureModel(), max_bytes=10000, max_output_tokens=value)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize("offset", [-1, 0, 1])
async def test_exact_byte_boundary_preserves_complete_request(offset: int) -> None:
    call = ToolCall("pending", "computer.execute", {"argv": ["true"]})
    request = ModelRequest(
        "fallback 原始目標",
        "generation",
        Privacy.LOCAL_ONLY,
        tools=(ToolDefinition("computer.execute", "permission facts", {"type": "object"}),),
        messages=(
            ModelMessage("system", "authorization facts [source:policy]"),
            ModelMessage("user", "原始目標"),
            ModelMessage("assistant", "", (call,)),
            ModelMessage("tool", "huge result " + "好" * 1000, tool_call_id="pending"),
        ),
    )
    encoded = json.dumps(asdict(request), ensure_ascii=False, separators=(",", ":")).encode()
    assert request_size_bytes(request) == len(encoded)
    provider = CaptureModel()
    model = ContextBudgetModel(FailoverModel((provider,)), max_bytes=len(encoded) + offset)
    token = CancellationToken()
    if offset < 0:
        with pytest.raises(ContextBudgetExceeded):
            _ = [chunk async for chunk in model.stream(request, token)]
        assert provider.requests == []
    else:
        assert len([chunk async for chunk in model.stream(request, token)]) == 2
        assert provider.requests == [request] and provider.requests[0] is request
    assert model.name == provider.name
    assert request.messages[-1].tool_call_id == "pending"


@pytest.mark.asyncio
async def test_cancel_and_invalid_budget_do_not_invoke_provider() -> None:
    provider = CaptureModel()
    with pytest.raises(ValueError):
        ContextBudgetModel(provider, max_bytes=0)
    token = CancellationToken()
    token.cancel()
    model = ContextBudgetModel(provider, max_bytes=1)
    assert [c async for c in model.stream(ModelRequest("large", "g"), token)] == []
    assert provider.requests == []


@pytest.mark.parametrize(
    "profile,limit,expected_calls,error",
    [
        ("candidate", "64", 0, "ContextBudgetExceeded"),
        ("candidate", "0", 1, None),
        ("legacy", "64", 1, None),
    ],
)
def test_actual_main_budget_and_feature_off(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    limit: str,
    expected_calls: int,
    error: str | None,
) -> None:
    import siro.adapters.models.ollama as ollama
    from siro.services.presentation.gateway import main

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    # Synthetic providers have no native tokenizer; preserve this fixture scope.
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", profile)
    monkeypatch.setenv("SIRO_CONTEXT_MAX_BYTES", limit)
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic-context")
    provider = CaptureModel()
    monkeypatch.setattr(ollama, "OllamaAdapter", lambda **kwargs: provider)

    def run(app: object, **kwargs: object) -> None:
        monkeypatch.setenv("SIRO_CONTEXT_MAX_BYTES", "65536" if limit != "0" else "1")
        with TestClient(cast(FastAPI, app)) as client:
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            headers = {"authorization": f"Bearer {token}"}
            assert (
                client.post(
                    "/v1/conversations/A/turns", headers=headers, json={"text": "保留原始目標"}
                ).status_code
                == 200
            )
            readback = client.get("/v1/agent-runs/A", headers=headers).json()
            assert readback["state"] == ("failed" if error else "completed")
            assert readback["error"] == error
            if profile == "candidate":
                assert readback["backend"] == provider.name
                assert readback["messages"][1]["content"] == "保留原始目標"
                assert readback["messages"][0]["role"] == "system"

    monkeypatch.setattr(uvicorn, "run", run)
    main()
    assert len(provider.requests) == expected_calls


@pytest.mark.asyncio
async def test_large_tool_result_fails_before_continuation_and_keeps_journal_pair(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    effects: list[bool] = []

    class ToolModel(CaptureModel):
        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            self.requests.append(request)
            yield ModelChunk("tool_request", tool_call=ToolCall("pair", "computer.execute", {}))
            yield ModelChunk("finished")

    async def execute(arguments: dict[str, object]) -> object:
        effects.append(True)
        return {"stdout": "huge" * 100_000}

    provider = ToolModel()
    controller = IntegratedCompanion(
        tmp_path,
        ContextBudgetModel(provider, max_bytes=65536),
        GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
        tool_orchestrator=ToolOrchestrator(
            SQLiteToolProposalRepository(store), {"computer.execute": execute}
        ),
    )
    await controller.respond("A", "immutable goal")
    readback = await controller.recovery_readback("A")
    assert len(provider.requests) == 1 and effects == [True]
    assert readback is not None
    assert readback["state"] == "failed" and readback["error"] == "ContextBudgetExceeded"
    messages = cast(list[dict[str, object]], readback["messages"])
    assert messages[0]["role"] == "system" and messages[1]["content"] == "immutable goal"
    assert messages[2]["role"] == "assistant" and messages[3]["role"] == "tool"
    assert messages[3]["tool_call_id"] == "pair"
    assert "huge" * 100_000 in str(messages[3]["content"])
    assert readback["tool_calls"] == 1
