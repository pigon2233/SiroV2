# ruff: noqa: RUF001
from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest


def test_play_order_offers_only_computer_play_while_chat_keeps_all_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from siro.ports.models import CancellationToken, ModelChunk, ModelRequest
    from siro.services.computer_use import http as computer_http
    from siro.services.presentation.gateway import main

    requests: list[ModelRequest] = []

    class Model:
        name = "hook-fixture"

        def __init__(self, **kwargs: object) -> None:
            pass

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            requests.append(request)
            yield ModelChunk("text", "ok")
            yield ModelChunk("finished")

    for key in list(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic")
    monkeypatch.setenv("SIRO_COMPUTER_TOKEN", "t" * 40)
    monkeypatch.setattr("siro.adapters.models.ollama.OllamaAdapter", Model)
    monkeypatch.setattr("shutil.which", lambda name: None)
    computer_http.reset_shared_runs()

    def turn(client: TestClient, headers: dict[str, str], session: str, text: str) -> ModelRequest:
        before = len(requests)
        client.post(f"/v1/conversations/{session}/turns", headers=headers, json={"text": text})
        deadline = time.monotonic() + 10
        while len(requests) <= before and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(requests) > before
        return requests[before]

    seen: dict[str, set[str]] = {}

    def run(app: FastAPI, **kwargs: object) -> None:
        runs = computer_http.shared_runs()
        assert runs is not None
        runs.bridge.gate.enable()
        runs.bridge._last_poll = runs.bridge._clock()  # the Windows shell is polling
        with TestClient(app) as client:
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            headers = {"authorization": f"Bearer {token}"}
            for name, session, text in (
                ("order", "hook-a", "幫我玩UNDERTALE"),
                ("chat", "hook-b", "今天天氣如何"),
                ("question", "hook-c", "你會玩Undertale嗎？"),
            ):
                request = turn(client, headers, session, text)
                seen[name] = {t.name for t in request.tools}
                time.sleep(0.3)

    monkeypatch.setattr(uvicorn, "run", run)
    try:
        main()
    finally:
        computer_http.reset_shared_runs()
    assert seen["order"] == {"computer.play"}
    assert {"computer.play", "computer.status", "claude.ask", "filesystem.read"} <= seen["chat"]
    assert seen["question"] == seen["chat"]
