from __future__ import annotations

from collections.abc import Sequence

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import Decision, StepRecord
from siro.services.computer_use.http import (
    TOKEN_HEADER,
    ComputerRuns,
    build_router,
    router_from_env,
)
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import ControlGate

TOKEN = "t" * 40
HEAD = {TOKEN_HEADER: TOKEN}


class NeverDecider:
    async def decide(
        self, goal: str, history: Sequence[StepRecord], observation: Observation
    ) -> Decision:
        return Decision("ask", None, "", "n/a", 1.0)


def _client(*, host: str = "127.0.0.1") -> tuple[TestClient, ComputerBridge]:
    bridge = ComputerBridge(ControlGate(enabled=False))
    app = FastAPI()
    app.include_router(build_router(TOKEN, ComputerRuns(bridge, NeverDecider())))
    return TestClient(app, client=(host, 5000)), bridge


def test_not_mounted_without_token() -> None:
    assert router_from_env({}) is None
    with pytest.raises(ValueError):
        build_router("short", ComputerRuns(ComputerBridge(ControlGate()), NeverDecider()))


def test_requires_loopback_and_token() -> None:
    client, _ = _client()
    assert client.get("/v1/computer/status").status_code == 401
    assert client.get("/v1/computer/status", headers={TOKEN_HEADER: "x" * 40}).status_code == 401
    remote, _ = _client(host="192.168.1.9")
    assert remote.get("/v1/computer/status", headers=HEAD).status_code == 403
    assert client.get("/v1/computer/status", headers=HEAD).json()["enabled"] is False


def test_state_stop_and_run_gating() -> None:
    client, bridge = _client()
    assert client.post("/v1/computer/run", headers=HEAD, json={"goal": "play"}).status_code == 409
    assert client.post("/v1/computer/state", headers=HEAD, json={"enabled": True}).json() == {
        "enabled": True
    }
    assert client.post("/v1/computer/stop", headers=HEAD).json() == {"stopped": True}
    assert bridge.gate.tripped and not bridge.gate.enabled
    assert client.post("/v1/computer/run", headers=HEAD, json={"goal": "play"}).status_code == 409
    client.post("/v1/computer/state", headers=HEAD, json={"enabled": True})
    assert bridge.gate.enabled  # tray re-enable clears the latch


def test_poll_returns_204_when_idle_and_result_for_unknown_is_rejected() -> None:
    client, _ = _client()
    assert client.post(
        "/v1/computer/result", headers=HEAD, json={"id": "zz", "ok": True}
    ).json() == {"accepted": False}
    bad = client.post("/v1/computer/result", headers=HEAD, json={"ok": True})
    assert bad.status_code == 422


def test_run_reports_owner_needed_and_executor_missing() -> None:
    client, _ = _client()
    client.post("/v1/computer/state", headers=HEAD, json={"enabled": True})
    started = client.post("/v1/computer/run", headers=HEAD, json={"goal": "play game"})
    assert started.json() == {"started": True}
    status = client.get("/v1/computer/status", headers=HEAD).json()
    assert status["executor_online"] is False
