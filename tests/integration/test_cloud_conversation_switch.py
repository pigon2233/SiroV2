"""Cloud conversation admission and cancellation, using synthetic inputs only."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest
from siro.services.presentation.gateway import GatewayState, create_app

ORIGIN = "http://testserver"


def authorization(client: TestClient, origin: str = ORIGIN) -> dict[str, str]:
    response = client.post("/v1/session", headers={"origin": origin})
    assert response.status_code == 200
    return {"authorization": f"Bearer {response.json()['token']}"}


def test_cloud_switch_blocks_callback_until_explicitly_enabled() -> None:
    state = GatewayState()
    state.routes["model"] = "cloud:synthetic"
    received: list[tuple[str, str, str]] = []

    async def on_turn(session_id: str, text: str, input_mode: str) -> None:
        received.append((session_id, text, input_mode))

    with TestClient(create_app(allowed_origins={ORIGIN}, state=state, on_turn=on_turn)) as client:
        headers = authorization(client)
        denied = client.post(
            "/v1/conversations/owner/turns", headers=headers, json={"text": "你好"}
        )
        assert denied.status_code == 403
        assert denied.json()["detail"] == "cloud conversation is disabled"
        assert not received
        assert not state.active_turns

        enabled = client.put("/v1/kill-switches/cloud", headers=headers, json={"enabled": True})
        assert enabled.status_code == 200
        accepted = client.post(
            "/v1/conversations/owner/turns", headers=headers, json={"text": "你好"}
        )
        assert accepted.status_code == 200
        assert received == [("owner", "你好", "text")]


def test_disabling_cloud_cancels_active_work_and_blocks_next_turn() -> None:
    state = GatewayState()
    state.routes["model"] = "cloud:synthetic"
    state.kill_switches["cloud"] = True
    cancelled: list[tuple[str, str]] = []
    received: list[str] = []

    async def on_cancel(turn_id: str, reason: str) -> None:
        cancelled.append((turn_id, reason))

    async def on_turn(_session_id: str, text: str, _input_mode: str) -> None:
        received.append(text)

    with TestClient(
        create_app(allowed_origins={ORIGIN}, state=state, on_turn=on_turn, on_cancel=on_cancel)
    ) as client:
        headers = authorization(client)
        assert client.put("/v1/kill-switches/cloud", json={"enabled": False}).status_code == 401
        assert not cancelled
        assert state.kill_switches["cloud"] is True

        disabled = client.put("/v1/kill-switches/cloud", headers=headers, json={"enabled": False})
        assert disabled.status_code == 200
        assert cancelled == [("active", "cloud disabled")]
        assert state.kill_switches["cloud"] is False
        assert (
            client.post(
                "/v1/conversations/owner/turns", headers=headers, json={"text": "你好"}
            ).status_code
            == 403
        )
        assert not received


@pytest.mark.parametrize("backend", ["ollama:synthetic", "offline"])
def test_cloud_disabled_does_not_block_local_conversation(backend: str) -> None:
    state = GatewayState()
    state.routes["model"] = backend
    received: list[str] = []

    async def on_turn(_session_id: str, text: str, _input_mode: str) -> None:
        received.append(text)

    with TestClient(create_app(allowed_origins={ORIGIN}, state=state, on_turn=on_turn)) as client:
        response = client.post(
            "/v1/conversations/owner/turns",
            headers=authorization(client),
            json={"text": "你好"},
        )
        assert response.status_code == 200
        assert received == ["你好"]
        assert state.kill_switches["cloud"] is False


def test_main_configured_cloud_starts_enabled_and_disable_stops_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uvicorn

    from siro.services.presentation import gateway

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    for key, value in {
        "SIRO_DATA_DIR": str(tmp_path),
        "SIRO_RUNTIME_PROFILE": "candidate",
        "SIRO_OPENAI_BASE_URL": "https://synthetic.invalid",
        "SIRO_OPENAI_MODEL": "synthetic",
        "SIRO_OPENAI_API_KEY": "synthetic-no-secret",  # pragma: allowlist secret
        "SIRO_CONTEXT_TOKEN_BUDGET_ENABLED": "0",
        "SIRO_WORKSPACE_ENABLED": "0",
        "SIRO_MEMORY_ORGANIZATION_ENABLED": "0",
        "SIRO_BROWSER_SESSION_ENABLED": "0",
    }.items():
        monkeypatch.setenv(key, value)
    requests: list[ModelRequest] = []

    async def synthetic_stream(
        _self: OpenAICompatibleAdapter,
        request: ModelRequest,
        cancellation: CancellationToken,
    ) -> AsyncIterator[ModelChunk]:
        assert not cancellation.cancelled
        requests.append(request)
        yield ModelChunk("text", "你好。我在。")
        yield ModelChunk("finished")

    apps: list[FastAPI] = []

    def capture_app(app: FastAPI, **_kwargs: object) -> None:
        apps.append(app)

    monkeypatch.setattr(OpenAICompatibleAdapter, "stream", synthetic_stream)
    monkeypatch.setattr(uvicorn, "run", capture_app)
    gateway.main()
    assert len(apps) == 1
    with TestClient(apps[0]) as client:
        headers = authorization(client, "http://127.0.0.1:8000")
        snapshot = client.get("/v1/snapshot", headers=headers).json()
        assert snapshot["routes"]["model"] == "cloud:synthetic"
        assert snapshot["kill_switches"]["cloud"] is True
        assert (
            client.post(
                "/v1/conversations/owner/turns", headers=headers, json={"text": "你好"}
            ).status_code
            == 200
        )
        assert len(requests) == 1
        assert (
            client.put(
                "/v1/kill-switches/cloud", headers=headers, json={"enabled": False}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/conversations/owner/turns", headers=headers, json={"text": "再聊聊"}
            ).status_code
            == 403
        )
        assert len(requests) == 1
