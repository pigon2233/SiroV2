from __future__ import annotations

import asyncio
import base64
import io
from collections.abc import Callable, Sequence
from typing import Any

import pytest
from PIL import Image

from siro.services.computer_use import bridge as bridge_module
from siro.services.computer_use import loop as loop_module
from siro.services.computer_use.bridge import BridgeResult, ComputerBridge
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
        self.focus_requests: list[str] = []
        self.focus_brings = True
        self.inputs: list[dict[str, Any]] = []
        self.drop_input = False
        self.after_input: Callable[[], None] | None = None
        self.on_observe: Callable[[], None] | None = None
        self.image_for_scene: Callable[[str], str] | None = None
        self.window_id = "101"
        self.pid = 1001
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
            "image_png_b64": self.image_for_scene(self.scene) if self.image_for_scene else "AAAA",
            "image_size": self.image_size,
            "window_id": self.window_id,
            "pid": self.pid,
        }

    async def _serve(self) -> None:
        while True:
            command = await self.bridge.next_command(wait=0.05)
            if command is None:
                continue
            if command["op"] == "observe":
                if self.on_observe:
                    self.on_observe()
                self.bridge.submit_result(command["id"], True, data=self._scene_report())
                continue
            if command["op"] == "focus":
                self.focus_requests.append(command["payload"]["process"])
                if self.focus_brings:
                    self.process = command["payload"]["process"]
                self.bridge.submit_result(command["id"], True)
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
    loop_kwargs.setdefault("focus", False)  # focusing is opt-in per test
    loop_kwargs.setdefault("autonomous", False)  # keep default stop-to-ask unless a test opts in
    loop_kwargs.setdefault("settle", 0)
    loop_kwargs.setdefault("wait", 0)
    loop = DecisionLoop(bridge, script, allowed=allowed, **loop_kwargs)
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


