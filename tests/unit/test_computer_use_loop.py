from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Any

import pytest

from siro.services.computer_use import bridge as bridge_module
from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import Decision, StepRecord
from siro.services.computer_use.http import ComputerRuns
from siro.services.computer_use.loop import DecisionLoop
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import ControlGate, InputAction

RECT = [100, 100, 800, 600]


class FakeDesktop:
    """Windows-shell stand-in: a tiny two-button game that answers observe/input commands."""

    def __init__(
        self, bridge: ComputerBridge, *, title: str = "Cool Game", process: str = "game.exe"
    ) -> None:
        self.bridge, self.title, self.process = bridge, title, process
        self.scene = "menu"
        self.image_size = [1920, 1080]
        self.inputs: list[dict[str, Any]] = []
        self.drop_input = False
        self.after_input: Callable[[], None] | None = None
        self.task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self._serve())

    async def close(self) -> None:
        assert self.task is not None
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)

    def _scene_report(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "process": self.process,
            "rect": RECT,
            "screen": [1920, 1080],
            "fingerprint": self.scene,
            "image_png_b64": "AAAA",
            "image_size": self.image_size,
        }

    async def _serve(self) -> None:
        while True:
            command = await self.bridge.next_command(wait=0.05)
            if command is None:
                continue
            if command["op"] == "observe":
                self.bridge.submit_result(command["id"], True, data=self._scene_report())
                continue
            action = command["payload"]
            self.inputs.append(action)
            if self.drop_input:
                continue
            if (
                action["kind"] == "click"
                and (action["x"], action["y"]) == (300, 300)
                and self.scene == "menu"
            ):
                self.scene = "playing"
            elif (
                action["kind"] == "click"
                and (action["x"], action["y"]) == (500, 400)
                and self.scene == "playing"
            ):
                self.scene = "won"
            self.bridge.submit_result(command["id"], True)
            if self.after_input:
                self.after_input()


class Script:
    """Decider driven by a function of the observation, like a model reading the screen."""

    def __init__(self, policy: Callable[[Observation, Sequence[StepRecord]], Decision]) -> None:
        self.policy, self.calls = policy, 0

    async def decide(
        self, goal: str, history: Sequence[StepRecord], observation: Observation
    ) -> Decision:
        self.calls += 1
        return self.policy(observation, history)


def click(x: int, y: int, expect: str = "scene changes", confidence: float = 0.9) -> Decision:
    return Decision("act", InputAction("click", x=x, y=y), expect, "r", confidence)


def solver(obs: Observation, history: Sequence[StepRecord]) -> Decision:
    if obs.fingerprint == "menu":
        return click(300, 300)
    if obs.fingerprint == "playing":
        return click(500, 400)
    return Decision("done", None, "", "won", 0.95, "banner says YOU WIN")


@pytest.fixture(autouse=True)
def fast_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge_module, "INPUT_TIMEOUT", 0.3)
    monkeypatch.setattr(bridge_module, "OBSERVE_TIMEOUT", 0.5)


async def _run(
    policy: Callable[[Observation, Sequence[StepRecord]], Decision],
    *,
    desktop_kwargs: dict[str, Any] | None = None,
    allowed: frozenset[str] = frozenset({"game.exe"}),
    enabled: bool = True,
    online: bool = True,
    setup: Callable[[FakeDesktop, ComputerBridge], None] | None = None,
    **loop_kwargs: Any,
) -> tuple[Any, FakeDesktop, ComputerBridge, Script]:
    bridge = ComputerBridge(ControlGate(screen=(0, 0, 1920, 1080), enabled=enabled))
    desktop = FakeDesktop(bridge, **(desktop_kwargs or {}))
    if setup:
        setup(desktop, bridge)
    if online:
        desktop.start()
        await asyncio.sleep(0.02)  # let the shell poll once, as the real one does continuously
    script = Script(policy)
    loop = DecisionLoop(bridge, script, allowed=allowed, settle=0, **loop_kwargs)
    try:
        report = await loop.run("win the game")
    finally:
        if online:
            await desktop.close()
    return report, desktop, bridge, script


