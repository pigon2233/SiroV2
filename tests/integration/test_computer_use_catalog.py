from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_computer_tools_appear_only_with_token_and_stay_gated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from siro.services.computer_use import http as computer_http
    from siro.services.presentation.gateway import main

    for key in list(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "local-test-model")
    monkeypatch.setenv("SIRO_COMPUTER_TOKEN", "t" * 40)
    monkeypatch.setattr("shutil.which", lambda name: None)
    computer_http.reset_shared_runs()
    seen: dict[str, object] = {}

    def run(app: FastAPI, **kwargs: object) -> None:
        with TestClient(app, client=("127.0.0.1", 5000)) as client:
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            headers = {"authorization": f"Bearer {token}"}
            tools = {
                t["name"]: t for t in client.get("/v1/runtime", headers=headers).json()["tools"]
            }
            seen["tools"] = tools
            # Control is OFF by default: play is unavailable, status can be read.
            seen["play_available"] = tools["computer.play"]["available"]
            seen["status_available"] = tools["computer.status"]["available"]
            # The loopback router shares the same state the tools read.
            computer = {"X-SIRO-Computer-Token": "t" * 40}
            seen["router_enabled"] = client.get("/v1/computer/status", headers=computer).json()[
                "enabled"
            ]
            client.post("/v1/computer/state", headers=computer, json={"enabled": True})
            tools = {
                t["name"]: t for t in client.get("/v1/runtime", headers=headers).json()["tools"]
            }
            # Enabled but the Windows shell has not connected: still unavailable.
            seen["play_after_enable"] = tools["computer.play"]["available"]

    monkeypatch.setattr(uvicorn, "run", run)
    try:
        main()
    finally:
        computer_http.reset_shared_runs()
    assert {"computer.play", "computer.status"} <= set(seen["tools"])  # type: ignore[arg-type]
    assert seen["play_available"] is False
    assert seen["status_available"] is True
    assert seen["router_enabled"] is False
    assert seen["play_after_enable"] is False