def _scene_png(scene: str) -> str:
    image = Image.new("RGB", (2, 2), "white" if scene == "menu" else "black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@pytest.mark.asyncio
async def test_screen_guard_waits_until_original_scene_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_SCREEN_GUARD", "1")
    observations = [0]

    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.image_size = [2, 2]
        desktop.image_for_scene = _scene_png

        def on_observe() -> None:
            observations[0] += 1
            if observations[0] == 3:
                desktop.scene = "menu"

        desktop.on_observe = on_observe

    holder: list[FakeDesktop] = []

    def setup_and_remember(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        setup(desktop, bridge)
        holder.append(desktop)

    def decide(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        holder[0].scene = "transition"  # the old screenshot is no longer displayed
        return Decision("act", InputAction("key", key="z"), confidence=0.9)

    report, desktop, _, _ = await _run(decide, setup=setup_and_remember, max_steps=1)
    assert report.reason == "step_limit"
    assert len(desktop.inputs) == 1
    assert observations[0] == 3


@pytest.mark.asyncio
async def test_screen_guard_stops_without_action_if_scene_never_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_SCREEN_GUARD", "1")
    monkeypatch.setattr(loop_module, "SCREEN_MATCH_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(loop_module, "SCREEN_MATCH_POLL_SECONDS", 0.005)
    holder: list[FakeDesktop] = []

    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.image_size = [2, 2]
        desktop.image_for_scene = _scene_png
        holder.append(desktop)

    def decide(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        holder[0].scene = "transition"
        return Decision("act", InputAction("key", key="z"), confidence=0.9)

    report, desktop, _, _ = await _run(decide, setup=setup, max_steps=1)
    assert report.reason == "screen_not_restored"
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_screen_guard_rejects_window_switch_with_same_pixels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_SCREEN_GUARD", "1")
    holder: list[FakeDesktop] = []

    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.image_size = [2, 2]
        desktop.image_for_scene = _scene_png
        holder.append(desktop)

    def decide(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        holder[0].window_id = "202"
        return Decision("act", InputAction("key", key="z"), confidence=0.9)

    report, desktop, _, _ = await _run(decide, setup=setup, max_steps=1)
    assert report.reason == "window_changed"
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_screen_guard_stop_and_reenable_does_not_revive_waiting_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_SCREEN_GUARD", "1")
    count = [0]

    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.image_size = [2, 2]
        desktop.image_for_scene = _scene_png

        def on_observe() -> None:
            count[0] += 1
            if count[0] == 2:
                bridge.stop()
                bridge.gate.enable()

        desktop.on_observe = on_observe

    report, desktop, _, _ = await _run(
        lambda o, h: Decision("act", InputAction("key", key="z"), confidence=0.9),
        setup=setup,
        max_steps=1,
    )
    assert report.reason == "emergency_stop"
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_screen_guard_reports_wait_and_stops_on_disable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_SCREEN_GUARD", "1")
    monkeypatch.setattr(loop_module, "SCREEN_MATCH_POLL_SECONDS", 0.01)
    bridge = ComputerBridge(ControlGate(screen=(0, 0, 1920, 1080), enabled=True))
    desktop = FakeDesktop(bridge)
    desktop.image_size = [2, 2]
    desktop.image_for_scene = _scene_png
    observed = asyncio.Event()
    count = [0]

    def on_observe() -> None:
        count[0] += 1
        if count[0] == 2:
            observed.set()

    desktop.on_observe = on_observe

    def decide(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        desktop.scene = "transition"
        return Decision("act", InputAction("key", key="z"), confidence=0.9)

    desktop.start()
    await asyncio.sleep(0.02)
    loop = DecisionLoop(
        bridge, Script(decide), allowed=frozenset({"game.exe"}), settle=0, focus=False
    )
    task = asyncio.create_task(loop.run("play"))
    try:
        await asyncio.wait_for(observed.wait(), timeout=1)
        assert loop.phase == "waiting_for_matching_screen"
        runs = ComputerRuns(bridge, Script(solver))
        runs._loop = loop
        assert runs.status()["phase"] == "waiting_for_matching_screen"
        bridge.gate.disable()
        report = await asyncio.wait_for(task, timeout=1)
    finally:
        await desktop.close()
    assert report.reason == "control_disabled"
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_screen_guard_unknown_input_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_SCREEN_GUARD", "1")

    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.image_size = [2, 2]
        desktop.image_for_scene = _scene_png
        desktop.drop_input = True

    report, desktop, _, _ = await _run(
        lambda o, h: Decision("act", InputAction("key", key="z"), confidence=0.9),
        setup=setup,
    )
    assert report.reason == "outcome_unknown"
    assert len(desktop.inputs) == 1


@pytest.mark.asyncio
async def test_screen_guard_missing_or_invalid_pixels_or_identity_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_SCREEN_GUARD", "1")
    report, desktop, _, _ = await _run(lambda o, h: click(300, 300), max_steps=1)
    assert report.reason == "screen_guard_unavailable" and desktop.inputs == []

    def missing_identity(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.image_size = [2, 2]
        desktop.image_for_scene = _scene_png
        desktop.window_id = ""

    report, desktop, _, _ = await _run(
        lambda o, h: Decision("act", InputAction("key", key="z"), confidence=0.9),
        setup=missing_identity,
        max_steps=1,
    )
    assert report.reason == "screen_guard_unavailable" and desktop.inputs == []


@pytest.mark.asyncio
async def test_opt_in_long_run_continues_past_40_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_MAX_STEPS", "55")
    monkeypatch.setenv("SIRO_COMPUTER_MAX_SECONDS", "900")
    now = [0.0]

    def clock() -> float:
        return now[0]

    gate = ControlGate(screen=(0, 0, 1920, 1080), enabled=True, clock=clock)
    bridge = ComputerBridge(gate, clock=clock)
    desktop = FakeDesktop(bridge)

    def progress() -> None:
        now[0] += 1.0
        desktop.scene = f"scene-{len(desktop.inputs)}"

    desktop.after_input = progress
    desktop.start()
    await asyncio.sleep(0.02)
    loop = DecisionLoop(
        bridge,
        Script(lambda o, h: click(150, 150)),
        allowed=frozenset({"game.exe"}),
        clock=clock,
        settle=0,
        focus=False,
    )
    try:
        report = await loop.run("play")
    finally:
        await desktop.close()
    assert report.reason == "step_limit"
    assert len(desktop.inputs) == 55
    assert loop.limits == {"max_steps": 55, "max_seconds": 900, "autonomous": False}


@pytest.mark.parametrize(
    "name,value",
    [
        ("SIRO_COMPUTER_MAX_STEPS", "0"),
        ("SIRO_COMPUTER_MAX_STEPS", "1201"),
        ("SIRO_COMPUTER_MAX_STEPS", "oops"),
        ("SIRO_COMPUTER_MAX_SECONDS", "7201"),
        ("SIRO_COMPUTER_MAX_SECONDS", "nan"),
    ],
)
def test_invalid_long_run_configuration_is_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    from siro.services.computer_use.loop import ComputerLimitError

    monkeypatch.setenv(name, value)
    with pytest.raises(ComputerLimitError):
        DecisionLoop(ComputerBridge(ControlGate()), Script(solver))


def test_unconfigured_limits_keep_existing_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIRO_COMPUTER_MAX_STEPS", raising=False)
    monkeypatch.delenv("SIRO_COMPUTER_MAX_SECONDS", raising=False)
    monkeypatch.delenv("SIRO_COMPUTER_AUTONOMOUS", raising=False)
    loop = DecisionLoop(ComputerBridge(ControlGate()), Script(solver))
    assert loop.limits == {"max_steps": 40, "max_seconds": 600, "autonomous": False}


@pytest.mark.asyncio
async def test_long_run_still_honours_emergency_stop_after_40_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_MAX_STEPS", "100")
    now = [0.0]

    def clock() -> float:
        return now[0]

    gate = ControlGate(screen=(0, 0, 1920, 1080), enabled=True, clock=clock)
    bridge = ComputerBridge(gate, clock=clock)
    desktop = FakeDesktop(bridge)

    def progress() -> None:
        now[0] += 1
        desktop.scene = f"scene-{len(desktop.inputs)}"
        if len(desktop.inputs) == 55:
            bridge.stop()

    desktop.after_input = progress
    desktop.start()
    await asyncio.sleep(0.02)
    loop = DecisionLoop(
        bridge,
        Script(lambda o, h: click(150, 150)),
        allowed=frozenset({"game.exe"}),
        clock=clock,
        settle=0,
        focus=False,
    )
    try:
        report = await loop.run("play")
    finally:
        await desktop.close()
    assert report.reason == "emergency_stop"
    assert len(desktop.inputs) == 55
    assert gate.tripped


@pytest.mark.asyncio
async def test_long_run_stops_when_input_outcome_unknown_after_40_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_MAX_STEPS", "100")
    now = [0.0]

    def clock() -> float:
        return now[0]

    bridge = ComputerBridge(
        ControlGate(screen=(0, 0, 1920, 1080), enabled=True, clock=clock), clock=clock
    )
    desktop = FakeDesktop(bridge)

    def progress() -> None:
        now[0] += 1
        desktop.scene = f"scene-{len(desktop.inputs)}"
        if len(desktop.inputs) == 44:
            desktop.drop_input = True

    desktop.after_input = progress
    desktop.start()
    await asyncio.sleep(0.02)
    loop = DecisionLoop(
        bridge,
        Script(lambda o, h: click(150, 150)),
        allowed=frozenset({"game.exe"}),
        clock=clock,
        settle=0,
        focus=False,
    )
    try:
        report = await loop.run("play")
    finally:
        await desktop.close()
    assert report.reason == "outcome_unknown"
    assert len(desktop.inputs) == 45
    assert report.steps[-1].outcome == "unknown"


@pytest.mark.asyncio
async def test_configured_30_minute_run_is_still_time_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_MAX_STEPS", "1000")
    monkeypatch.setenv("SIRO_COMPUTER_MAX_SECONDS", "1800")
    now = [0.0]

    def clock() -> float:
        return now[0]

    bridge = ComputerBridge(
        ControlGate(screen=(0, 0, 1920, 1080), enabled=True, clock=clock), clock=clock
    )
    desktop = FakeDesktop(bridge)

    def progress() -> None:
        now[0] += 2
        desktop.scene = f"scene-{len(desktop.inputs)}"

    desktop.after_input = progress
    desktop.start()
    await asyncio.sleep(0.02)
    loop = DecisionLoop(
        bridge,
        Script(lambda o, h: click(150, 150)),
        allowed=frozenset({"game.exe"}),
        clock=clock,
        settle=0,
        focus=False,
    )
    try:
        report = await loop.run("play")
    finally:
        await desktop.close()
    assert report.reason == "time_limit"
    assert len(desktop.inputs) == 900
    assert now[0] == 1800


@pytest.mark.asyncio
async def test_invalid_run_limits_are_visible_in_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_MAX_STEPS", "lots")
    runs = ComputerRuns(ComputerBridge(ControlGate(enabled=True)), Script(solver))
    assert runs.start("play")
    assert runs._task is not None
    await runs._task
    report = runs.status()["report"]
    assert report["state"] == "failed"
    assert report["reason"] == "invalid_run_limits"
    assert report["detail"] == "invalid SIRO_COMPUTER_MAX_STEPS"


@pytest.mark.asyncio
async def test_effective_run_limits_are_visible_in_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_COMPUTER_MAX_STEPS", "1000")
    monkeypatch.setenv("SIRO_COMPUTER_MAX_SECONDS", "1800")
    monkeypatch.delenv("SIRO_COMPUTER_ALLOWED_PROCESSES", raising=False)
    runs = ComputerRuns(ComputerBridge(ControlGate(enabled=True)), Script(solver))
    assert runs.start("play")
    assert runs._task is not None
    await runs._task
    assert runs.status()["limits"] == {
        "max_steps": 1000,
        "max_seconds": 1800,
        "autonomous": False,
        "endless": False,
        "session_segments": 1,
    }


@pytest.mark.asyncio
async def test_separate_rate_limit_events_do_not_accumulate_forever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(loop_module, "RATE_WAIT_SECONDS", 0)
    now = [0.0]

    def clock() -> float:
        return now[0]

    bridge = ComputerBridge(
        ControlGate(screen=(0, 0, 1920, 1080), enabled=True, clock=clock), clock=clock
    )
    desktop = FakeDesktop(bridge)

    def progress() -> None:
        now[0] += 2
        desktop.scene = f"scene-{len(desktop.inputs)}"

    desktop.after_input = progress
    original_act = bridge.act
    attempts = [0]

    async def intermittently_limited(action: InputAction) -> BridgeResult:
        attempts[0] += 1
        if attempts[0] <= 12 and attempts[0] % 2:
            return BridgeResult(False, "rate_limited")
        return await original_act(action)

    bridge.act = intermittently_limited  # type: ignore[method-assign]
    desktop.start()
    await asyncio.sleep(0.02)
    loop = DecisionLoop(
        bridge,
        Script(lambda o, h: click(150, 150)),
        allowed=frozenset({"game.exe"}),
        clock=clock,
        max_steps=14,
        settle=0,
        focus=False,
    )
    try:
        report = await loop.run("play")
    finally:
        await desktop.close()
    assert report.reason == "step_limit"
    assert len(desktop.inputs) == 8


@pytest.mark.asyncio
async def test_continuous_rate_limit_still_stops_without_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(loop_module, "RATE_WAIT_SECONDS", 0)
    bridge = ComputerBridge(ControlGate(screen=(0, 0, 1920, 1080), enabled=True))
    desktop = FakeDesktop(bridge)
    attempts = [0]

    async def limited(action: InputAction) -> BridgeResult:
        attempts[0] += 1
        return BridgeResult(False, "rate_limited")

    bridge.act = limited  # type: ignore[method-assign]
    desktop.start()
    await asyncio.sleep(0.02)
    loop = DecisionLoop(
        bridge,
        Script(lambda o, h: click(150, 150)),
        allowed=frozenset({"game.exe"}),
        settle=0,
        focus=False,
    )
    try:
        report = await loop.run("play")
    finally:
        await desktop.close()
    assert report.reason == "denied:rate_limited"
    assert attempts[0] == 6
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_stop_then_reenable_cannot_revive_pending_model_action() -> None:
    gate = ControlGate(screen=(0, 0, 1920, 1080), enabled=True)
    bridge = ComputerBridge(gate)
    desktop = FakeDesktop(bridge)
    desktop.start()
    await asyncio.sleep(0.02)

    class LateDecision:
        async def decide(
            self, goal: str, history: Sequence[StepRecord], obs: Observation
        ) -> Decision:
            bridge.stop()
            gate.enable()
            return click(300, 300)

    loop = DecisionLoop(
        bridge, LateDecision(), allowed=frozenset({"game.exe"}), max_steps=1, settle=0, focus=False
    )
    try:
        report = await loop.run("play")
    finally:
        await desktop.close()
    assert report.reason == "emergency_stop"
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_decision_that_finishes_after_deadline_cannot_send_input() -> None:
    now = [0.0]
    bridge = ComputerBridge(
        ControlGate(screen=(0, 0, 1920, 1080), enabled=True), clock=lambda: now[0]
    )
    desktop = FakeDesktop(bridge)
    desktop.start()
    await asyncio.sleep(0.02)

    class SlowDecision:
        async def decide(
            self, goal: str, history: Sequence[StepRecord], obs: Observation
        ) -> Decision:
            now[0] = 2.0
            return click(300, 300)

    loop = DecisionLoop(
        bridge,
        SlowDecision(),
        allowed=frozenset({"game.exe"}),
        max_seconds=1,
        clock=lambda: now[0],
        settle=0,
        focus=False,
    )
    try:
        report = await loop.run("play")
    finally:
        await desktop.close()
    assert report.reason == "time_limit"
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_deadline_cancels_hung_decision() -> None:
    bridge = ComputerBridge(ControlGate(screen=(0, 0, 1920, 1080), enabled=True))
    desktop = FakeDesktop(bridge)
    desktop.start()
    await asyncio.sleep(0.02)
    cancelled = asyncio.Event()

    class HungDecision:
        async def decide(
            self, goal: str, history: Sequence[StepRecord], obs: Observation
        ) -> Decision:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
            raise AssertionError("unreachable")

    loop = DecisionLoop(
        bridge,
        HungDecision(),
        allowed=frozenset({"game.exe"}),
        max_seconds=0.05,
        settle=0,
        focus=False,
    )
    try:
        report = await asyncio.wait_for(loop.run("play"), timeout=0.5)
    finally:
        await desktop.close()
    assert report.reason == "time_limit"
    assert cancelled.is_set()
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_decider_timeout_is_reported_as_failure_not_run_deadline() -> None:
    bridge = ComputerBridge(ControlGate(screen=(0, 0, 1920, 1080), enabled=True))
    desktop = FakeDesktop(bridge)
    desktop.start()
    await asyncio.sleep(0.02)

    class TimedOutDecision:
        async def decide(
            self, goal: str, history: Sequence[StepRecord], obs: Observation
        ) -> Decision:
            raise TimeoutError("provider timeout")

    loop = DecisionLoop(
        bridge, TimedOutDecision(), allowed=frozenset({"game.exe"}), settle=0, focus=False
    )
    try:
        report = await loop.run("play")
    finally:
        await desktop.close()
    assert report.state == "failed"
    assert report.reason == "decider_error:provider timeout"
    assert desktop.inputs == []


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
async def test_wait_interrupts_completion_confirmation() -> None:
    choices = iter(
        [
            Decision("done", confidence=0.9, evidence="banner seen"),
            Decision("wait", confidence=0.9),
            Decision("done", confidence=0.9, evidence="banner seen again"),
        ]
    )
    report, desktop, _, _ = await _run(lambda o, h: next(choices), max_steps=3, wait=0)
    assert report.state == "stopped"
    assert report.reason == "step_limit"
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_wait_history_reports_unchanged_frame_to_model() -> None:
    def policy(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        if history and history[-1].screen_changed is False:
            return Decision("ask", reason="The scene did not change; need guidance", confidence=0.9)
        return Decision("wait", confidence=0.9, seen="unchanged scene")

    report, desktop, _, _ = await _run(policy, wait=0)
    assert report.reason == "needs_owner"
    assert report.steps[0].action == "(wait)"
    assert report.steps[0].screen_changed is False
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_wait_history_reports_changed_frame_to_model() -> None:
    count = [0]

    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        def on_observe() -> None:
            count[0] += 1
            if count[0] == 2:
                desktop.scene = "transition finished"

        desktop.on_observe = on_observe

    def policy(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        if history and history[-1].screen_changed is True:
            return Decision("ask", reason="Transition changed", confidence=0.9)
        return Decision("wait", confidence=0.9, seen="transition")

    report, desktop, _, _ = await _run(policy, setup=setup, wait=0)
    assert report.reason == "needs_owner"
    assert report.steps[0].screen_changed is True
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_wait_history_with_no_fingerprint_remains_unknown() -> None:
    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.scene = ""

    report, desktop, _, _ = await _run(
        lambda o, h: Decision("wait", confidence=0.9), setup=setup, wait=0
    )
    assert report.reason == "stuck_waiting"
    assert all(step.screen_changed is None for step in report.steps)
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_repeated_unchanged_waits_do_not_count_as_failed_actions() -> None:
    report, desktop, _, _ = await _run(lambda o, h: Decision("wait", confidence=0.9), wait=0)
    assert report.reason == "stuck_waiting"
    assert len(report.steps) == 7
    assert [step.screen_changed for step in report.steps] == [False] * 6 + [None]
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_wait_history_window_switch_remains_unknown() -> None:
    count = [0]

    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        def on_observe() -> None:
            count[0] += 1
            if count[0] == 2:
                desktop.window_id = "202"

        desktop.on_observe = on_observe

    def policy(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        if history:
            return Decision("ask", reason="window changed", confidence=0.9)
        return Decision("wait", confidence=0.9)

    report, desktop, _, _ = await _run(policy, setup=setup, wait=0)
    assert report.reason == "needs_owner"
    assert report.steps[0].screen_changed is None
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_completion_can_be_confirmed_after_wait() -> None:
    choices = iter(
        [
            Decision("done", confidence=0.9, evidence="banner seen"),
            Decision("wait", confidence=0.9),
            Decision("done", confidence=0.9, evidence="banner reappears"),
            Decision("done", confidence=0.9, evidence="banner remains"),
        ]
    )
    report, desktop, _, _ = await _run(lambda o, h: next(choices), max_steps=4, wait=0)
    assert report.success
    assert report.reason == "banner remains"
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_owner_question_is_available_in_status() -> None:
    question = "Should I choose Continue or New Game?"
    report, desktop, bridge, _ = await _run(
        lambda o, h: Decision("ask", reason=question, confidence=0.9)
    )
    runs = ComputerRuns(bridge, Script(solver))
    runs.report = report
    status = runs.status()
    assert status["report"]["reason"] == "needs_owner"
    assert status["report"]["detail"] == question
    assert desktop.inputs == []


@pytest.mark.asyncio
async def test_stuck_when_screen_never_changes() -> None:
    report, desktop, _, _ = await _run(lambda o, h: click(150, 150))
    assert report.reason == "stuck_no_visible_change"
    assert len(desktop.inputs) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["missing_before", "missing_after", "different_window"])
async def test_post_action_comparison_is_unknown_when_unreliable(case: str) -> None:
    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        if case == "missing_before":
            desktop.scene = ""

        def after_input() -> None:
            if case == "missing_before":
                desktop.scene = "new scene"
            elif case == "missing_after":
                desktop.scene = ""
            else:
                desktop.window_id = "202"

        desktop.after_input = after_input

    def policy(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        if history:
            return Decision("ask", reason="check result", confidence=0.9)
        return click(150, 150)

    report, desktop, _, _ = await _run(policy, setup=setup)
    assert report.reason == "needs_owner"
    assert len(desktop.inputs) == 1
    assert report.steps[0].screen_changed is None


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
async def test_autonomous_ask_waits_then_keeps_playing() -> None:
    calls = {"n": 0}

    def policy(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        calls["n"] += 1
        if calls["n"] == 1:
            return Decision("ask", None, "", "unsure which button", 0.9)
        return solver(obs, history)

    report, desktop, _, script = await _run(policy, autonomous=True)
    assert report.state == "done" and report.success
    assert any(s.action == "(wait)" for s in report.steps)
    assert len(desktop.inputs) >= 2
    assert script.calls >= 3


@pytest.mark.asyncio
async def test_autonomous_low_confidence_act_is_still_executed() -> None:
    def policy(obs: Observation, history: Sequence[StepRecord]) -> Decision:
        if obs.fingerprint == "menu":
            return click(300, 300, confidence=0.2)
        if obs.fingerprint == "playing":
            return click(500, 400, confidence=0.2)
        return Decision("done", None, "", "won", 0.95, "banner says YOU WIN")

    report, desktop, _, _ = await _run(policy, autonomous=True)
    assert report.success
    assert len(desktop.inputs) == 2
    assert report.reason != "low_confidence"


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


@pytest.mark.asyncio
async def test_chat_started_run_brings_the_allowed_game_forward_once() -> None:
    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.process = "chat.exe"  # the chat/monitor window is in front when the run starts

    report, desktop, _, _ = await _run(solver, setup=setup, focus=True)
    assert desktop.focus_requests == ["game.exe"] and report.success


@pytest.mark.asyncio
async def test_focus_is_off_unwanted_ambiguous_or_ineffective() -> None:
    def setup(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.process = "chat.exe"

    report, desktop, _, _ = await _run(solver, setup=setup, focus=False)
    assert desktop.focus_requests == [] and report.reason == "window_not_allowed"

    def stubborn(desktop: FakeDesktop, bridge: ComputerBridge) -> None:
        desktop.process = "chat.exe"
        desktop.focus_brings = False

    report, desktop, _, _ = await _run(solver, setup=stubborn, focus=True)
    assert len(desktop.focus_requests) == 1 and report.reason == "window_not_allowed"

    report, desktop, _, _ = await _run(
        solver, setup=setup, focus=True, allowed=frozenset({"a.exe", "b.exe"})
    )
    assert desktop.focus_requests == [] and report.reason == "window_not_allowed"  # ambiguous


@pytest.mark.asyncio
async def test_blocked_foreground_window_is_never_replaced() -> None:
    report, desktop, _, _ = await _run(
        solver, desktop_kwargs={"title": "Bank login - Password"}, focus=True
    )
    assert report.reason == "blocked_title" and desktop.focus_requests == []


def test_goal_names_program_even_next_to_chinese_but_not_inside_words() -> None:
    from siro.services.computer_use.intent import names_program as _names

    assert _names("undertale", "幫我玩undertale")
    assert _names("undertale", "play undertale now")
    assert not _names("a", "win the game") and not _names("game", "gamer lounge")
