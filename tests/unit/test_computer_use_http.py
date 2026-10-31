from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from siro.services.computer_use import http as http_module
from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import Decision, StepRecord
from siro.services.computer_use.http import (
    TOKEN_HEADER,
    ComputerRuns,
    build_router,
    router_from_env,
)
from siro.services.computer_use.loop import LoopReport
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


@pytest.mark.asyncio
async def test_endless_session_chains_recoverable_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_AUTONOMOUS", "1")
    monkeypatch.setenv("SIRO_COMPUTER_ENDLESS", "1")
    monkeypatch.setenv("SIRO_COMPUTER_MAX_SEGMENTS", "3")
    monkeypatch.setenv("SIRO_COMPUTER_ALLOWED_PROCESSES", "game.exe")

    async def _no_sleep(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(http_module.asyncio, "sleep", _no_sleep)
    calls = {"n": 0}

    async def fake_run(self: Any, goal: str) -> LoopReport:
        calls["n"] += 1
        return LoopReport(
            "stopped",
            "step_limit",
            (StepRecord(1, "click", "x", "ok", True, "menu"),),
        )

    monkeypatch.setattr(http_module.DecisionLoop, "run", fake_run)
    bridge = ComputerBridge(ControlGate(enabled=True))
    runs = ComputerRuns(bridge, NeverDecider())
    assert runs.start("play forever")
    assert runs._task is not None
    await runs._task
    assert calls["n"] == 3
    assert runs.session_segments == 3
    assert runs.report is not None
    assert "session_segment_limit:3" in (runs.report.detail or "")


@pytest.mark.asyncio
async def test_endless_off_does_not_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_AUTONOMOUS", "1")
    monkeypatch.setenv("SIRO_COMPUTER_ENDLESS", "0")
    monkeypatch.delenv("SIRO_COMPUTER_MAX_SEGMENTS", raising=False)

    async def fake_run(self: Any, goal: str) -> LoopReport:
        return LoopReport("stopped", "step_limit", ())

    monkeypatch.setattr(http_module.DecisionLoop, "run", fake_run)
    runs = ComputerRuns(ComputerBridge(ControlGate(enabled=True)), NeverDecider())
    assert runs.start("play")
    assert runs._task is not None
    await runs._task
    assert runs.session_segments == 1


@pytest.mark.asyncio
async def test_endless_zero_segments_means_unlimited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_AUTONOMOUS", "1")
    monkeypatch.setenv("SIRO_COMPUTER_ENDLESS", "1")
    monkeypatch.setenv("SIRO_COMPUTER_MAX_SEGMENTS", "0")

    async def _no_sleep(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(http_module.asyncio, "sleep", _no_sleep)
    calls = {"n": 0}

    async def fake_run(self: Any, goal: str) -> LoopReport:
        calls["n"] += 1
        if calls["n"] >= 5:
            return LoopReport("stopped", "emergency_stop", ())
        return LoopReport("stopped", "step_limit", ())

    monkeypatch.setattr(http_module.DecisionLoop, "run", fake_run)
    runs = ComputerRuns(ComputerBridge(ControlGate(enabled=True)), NeverDecider())
    assert runs.start("play forever")
    assert runs._task is not None
    await runs._task
    assert calls["n"] == 5
    assert runs.session_segments == 5
    assert runs.report is not None
    assert runs.report.reason == "emergency_stop"
