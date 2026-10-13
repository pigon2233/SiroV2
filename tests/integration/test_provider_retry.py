from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
from siro.services.agent.runs import SQLiteAgentRunRepository


@pytest.mark.parametrize(
    "profile,mode,disabled,expected_requests,expected_effect,state",
    [
        ("candidate", "retry_then_tool", False, 3, True, "completed"),
        ("candidate", "always_fail", False, 2, False, "failed"),
        ("legacy", "always_fail", False, 1, False, "failed"),
        ("candidate", "always_fail", True, 1, False, "failed"),
        ("candidate", "tool_then_fail", False, 1, False, "failed"),
        ("candidate", "text_then_fail", False, 1, False, "failed"),
        ("candidate", "continuation_tool_failure", False, 2, True, "failed"),
        ("candidate", "cloud_fail", False, 1, False, "failed"),
        ("candidate", "cloud_fail", True, 1, False, "failed"),
    ],
)
def test_real_main_provider_policy_and_dispatch_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    mode: str,
    disabled: bool,
    expected_requests: int,
    expected_effect: bool,
    state: str,
) -> None:
    import siro.adapters.models.ollama as ollama
    import siro.adapters.models.openai_compatible as cloud
    from siro.services.presentation.gateway import main

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    # Synthetic providers have no native tokenizer; preserve this fixture scope.
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", profile)
    monkeypatch.setenv("SIRO_MODEL_RETRY_ENABLED", "0" if disabled else "1")
    # Both are configured to ensure original local priority does not gain cloud fallback.
    monkeypatch.setenv("SIRO_OPENAI_MODEL", "synthetic-cloud")
    monkeypatch.setenv("SIRO_OPENAI_API_KEY", "synthetic-key-canary")
    if mode != "cloud_fail":
        monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic-local")
    marker = tmp_path / "effect.txt"
    requests: list[ModelRequest] = []
    cloud_created: list[bool] = []

    class Local:
        name = "synthetic-local"

        def __init__(self, *, model: str) -> None:
            pass

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            requests.append(request)
            index = len(requests)
            failure = mode in {"always_fail", "cloud_fail"} or (
                mode == "retry_then_tool" and index == 1
            )
            if failure:
                if mode == "cloud_fail":
                    req = httpx.Request("POST", "http://synthetic.invalid")
                    raise httpx.HTTPStatusError(
                        "synthetic429", request=req, response=httpx.Response(429, request=req)
                    )
                raise ConnectionError("synthetic unavailable")
            if mode == "text_then_fail":
                yield ModelChunk("text", "partial")
                raise ConnectionError("after text")
            if (
                mode == "tool_then_fail"
                or (mode == "retry_then_tool" and index == 2)
                or (mode == "continuation_tool_failure" and index in {1, 2})
            ):
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall(
                        "repeatable-provider-id-" + str(index),
                        "computer.execute",
                        {
                            "argv": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; "
                                f"Path({str(marker)!r}).write_text('one real effect')",
                            ]
                        },
                    ),
                )
                if mode == "tool_then_fail" or (mode == "continuation_tool_failure" and index == 2):
                    raise ConnectionError("after tool intent")
            else:
                yield ModelChunk("text", "confirmed")
            yield ModelChunk("finished")

    class Cloud(Local):
        name = "synthetic-cloud"

        def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
            cloud_created.append(True)

    monkeypatch.setattr(ollama, "OllamaAdapter", Local)
    monkeypatch.setattr(cloud, "OpenAICompatibleAdapter", Cloud)

    def run(app: object, **kwargs: object) -> None:
        # Startup captures the choice; later environment changes cannot alter this generation.
        monkeypatch.setenv("SIRO_MODEL_RETRY_ENABLED", "1" if disabled else "0")
        with TestClient(cast(FastAPI, app)) as client:
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            headers = {"authorization": f"Bearer {token}"}
            response = client.post(
                "/v1/conversations/retry/turns", headers=headers, json={"text": "synthetic goal"}
            )
            assert response.status_code == 200
            readback = client.get("/v1/agent-runs/retry", headers=headers).json()
            assert readback["state"] == state
            runtime = client.get("/v1/runtime", headers=headers).json()
            assert runtime["routes"]["model"] == (
                "cloud:synthetic-cloud" if mode == "cloud_fail" else "ollama:synthetic-local"
            )
            assert "synthetic-key-canary" not in str(runtime)
            if profile == "candidate":
                assert readback["backend"] == (
                    "synthetic-cloud" if mode == "cloud_fail" else "synthetic-local"
                )
                assert readback["model_rounds"] == (2 if expected_effect else 1)
                if mode == "continuation_tool_failure":
                    assert readback["tool_calls"] == 1
                    assert len([m for m in readback["messages"] if m["role"] == "tool"]) == 1
                if mode in {"tool_then_fail", "text_then_fail", "always_fail", "cloud_fail"}:
                    assert readback["tool_calls"] == 0

    monkeypatch.setattr(uvicorn, "run", run)
    main()
    if profile == "candidate":
        selected = "synthetic-cloud" if mode == "cloud_fail" else "synthetic-local"
        with sqlite3.connect(tmp_path / "siro.db") as connection:
            assert connection.execute("SELECT backend FROM run_journal").fetchall() == [(selected,)]

        async def reopened_readback() -> None:
            store = SQLiteStore(tmp_path / "siro.db")
            await store.initialize()
            persisted = await SQLiteAgentRunRepository(store).readback("retry")
            assert persisted is not None and persisted["backend"] == selected
            assert persisted["state"] == state

        asyncio.run(reopened_readback())
    assert len(requests) == expected_requests
    assert marker.exists() is expected_effect
    assert len(cloud_created) == int(mode == "cloud_fail")
    assert all(
        r.privacy is (Privacy.CLOUD_ALLOWED if mode == "cloud_fail" else Privacy.LOCAL_ONLY)
        for r in requests
    )
    if mode == "retry_then_tool":
        assert requests[0].generation_id != requests[1].generation_id
        assert requests[0].messages == requests[1].messages
        assert requests[2].messages[-1].tool_call_id == "repeatable-provider-id-2"
