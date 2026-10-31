"""Loopback + token HTTP surface for the Windows shell and the owner (default: not mounted).

Mounted only when SIRO_COMPUTER_TOKEN (>= 32 chars) is set. The shell polls commands, posts
results, and mirrors the tray switch; the owner starts and inspects a run. All routes need the
token header; none of them can enable control on their own except the tray-driven ``state`` route.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import ClaudeVisionDecider, Decider, StepRecord
from siro.services.computer_use.demos import DemoRecorder, demos_dir
from siro.services.computer_use.loop import ComputerLimitError, DecisionLoop, LoopReport
from siro.services.computer_use.playbook import ClaudeReflector, PlaybookStore, playbook_dir
from siro.services.computer_use.safety import ControlGate

TOKEN_ENV = "SIRO_COMPUTER_TOKEN"
TOKEN_HEADER = "X-SIRO-Computer-Token"
AUTONOMOUS_FLAG = "SIRO_COMPUTER_AUTONOMOUS"
ENDLESS_FLAG = (
    "SIRO_COMPUTER_ENDLESS"  # with autonomous: start another segment after recoverable stops
)
MAX_SEGMENTS_ENV = "SIRO_COMPUTER_MAX_SEGMENTS"
DEFAULT_MAX_SEGMENTS = 48
MAX_CONFIGURED_SEGMENTS = 500
# Reasons that may continue a long autonomous session (never emergency / privacy / unknown).
_CONTINUE_REASONS = frozenset(
    {
        "step_limit",
        "time_limit",
        "stuck_waiting",
        "stuck_no_visible_change",
        "too_many_invalid_decisions",
        "decider_stuck",
        "low_confidence",
        "done_without_evidence",
    }
)


class ResultBody(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    ok: bool
    error: str = Field(default="", max_length=80)
    data: dict[str, Any] | None = None


class StateBody(BaseModel):
    enabled: bool


class RunBody(BaseModel):
    goal: str = Field(min_length=2, max_length=500)


class Reflector(Protocol):
    async def reflect(
        self,
        game: str,
        goal: str,
        state: str,
        reason: str,
        existing: Sequence[str],
        steps: Sequence[StepRecord],
    ) -> list[str]: ...


class ComputerRuns:
    """One owner session at a time; may chain segments when endless autonomous play is on."""

    def __init__(
        self,
        bridge: ComputerBridge,
        decider: Decider,
        *,
        playbook: PlaybookStore | None = None,
        reflector: Reflector | None = None,
        recorder: DemoRecorder | None = None,
    ) -> None:
        self.bridge = bridge
        self.recorder = recorder
        self._decider = decider
        self.playbook = playbook
        self._reflector = reflector
        self.learned = 0  # lessons added by the last finished segment
        self.session_segments = 0
        self.session_learned = 0
        self._task: asyncio.Task[None] | None = None
        self._loop: DecisionLoop | None = None
        self.goal = ""
        self.report: LoopReport | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, goal: str) -> bool:
        if self.running:
            return False
        self.goal, self.report, self._loop = goal, None, None
        self.learned = self.session_learned = self.session_segments = 0
        self._task = asyncio.create_task(self._run(goal))
        return True

    def _endless(self) -> bool:
        env = os.environ
        return env.get(AUTONOMOUS_FLAG, "0") == "1" and env.get(ENDLESS_FLAG, "0") == "1"

    def _max_segments(self) -> int:
        raw = os.environ.get(MAX_SEGMENTS_ENV)
        if raw is None:
            return DEFAULT_MAX_SEGMENTS
        if not raw.isascii() or not raw.isdigit() or len(raw) > 4:
            raise ComputerLimitError(f"invalid {MAX_SEGMENTS_ENV}")
        value = int(raw)
        if not 1 <= value <= MAX_CONFIGURED_SEGMENTS:
            raise ComputerLimitError(f"invalid {MAX_SEGMENTS_ENV}")
        return value

    def _should_continue(self, report: LoopReport) -> bool:
        if not self._endless() or not self.bridge.gate.enabled:
            return False
        if report.reason in {"emergency_stop", "control_disabled", "executor_offline"}:
            return False
        if report.reason in {
            "window_not_allowed",
            "cloud_screen_not_allowed",
            "no_allowed_processes",
            "outcome_unknown",
            "invalid_run_limits",
        }:
            return False
        if report.reason.startswith("blocked_") or report.reason.startswith("crashed:"):
            return False
        if report.state == "done":
            return True  # open-ended play: a "done" segment still continues until the owner stops
        if report.reason in _CONTINUE_REASONS:
            return True
        return bool(report.reason.startswith("decider_error:"))

    async def _run(self, goal: str) -> None:
        try:
            max_segments = self._max_segments()
        except ComputerLimitError as error:
            self.report = LoopReport("failed", "invalid_run_limits", detail=str(error))
            return
        segment_goal = goal
        while True:
            self.session_segments += 1
            try:
                self._loop = DecisionLoop(
                    self.bridge, self._decider, playbook=self.playbook, recorder=self.recorder
                )
                self.report = await self._loop.run(segment_goal)
            except ComputerLimitError as error:
                self.report = LoopReport("failed", "invalid_run_limits", detail=str(error))
                return
            except Exception as error:
                self.report = LoopReport("failed", f"crashed:{type(error).__name__}")
                return
            await self._learn(segment_goal)
            self.session_learned += self.learned
            report = self.report
            assert report is not None
            if (
                not self._should_continue(report)
                or self.session_segments >= max_segments
                or not self.bridge.gate.enabled
            ):
                if self._endless() and self.session_segments >= max_segments:
                    self.report = LoopReport(
                        report.state,
                        report.reason,
                        report.steps,
                        detail=(report.detail + " | " if report.detail else "")
                        + f"session_segment_limit:{max_segments}",
                    )
                return
            await asyncio.sleep(1.5)
            if not self.bridge.gate.enabled:
                return
            segment_goal = (
                f"{goal}\n\nContinue from the current screen. Previous segment ended with "
                f"{report.state}/{report.reason}. Keep playing; do not ask the owner."
            )

    async def _learn(self, goal: str) -> None:
        """After a run, turn what happened into a few reusable notes (best effort, never raises)."""
        report, loop = self.report, self._loop
        self.learned = 0
        if self.playbook is None or self._reflector is None or report is None or loop is None:
            return
        if (
            not loop.process
            or not report.steps
            or report.reason in {"emergency_stop", "window_not_allowed"}
        ):
            return
        try:
            lessons = await self._reflector.reflect(
                loop.process,
                goal,
                report.state,
                report.reason,
                self.playbook.texts(loop.process),
                report.steps,
            )
            self.learned = self.playbook.add(loop.process, lessons, uuid4().hex[:12])
        except Exception:
            self.learned = 0

    def status(self) -> dict[str, Any]:
        gate = self.bridge.gate
        report = self.report
        live = self._loop.live if self.running and self._loop is not None else []
        limits = None if self._loop is None else dict(self._loop.limits)
        if limits is not None:
            limits["endless"] = self._endless()
            limits["session_segments"] = self.session_segments
        return {
            "enabled": gate.enabled,
            "tripped": gate.tripped,
            "executor_online": self.bridge.executor_online,
            "running": self.running,
            "goal": self.goal,
            "live_steps": _steps(live),
            "limits": limits,
            "phase": None if self._loop is None else self._loop.phase,
            "learned_notes": self.session_learned if self.session_learned else self.learned,
            "session_segments": self.session_segments,
            "report": None
            if report is None
            else {
                "state": report.state,
                "reason": report.reason,
                "detail": report.detail,
                "steps": _steps(report.steps),
            },
        }


def _steps(records: Sequence[StepRecord]) -> list[dict[str, Any]]:
    return [
        {
            "step": s.step,
            "action": s.action,
            "expect": s.expect,
            "outcome": s.outcome,
            "screen_changed": s.screen_changed,
            "seen": s.seen,
        }
        for s in records
    ]


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

    @router.get("/playbook/{process}")
    async def playbook_notes(request: Request, process: str) -> dict[str, Any]:
        guard(request)
        store = runs.playbook
        notes = [] if store is None else store.notes(process)
        return {
            "process": process.lower(),
            "notes": [
                {"index": i, "text": n.text, "run_id": n.run_id, "at": n.at}
                for i, n in enumerate(notes)
            ],
        }

    @router.delete("/playbook/{process}")
    async def playbook_delete(
        request: Request, process: str, index: int | None = None
    ) -> dict[str, bool]:
        guard(request)
        if runs.playbook is None:
            raise HTTPException(status_code=404, detail="playbooks are off")
        if index is None:
            runs.playbook.clear(process)
            return {"deleted": True}
        return {"deleted": runs.playbook.remove(process, index)}

    @router.get("/demos")
    async def demo_list(request: Request) -> dict[str, Any]:
        guard(request)
        recorder = runs.recorder
        return {
            "recording": recorder is not None,
            "runs": [] if recorder is None else recorder.summary(),
        }

    @router.delete("/demos")
    async def demo_delete(request: Request, process: str | None = None) -> dict[str, int]:
        guard(request)
        return {"deleted_runs": 0 if runs.recorder is None else runs.recorder.clear(process)}

    @router.post("/run")
    async def run(request: Request, body: RunBody) -> dict[str, bool]:
        guard(request)
        if not bridge.gate.enabled:
            raise HTTPException(status_code=409, detail="computer control is off")
        if not runs.start(body.goal):
            raise HTTPException(status_code=409, detail="a run is already in progress")
        return {"started": True}

    return router


_SHARED: ComputerRuns | None = None


def shared_runs(env: Mapping[str, str] | None = None) -> ComputerRuns | None:
    """The one process-wide ComputerRuns (router and chat tools must share it); None if unset."""
    global _SHARED
    values = os.environ if env is None else env
    if not values.get(TOKEN_ENV):
        return None
    if _SHARED is None:
        learning = values.get("SIRO_COMPUTER_PLAYBOOK", "1") != "0"
        _SHARED = ComputerRuns(
            ComputerBridge(ControlGate()),
            ClaudeVisionDecider(),
            playbook=PlaybookStore(playbook_dir(dict(values))) if learning else None,
            reflector=ClaudeReflector(env=dict(values)) if learning else None,
            recorder=DemoRecorder(demos_dir(dict(values)))
            if values.get("SIRO_COMPUTER_RECORD", "0") == "1"
            else None,
        )
    return _SHARED


def reset_shared_runs() -> None:
    global _SHARED
    _SHARED = None


def router_from_env(env: Mapping[str, str] | None = None) -> APIRouter | None:
    values = os.environ if env is None else env
    runs = shared_runs(values)
    if runs is None:
        return None
    return build_router(values[TOKEN_ENV], runs)
