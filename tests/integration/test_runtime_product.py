from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, ToolCall


class ProductModel:
    name = "synthetic-product"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        if request.messages[-1].role == "tool":
            yield ModelChunk("text", request.messages[-1].content)
        elif request.messages[-1].content == "read-workspace":
            yield ModelChunk(
                "tool_request", tool_call=ToolCall("read1", "filesystem.read", {"path": "note.txt"})
            )
        elif request.messages[-1].content == "long-answer":
            yield ModelChunk("text", "begin " + "detail " * 1500 + " end")
        else:
            yield ModelChunk("text", "recorded")


def boot(
    tmp: Path, monkeypatch: pytest.MonkeyPatch, *, enabled: bool = True
) -> tuple[TestClient, ProductModel]:
    import uvicorn

    from siro.services.presentation import gateway

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    for key, value in {
        "SIRO_DATA_DIR": str(tmp),
        "SIRO_RUNTIME_PROFILE": "candidate",
        "SIRO_OLLAMA_MODEL": "synthetic",
        "SIRO_CONTEXT_TOKEN_BUDGET_ENABLED": "0",
        "SIRO_CONTEXT_SUMMARY_ENABLED": str(int(enabled)),
        "SIRO_MEMORY_ORGANIZATION_ENABLED": str(int(enabled)),
        "SIRO_WORKSPACE_ENABLED": str(int(enabled)),
    }.items():
        monkeypatch.setenv(key, value)
    model = ProductModel()
    monkeypatch.setattr("siro.adapters.models.ollama.OllamaAdapter", lambda *a, **k: model)
    captured: dict[str, Any] = {}

    def serve(app: Any, **kwargs: Any) -> None:
        captured["app"] = app

    monkeypatch.setattr(uvicorn, "run", serve)
    gateway.main()
    return TestClient(captured["app"]), model


def auth(client: TestClient) -> dict[str, str]:
    response = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"})
    return {"authorization": "Bearer " + response.json()["token"]}


def test_main_rust_tool_digest_revision_delete_summary_and_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "note.txt").write_text("synthetic workspace observation")
    client, model = boot(tmp_path, monkeypatch)
    with client:
        headers = auth(client)
        status = client.get("/v1/runtime", headers=headers).json()
        assert status["features"]["workspace"]["available"]
        assert client.post("/v1/workspace/read?path=note.txt").status_code == 401
        direct = client.post("/v1/workspace/read?path=note.txt", headers=headers)
        assert direct.json()["result"]["text"] == "synthetic workspace observation"
        assert client.post("/v1/workspace/read?path=../siro.db", headers=headers).status_code == 403
        client.put("/v1/kill-switches/tools", headers=headers, json={"enabled": False})
        assert client.post("/v1/workspace/read?path=note.txt", headers=headers).status_code == 403
        client.put("/v1/kill-switches/tools", headers=headers, json={"enabled": True})
        assert status["features"]["summary"]["enabled"]
        assert any(
            t["name"] == "filesystem.read" and t["backend"] == "rust.scoped"
            for t in status["tools"]
        )
        client.post(
            "/v1/conversations/test/turns", headers=headers, json={"text": "read-workspace"}
        )
        assert "synthetic workspace observation" in model.requests[-1].messages[-1].content
        assert model.requests[-1].messages[-1].role == "tool"
        assert client.get("/v1/agent-runs/test", headers=headers).json()["state"] == "completed"
        for text in ["remember: tea", "long-answer", "continue", "continue-again"]:
            client.post("/v1/conversations/test/turns", headers=headers, json={"text": text})
        assert "Extractive summary v1" in str(model.requests[-1].messages)
        assert client.post("/v1/memory-organization?enabled=true&refresh=true").status_code == 401
        client.post("/v1/memory-organization?enabled=true&refresh=true", headers=headers)
        for _ in range(100):
            report = client.get("/v1/memory-organization", headers=headers).json()
            if report["groups"]:
                break
            time.sleep(0.01)
        assert report["groups"][0]["text"] == "tea"
        memories = client.get("/v1/memories", headers=headers).json()["items"]
        assert len(memories) == 1  # digest creates no extra facts
        memory_id = memories[0]["memory_id"]
        assert (
            client.post(
                f"/v1/memories/{memory_id}/correct",
                headers=headers,
                json={"text": "coffee", "reason": "synthetic correction"},
            ).status_code
            == 200
        )
        assert not client.get("/v1/memory-organization", headers=headers).json()["groups"]
        client.post(
            "/v1/conversations/test/turns",
            headers=headers,
            json={"text": "continue-after-correction"},
        )
        assert "Extractive summary v1" not in str(model.requests[-1].messages)
        assert "long-answer" not in str(model.requests[-1].messages)
        assert client.delete(f"/v1/memories/{memory_id}", headers=headers).status_code == 200
        assert not client.get("/v1/memories", headers=headers).json()["items"]
        assert not client.get("/v1/memory-organization", headers=headers).json()["groups"]
    # Drained restart with all three switches off preserves DB but removes new behavior.
    client, model = boot(tmp_path, monkeypatch, enabled=False)
    with client:
        headers = auth(client)
        features = client.get("/v1/runtime", headers=headers).json()["features"]
        assert not features["workspace"]["enabled"]
        assert not features["summary"]["enabled"]
        assert not features["memory_organization"]["enabled"]
        assert client.get("/v1/memories", headers=headers).json()["items"] == []
        client.post("/v1/conversations/fresh/turns", headers=headers, json={"text": "hello"})
        assert model.requests[-1].messages[-1].content == "hello"