@pytest.mark.asyncio
async def test_solves_scene_chain_and_confirms_done_twice() -> None:
    report, desktop, _, script = await _run(solver)
    assert report.success and report.reason == "banner says YOU WIN"
    assert [(a["x"], a["y"]) for a in desktop.inputs] == [(300, 300), (500, 400)]
    assert script.calls == 4  # click, click, done, done-confirmed
    assert [r.outcome for r in report.steps if r.action != "(confirm done)"] == ["ok", "ok"]
    assert report.steps[0].screen_changed is True


@pytest.mark.asyncio
async def test_done_flip_flop_does_not_finish() -> None:
    calls = {"n": 0}

    def policy(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        calls["n"] += 1
        if calls["n"] == 1:
            return Decision("done", None, "", "?", 0.9, "looks done")
        return click(300, 300)

    report, desktop, _, _ = await _run(policy, max_steps=3)
    assert not report.success and report.reason in {"step_limit", "stuck_no_visible_change"}
    assert desktop.inputs  # kept working instead of declaring victory


@pytest.mark.asyncio
async def test_stuck_when_screen_never_changes() -> None:
    report, desktop, _, _ = await _run(lambda o, h: click(150, 150))
    assert report.reason == "stuck_no_visible_change"
    assert len(desktop.inputs) == 3


@pytest.mark.asyncio
async def test_click_outside_window_rejected_without_input() -> None:
    report, desktop, _, _ = await _run(lambda o, h: click(1500, 900))
    assert report.reason == "too_many_invalid_decisions"
    assert desktop.inputs == []
    assert all(r.outcome == "invalid:outside_window" for r in report.steps)


@pytest.mark.asyncio
async def test_blocked_window_sends_no_input_and_no_pixels() -> None:
    seen: list[Observation] = []

    def policy(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        seen.append(obs)
        return click(300, 300)

    report, desktop, _, script = await _run(
        policy, desktop_kwargs={"title": "Bank login - Password"}
    )
    assert report.reason == "blocked_title" and desktop.inputs == [] and script.calls == 0


@pytest.mark.asyncio
async def test_window_not_on_allowlist() -> None:
    report, desktop, _, script = await _run(solver, desktop_kwargs={"process": "chrome.exe"})
    assert report.reason == "window_not_allowed" and script.calls == 0 and desktop.inputs == []


@pytest.mark.asyncio
async def test_empty_allowlist_refuses_everything() -> None:
    report, _, _, script = await _run(solver, allowed=frozenset())
    assert report.reason == "no_allowed_processes" and script.calls == 0


@pytest.mark.asyncio
async def test_default_off_gate_denies_first_action() -> None:
    report, desktop, _, _ = await _run(solver, enabled=False)
    assert report.reason == "denied:control_disabled" and desktop.inputs == []


@pytest.mark.asyncio
async def test_executor_offline() -> None:
    report, _, _, _ = await _run(solver, online=False)
    assert report.reason == "executor_offline"


@pytest.mark.asyncio
async def test_emergency_stop_mid_run_halts_further_input() -> None:
    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.after_input = bridge.stop

    report, desktop, bridge, _ = await _run(solver, setup=setup)
    assert report.reason == "emergency_stop"
    assert len(desktop.inputs) == 1 and bridge.gate.tripped


@pytest.mark.asyncio
async def test_lost_input_is_unknown_and_never_resent() -> None:
    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.drop_input = True

    report, desktop, _, _ = await _run(solver, setup=setup)
    assert report.reason == "outcome_unknown" and not report.success
    assert len(desktop.inputs) == 1
    assert report.steps[-1].outcome == "unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision", "reason"),
    [
        (Decision("ask", None, "", "login needed", 0.9), "needs_owner"),
        (Decision("stuck", None, "", "no idea", 0.9), "decider_stuck"),
        (click(300, 300, confidence=0.3), "low_confidence"),
        (Decision("done", None, "", "x", 0.9, "  "), "done_without_evidence"),
    ],
)
async def test_decider_stop_conditions(decision: Decision, reason: str) -> None:
    report, desktop, _, _ = await _run(lambda o, h: decision)
    assert report.reason == reason and desktop.inputs == []


