"""Loopback + token HTTP surface for the Windows shell and the owner (default: not mounted).

Mounted only when SIRO_COMPUTER_TOKEN (>= 32 chars) is set. The shell polls commands, posts
results, and mirrors the tray switch; the owner starts and inspects a run. All routes need the
token header; none of them can enable control on their own except the tray-driven ``state`` route.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import ClaudeVisionDecider, Decider
from siro.services.computer_use.loop import DecisionLoop, LoopReport
from siro.services.computer_use.safety import ControlGate

TOKEN_ENV = "SIRO_COMPUTER_TOKEN"
TOKEN_HEADER = "X-SIRO-Computer-Token"


class ResultBody(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    ok: bool
    error: str = Field(default="", max_length=80)
    data: dict[str, Any] | None = None


class StateBody(BaseModel):
    enabled: bool


class RunBody(BaseModel):
    goal: str = Field(min_length=2, max_length=500)


class ComputerRuns:
    """One run at a time; the report of the latest run stays readable."""

    def __init__(self, bridge: ComputerBridge, decider: Decider) -> None:
        self.bridge = bridge
        self._decider = decider
        self._task: asyncio.Task[None] | None = None
        self.goal = ""
        self.report: LoopReport | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, goal: str) -> bool:
        if self.running:
            return False
        self.goal, self.report = goal, None
        self._task = asyncio.create_task(self._run(goal))
        return True

    async def _run(self, goal: str) -> None:
        try:
            self.report = await DecisionLoop(self.bridge, self._decider).run(goal)
        except Exception as error:
            self.report = LoopReport("failed", f"crashed:{type(error).__name__}")

    def status(self) -> dict[str, Any]:
        gate = self.bridge.gate
        report = self.report
        return {
            "enabled": gate.enabled,
            "tripped": gate.tripped,
            "executor_online": self.bridge.executor_online,
            "running": self.running,
            "goal": self.goal,
            "report": None
            if report is None
            else {
                "state": report.state,
                "reason": report.reason,
                "steps": [
                    {
                        "step": s.step,
                        "action": s.action,
                        "expect": s.expect,
                        "outcome": s.outcome,
                        "screen_changed": s.screen_changed,
                    }
                    for s in report.steps
                ],
            },
        }


def build_router(token: str, runs: ComputerRuns) -> APIRouter:
    if len(token) < 32:
        raise ValueError(f"{TOKEN_ENV} must contain at least 32 characters")
    router = APIRouter(prefix="/v1/computer")
    bridge = runs.bridge

    def guard(request: Request) -> None:
        if request.client is None or request.client.host != "127.0.0.1":
            raise HTTPException(status_code=403, detail="computer control is loopback only")
        if not secrets.compare_digest(request.headers.get(TOKEN_HEADER, ""), token):
            raise HTTPException(status_code=401, detail="computer token is invalid")

    @router.post("/poll")
    async def poll(request: Request) -> Any:
        guard(request)
        command = await bridge.next_command(wait=20.0)
        if command is None:
            return Response(status_code=204)
        return command

    @router.post("/result")
    async def result(request: Request, body: ResultBody) -> dict[str, bool]:
        guard(request)
        return {"accepted": bridge.submit_result(body.id, body.ok, body.error, body.data)}

    @router.post("/stop")
    async def stop(request: Request) -> dict[str, bool]:
        guard(request)
        bridge.stop()
        return {"stopped": True}

    @router.post("/state")
    async def state(request: Request, body: StateBody) -> dict[str, bool]:
        """Mirror of the owner's tray switch (the only way, besides the env flag, to enable)."""
        guard(request)
        if body.enabled:
            bridge.gate.enable()
        else:
            bridge.gate.disable()
        return {"enabled": bridge.gate.enabled}

    @router.get("/status")
    async def status(request: Request) -> dict[str, Any]:
        guard(request)
        return runs.status()

    @router.post("/run")
    async def run(request: Request, body: RunBody) -> dict[str, bool]:
        guard(request)
        if not bridge.gate.enabled:
            raise HTTPException(status_code=409, detail="computer control is off")
        if not runs.start(body.goal):
            raise HTTPException(status_code=409, detail="a run is already in progress")
        return {"started": True}

    return router


def router_from_env(env: Mapping[str, str] | None = None) -> APIRouter | None:
    values = os.environ if env is None else env
    token = values.get(TOKEN_ENV)
    if not token:
        return None
    runs = ComputerRuns(ComputerBridge(ControlGate()), ClaudeVisionDecider())
    return build_router(token, runs)
