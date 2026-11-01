# ruff: noqa: RUF001
from __future__ import annotations

from collections.abc import Sequence

import pytest

from siro.services.computer_use import http as computer_http
from siro.services.computer_use import tool
from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import Decision, StepRecord
from siro.services.computer_use.http import ComputerRuns, shared_runs
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import ControlGate


class AskDecider:
    async def decide(
        self, goal: str, history: Sequence[StepRecord], observation: Observation, **_kwargs
    ) -> Decision:
        return Decision("ask", None, "", "n/a", 1.0)


def _runs(enabled: bool = True) -> ComputerRuns:
    return ComputerRuns(ComputerBridge(ControlGate(enabled=enabled)), AskDecider())


def test_tools_absent_without_token() -> None:
    computer_http.reset_shared_runs()
    assert shared_runs({}) is None


def test_shared_runs_is_one_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    computer_http.reset_shared_runs()
    env = {"SIRO_COMPUTER_TOKEN": "t" * 40}
    try:
        assert shared_runs(env) is shared_runs(env) and shared_runs(env) is not None
    finally:
        computer_http.reset_shared_runs()


def test_definitions_and_effects() -> None:
    assert set(tool.DEFINITIONS) == tool.COMPUTER_TOOL_NAMES
    assert {tool.COMPUTER_STATUS} == tool.READ_ONLY  # play is never a read-only/planner tool
    assert tool.DEFINITIONS[tool.COMPUTER_PLAY].input_schema["required"] == ["goal"]


def test_readiness_needs_switch_and_connected_shell() -> None:
    runs = _runs(enabled=False)
    assert not tool.computer_ready(runs, tool.COMPUTER_PLAY)
    assert tool.computer_ready(runs, tool.COMPUTER_STATUS)
    runs.bridge.gate.enable()
    assert not tool.computer_ready(runs, tool.COMPUTER_PLAY)  # shell not polling yet
    runs.bridge._last_poll = runs.bridge._clock()
    assert tool.computer_ready(runs, tool.COMPUTER_PLAY)
    runs.bridge.stop()
    assert not tool.computer_ready(runs, tool.COMPUTER_PLAY)


@pytest.mark.asyncio
async def test_play_refuses_when_off_bad_goal_or_busy() -> None:
    runs = _runs(enabled=False)
    play = tool.computer_handlers(runs)[tool.COMPUTER_PLAY]
    with pytest.raises(PermissionError):
        await play({"goal": "win the game"})
    runs.bridge.gate.enable()
    for bad in ({}, {"goal": "x"}, {"goal": 5}, {"goal": "a" * 501}):
        with pytest.raises(ValueError, match="goal"):
            await play(bad)
    assert await play({"goal": "win the game"}) == {
        "started": True,
        "goal": "win the game",
        "reply_with": "已經開始操作電腦了，每步大約 7 到 10 秒；要停就按 Ctrl+Alt+Shift+Esc。",
    }
    with pytest.raises(RuntimeError, match="in progress"):
        await play({"goal": "again"})
    assert runs._task is not None
    await runs._task


@pytest.mark.asyncio
async def test_status_reports_run_outcome() -> None:
    runs = _runs()
    handlers = tool.computer_handlers(runs)
    await handlers[tool.COMPUTER_PLAY]({"goal": "win the game"})
    assert runs._task is not None
    await runs._task
    status = await handlers[tool.COMPUTER_STATUS]({})
    assert status["running"] is False
    assert status["report"]["state"] == "stopped"
    assert status["report"]["reason"] == "no_allowed_processes"
