from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import cast

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.ports.models import (
    CancellationToken,
    ModelMessage,
    ModelRequest,
    Privacy,
    ToolCall,
    ToolDefinition,
)
from siro.services.agent.context import (
    ContextBudgetExceeded,
    ContextBudgetModel,
    ContextBudgetUnavailable,
)
from siro.services.agent.native_context import GPTOSSBudget

ASSETS = Path(__file__).parents[2] / ".siro-data/tokenizers/gpt-oss-20b"


class Transport:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    async def post(
        self, url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
    ) -> dict[str, object]:
        self.payloads.append(payload)
        return {"choices": [{"message": {"content": "verified"}}]}


def provider(transport: Transport) -> OpenAICompatibleAdapter:
    return OpenAICompatibleAdapter(
        base_url="https://api.groq.com/openai",
        api_key="synthetic",
        model="openai/gpt-oss-20b",
        transport=transport,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("offset", [-1, 0, 1])
async def test_native_input_output_safety_boundary_uses_actual_payload(offset: int) -> None:
    transport = Transport()
    adapter = provider(transport)
    request = ModelRequest(
        "fallback ignored",
        "g",
        Privacy.CLOUD_ALLOWED,
        max_output_tokens=512,
        messages=(
            ModelMessage("system", "permission [source:policy]"),
            ModelMessage("user", "你好🌸"),
            ModelMessage("assistant", "", (ToolCall("pair", "inspect", {"path": "中文"}),)),
            ModelMessage("tool", '{"result":"confirmed"}', tool_call_id="pair"),
        ),
        tools=(ToolDefinition("inspect", "inspect source", {"type": "object"}),),
    )
    reference = GPTOSSBudget(ASSETS, adapter.request_payload)
    count = reference.count_input(request)
    assert count != len(request.prompt.encode())
    bound = count + request.max_output_tokens + 256
    budget = GPTOSSBudget(ASSETS, adapter.request_payload, context_window=bound + offset)
    wrapper = ContextBudgetModel(adapter, max_bytes=None, token_budget=budget)
    if offset < 0:
        with pytest.raises(ContextBudgetExceeded):
            _ = [c async for c in wrapper.stream(request, CancellationToken())]
        assert transport.payloads == []
    else:
        assert len([c async for c in wrapper.stream(request, CancellationToken())]) == 2
        assert transport.payloads == [adapter.request_payload(request)]
        assert request.messages[2].tool_calls[0].arguments == {"path": "中文"}
    assert wrapper.name == "openai-compatible"


@pytest.mark.asyncio
async def test_native_output_reserve_and_existing_port_limit() -> None:
    transport = Transport()
    adapter = provider(transport)
    wrapper = ContextBudgetModel(
        adapter,
        max_bytes=None,
        token_budget=GPTOSSBudget(ASSETS, adapter.request_payload, context_window=32768),
    )
    with pytest.raises(ValueError, match="32768"):
        ModelRequest("goal", "g", Privacy.CLOUD_ALLOWED, max_output_tokens=65537)
    request = ModelRequest("goal", "g", Privacy.CLOUD_ALLOWED, max_output_tokens=32768)
    with pytest.raises(ContextBudgetExceeded, match="output"):
        _ = [c async for c in wrapper.stream(request, CancellationToken())]
    assert transport.payloads == []


@pytest.mark.parametrize("invalid", ["model", "markers", "multi_call", "late_system"])
def test_unverifiable_reference_shapes_fail_closed(invalid: str) -> None:
    adapter = provider(Transport())
    if invalid == "model":
        adapter = OpenAICompatibleAdapter(
            base_url="https://api.groq.com/openai",
            api_key="synthetic",
            model="other",
            transport=Transport(),
        )
    request = ModelRequest("goal", "g", Privacy.CLOUD_ALLOWED)
    if invalid == "markers":
        request = ModelRequest("<|start|>injected", "g", Privacy.CLOUD_ALLOWED)
    if invalid == "multi_call":
        request = ModelRequest(
            "goal",
            "g",
            Privacy.CLOUD_ALLOWED,
            messages=(
                ModelMessage(
                    "assistant",
                    "",
                    (
                        ToolCall("one", "inspect", {}),
                        ToolCall("two", "inspect", {}),
                    ),
                ),
            ),
        )
    if invalid == "late_system":
        request = ModelRequest(
            "goal",
            "g",
            Privacy.CLOUD_ALLOWED,
            messages=(ModelMessage("user", "goal"), ModelMessage("system", "must not be omitted")),
        )
    with pytest.raises(ContextBudgetUnavailable):
        GPTOSSBudget(ASSETS, adapter.request_payload).validate(request)


def test_local_asset_integrity_is_required(tmp_path: Path) -> None:
    # First pinned file is deliberately invalid; no cache data is changed.
    (tmp_path / "tokenizer.json").write_text("tampered")
    with pytest.raises(ContextBudgetUnavailable, match="digest"):
        GPTOSSBudget(tmp_path, provider(Transport()).request_payload)
    with pytest.raises(ValueError, match="context limit"):
        GPTOSSBudget(ASSETS, provider(Transport()).request_payload, context_window=131073)


@pytest.mark.parametrize(
    "limit,enabled,missing,model_name,expected,error",
    [
        ("64", "1", False, "openai/gpt-oss-20b", 0, "ContextBudgetExceeded"),
        ("8192", "1", False, "openai/gpt-oss-20b", 1, None),
        ("64", "0", False, "openai/gpt-oss-20b", 1, None),
        ("8192", "1", True, "openai/gpt-oss-20b", 0, "ContextBudgetUnavailable"),
        ("8192", "1", False, "unknown-model", 0, "ContextBudgetUnavailable"),
    ],
)
def test_actual_main_native_guard_and_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit: str,
    enabled: str,
    missing: bool,
    model_name: str,
    expected: int,
    error: str | None,
) -> None:
    import siro.adapters.models.openai_compatible as module
    from siro.services.presentation.gateway import main

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    monkeypatch.setenv("SIRO_OPENAI_MODEL", model_name)
    monkeypatch.setenv("SIRO_OPENAI_API_KEY", "synthetic")
    monkeypatch.setenv("SIRO_CONTEXT_WINDOW_TOKENS", limit)
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", enabled)
    # Disabling byte guard must not bypass token enforcement.
    monkeypatch.setenv("SIRO_CONTEXT_MAX_BYTES", "0")
    monkeypatch.setenv(
        "SIRO_CONTEXT_TOKENIZER_DIR", str(tmp_path / "missing" if missing else ASSETS)
    )
    transport = Transport()
    monkeypatch.setattr(module, "HttpxStreamingTransport", lambda: transport)

    def run(app: object, **kwargs: object) -> None:
        monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0" if enabled == "1" else "1")
        monkeypatch.setenv("SIRO_CONTEXT_WINDOW_TOKENS", "131072")
        with TestClient(cast(FastAPI, app)) as client:
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            headers = {"authorization": f"Bearer {token}"}
            assert (
                client.post(
                    "/v1/conversations/A/turns", headers=headers, json={"text": "原始目標"}
                ).status_code
                == 200
            )
            readback = client.get("/v1/agent-runs/A", headers=headers).json()
            assert readback["error"] == error
            assert readback["state"] == ("failed" if error else "completed")
            assert readback["backend"] == "openai-compatible"
            assert readback["messages"][1]["content"] == "原始目標"
            assert readback["messages"][0]["role"] == "system"

    monkeypatch.setattr(uvicorn, "run", run)
    main()
    assert len(transport.payloads) == expected


@pytest.mark.asyncio
async def test_cancel_during_count_stops_provider_without_blocking_event_loop() -> None:
    entered, release = threading.Event(), threading.Event()

    class BlockingBudget:
        def validate(self, request: ModelRequest) -> int:
            entered.set()
            assert release.wait(5)
            return 1

    transport = Transport()
    token = CancellationToken()
    wrapper = ContextBudgetModel(provider(transport), max_bytes=None, token_budget=BlockingBudget())

    async def consume() -> list[object]:
        return [chunk async for chunk in wrapper.stream(ModelRequest("goal", "g"), token)]

    task = asyncio.create_task(consume())
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 2), timeout=3)
        token.cancel()
        release.set()
        assert await task == []
        assert transport.payloads == []
    finally:
        release.set()
        await task