@pytest.mark.asyncio
async def test_decider_failure_is_failed_not_success() -> None:
    from siro.services.computer_use.decision import DecisionError

    class Broken:
        async def decide(self, *args: Any) -> Decision:
            raise DecisionError("not_json")

    bridge = ComputerBridge(ControlGate(enabled=True))
    desktop = FakeDesktop(bridge)
    desktop.start()
    await asyncio.sleep(0.02)
    report = await DecisionLoop(bridge, Broken(), allowed=frozenset({"game.exe"}), settle=0).run(
        "g"
    )
    await desktop.close()
    assert report.state == "failed" and report.reason == "decider_error:not_json"


@pytest.mark.asyncio
async def test_time_and_step_limits_stop() -> None:
    report, desktop, _, _ = await _run(solver, max_seconds=-1.0)
    assert report.reason == "time_limit" and desktop.inputs == []
    report, _, _, _ = await _run(solver, max_steps=1)
    assert report.reason == "step_limit" and not report.success


@pytest.mark.asyncio
async def test_decision_coordinates_are_mapped_from_screenshot_to_screen() -> None:
    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.image_size = [960, 540]  # model sees half-size pixels

    def policy(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        if obs.fingerprint == "menu":
            return click(150, 150)  # == (300, 300) on screen
        if obs.fingerprint == "playing":
            return click(250, 200)  # == (500, 400)
        return Decision("done", None, "", "won", 0.95, "banner")

    report, desktop, _, _ = await _run(policy, setup=setup)
    assert report.success
    assert [(a["x"], a["y"]) for a in desktop.inputs] == [(300, 300), (500, 400)]


@pytest.mark.asyncio
async def test_wait_decisions_pause_then_continue_but_not_forever() -> None:
    calls = {"n": 0}

    def policy(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        calls["n"] += 1
        if calls["n"] <= 2:
            return Decision(
                "wait", None, "fade ends", "black screen", 0.2
            )  # low confidence is fine
        return solver(obs, history)

    report, desktop, _, _ = await _run(policy, wait=0)
    assert report.success and len(desktop.inputs) == 2
    assert [r.action for r in report.steps][:2] == ["(wait)", "(wait)"]

    report, desktop, _, _ = await _run(
        lambda o, h: Decision("wait", None, "", "still black", 0.9), wait=0
    )
    assert report.reason == "stuck_waiting" and desktop.inputs == []


@pytest.mark.asyncio
async def test_live_steps_visible_while_running() -> None:
    bridge = ComputerBridge(ControlGate(enabled=True))
    desktop = FakeDesktop(bridge)
    desktop.start()
    await asyncio.sleep(0.02)
    gate_open = asyncio.Event()

    class Slow:
        async def decide(
            self, goal: str, history: Sequence[StepRecord], obs: Observation
        ) -> Decision:
            if history:
                await gate_open.wait()
            return click(300, 300)

    runs = ComputerRuns(bridge, Slow())
    runs._loop = DecisionLoop(bridge, Slow(), allowed=frozenset({"game.exe"}), settle=0)
    task = asyncio.create_task(runs._loop.run("g"))
    await asyncio.sleep(0.3)
    assert runs._loop.live and runs._loop.live[0].action.startswith("click")
    gate_open.set()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await desktop.close()


@pytest.mark.asyncio
async def test_run_is_recorded_as_local_training_data(tmp_path: Any) -> None:
    import json

    from siro.services.computer_use.demos import DemoRecorder

    recorder = DemoRecorder(tmp_path)
    report, _, _, _ = await _run(solver, recorder=recorder)
    assert report.success
    (run,) = recorder.runs()
    steps = [json.loads(x) for x in (run / "steps.jsonl").read_text().splitlines()]
    acted = [s for s in steps if s["action"]]
    assert [s["action"]["kind"] for s in acted] == ["click", "click"]
    assert all(s["changed"] is True for s in acted)  # the effect of each action was filled in
    assert (run / "meta.json").exists() and json.loads((run / "meta.json").read_text())[
        "state"
    ] == "done"
