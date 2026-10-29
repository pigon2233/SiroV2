from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

import pytest

from siro.services.computer_use import bridge as bridge_module
from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import (
    ClaudeVisionDecider,
    CloudScreenNotAllowed,
    DecisionError,
    parse_decision,
)
from siro.services.computer_use.perception import (
    Observation,
    allowed_processes,
    image_to_screen,
    is_fresh,
    rect_in_image,
    sanitize,
)
from siro.services.computer_use.safety import ControlGate, InputAction

RAW: dict[str, Any] = {
    "title": "Cool Game",
    "process": "Game.EXE",
    "rect": [0, 0, 800, 600],
    "screen": [1920, 1080],
    "fingerprint": "abc",
    "image_png_b64": "AAAA",
    "image_size": [960, 540],
}


def test_sanitize_normalizes_and_keeps_pixels() -> None:
    obs = sanitize(RAW, seq=1, now=10.0)
    assert obs.process == "game.exe" and obs.image_png_b64 == "AAAA" and obs.blocked_reason is None
    assert obs.window_rect == (0, 0, 800, 600)


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"process": "KeePassXC.exe"}, "blocked_process"),
        ({"title": "Enter your 密碼"}, "blocked_title"),
        ({"title": "Chase Bank - Sign in"}, "blocked_title"),
        ({"process": ""}, "unknown_window"),
        ({"screen": [0, 0]}, "bad_screen_report"),
        ({"focus_is_secret": True}, "secret_field_focused"),
    ],
)
def test_blocked_observation_drops_pixels(override: dict[str, Any], reason: str) -> None:
    obs = sanitize({**RAW, **override}, seq=1, now=0.0)
    assert obs.blocked_reason == reason and obs.image_png_b64 is None


def test_image_without_size_is_dropped_and_points_map_to_screen() -> None:
    assert sanitize({**RAW, "image_size": None}, seq=1, now=0.0).image_png_b64 is None
    obs = sanitize(RAW, seq=1, now=0.0)
    assert image_to_screen(obs, 100, 50) == (200, 100)
    assert rect_in_image(obs) == (0, 0, 400, 300)


def test_cropped_window_screenshot_maps_back_to_screen() -> None:
    # Only the window (screen 400,200 800x600) was captured, sent at half size (400x300).
    raw = {
        **RAW,
        "rect": [400, 200, 800, 600],
        "image_rect": [400, 200, 800, 600],
        "image_size": [400, 300],
    }
    obs = sanitize(raw, seq=1, now=0.0)
    assert obs.image_rect == (400, 200, 800, 600)
    assert image_to_screen(obs, 0, 0) == (400, 200)
    assert image_to_screen(obs, 200, 150) == (800, 500)
    assert rect_in_image(obs) == (0, 0, 400, 300)
    blocked = sanitize({**raw, "process": "keepass.exe"}, seq=1, now=0.0)
    assert blocked.image_rect is None


def test_title_secret_scrubbed_and_bad_rect_ignored() -> None:
    obs = sanitize({**RAW, "title": "key sk-" + "a" * 24, "rect": [0, 0, -1, 5]}, seq=1, now=0.0)
    assert "sk-" not in obs.window_title and obs.window_rect is None


def test_freshness_and_allowlist_env() -> None:
    obs = sanitize(RAW, seq=1, now=10.0)
    assert is_fresh(obs, 11.0) and not is_fresh(obs, 14.0) and not is_fresh(obs, 9.0)
    assert allowed_processes({"SIRO_COMPUTER_ALLOWED_PROCESSES": " A.exe, b.exe ,"}) == {
        "a.exe",
        "b.exe",
    }
    assert allowed_processes({}) == frozenset()


GOOD = '{"kind":"act","action":{"kind":"click","x":5,"y":6},"expect":"menu opens","confidence":0.8}'


def test_parse_decision_accepts_and_rejects() -> None:
    decision = parse_decision("sure!\n" + GOOD)
    assert decision.action == InputAction("click", x=5, y=6) and decision.confidence == 0.8
    done = parse_decision('{"kind":"done","confidence":1,"evidence":"WIN banner"}')
    assert done.kind == "done" and done.action is None
    for bad in [
        "no json",
        '{"kind":"dance","confidence":1}',
        '{"kind":"act","confidence":1}',
        '{"kind":"act","action":{"kind":"shell"},"confidence":1}',
        '{"kind":"act","action":{"kind":"click","x":1,"y":1},"confidence":2}',
        '{"kind":"act","action":{"kind":"key"},"confidence":0.9}',
        '{"kind":"act","action":{"kind":"click","x":1},"confidence":0.9}',
        '{"kind":"act","action":{"kind":"type","text":""},"confidence":0.9}',
        '{"kind":"act","action":{"kind":"click","x":1,"y":1}}',
    ]:
        with pytest.raises(DecisionError):
            parse_decision(bad)


def _obs(image: str | None = base64.b64encode(b"png").decode()) -> Observation:
    return sanitize({**RAW, "image_png_b64": image}, seq=1, now=0.0)


@pytest.mark.asyncio
async def test_vision_decider_requires_owner_opt_in() -> None:
    called: list[Any] = []

    async def run(*args: Any, **kwargs: Any) -> dict[str, object]:
        called.append(args)
        return {}

    decider = ClaudeVisionDecider(binary=Path("claude"), run=run, env={})
    with pytest.raises(CloudScreenNotAllowed):
        await decider.decide("g", [], _obs())
    assert called == []


@pytest.mark.asyncio
async def test_vision_decider_runs_claude_with_read_only_screenshot() -> None:
    captured: dict[str, Any] = {}

    async def run(argv: tuple[str, ...], *, cwd: Path, **kwargs: Any) -> dict[str, object]:
        captured.update(
            argv=argv, shot=(cwd / "screen.png").read_bytes(), env=kwargs["environment"]
        )
        return {"returncode": 0, "stdout": json.dumps({"result": GOOD, "is_error": False})}

    decider = ClaudeVisionDecider(
        binary=Path("claude"), run=run, env={"SIRO_COMPUTER_CLOUD_SCREEN": "1"}, model="m"
    )
    decision = await decider.decide("win", [], _obs())
    assert decision.kind == "act" and captured["shot"] == b"png"
    argv = captured["argv"]
    assert argv[argv.index("--tools") + 1] == "Read" and "--allowedTools" in argv
    assert "Bash" not in argv and "Write" not in argv
    with pytest.raises(DecisionError):
        await decider.decide("win", [], _obs(None))


@pytest.mark.asyncio
async def test_vision_decider_failure_modes() -> None:
    async def failing(*args: Any, **kwargs: Any) -> dict[str, object]:
        return {"returncode": 1, "stdout": ""}

    async def errored(*args: Any, **kwargs: Any) -> dict[str, object]:
        return {"returncode": 0, "stdout": json.dumps({"result": "", "is_error": True})}

    for run in (failing, errored):
        decider = ClaudeVisionDecider(
            binary=Path("claude"), run=run, env={"SIRO_COMPUTER_CLOUD_SCREEN": "1"}
        )
        with pytest.raises(DecisionError):
            await decider.decide("g", [], _obs())


@pytest.mark.asyncio
async def test_stale_command_is_never_delivered(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"t": 100.0}
    bridge = ComputerBridge(ControlGate(enabled=True), clock=lambda: clock["t"])
    monkeypatch.setattr(bridge_module, "INPUT_TIMEOUT", 0.2)
    await bridge.next_command(wait=0.01)  # shell announces itself
    task = asyncio.create_task(bridge.act(InputAction("move", x=1, y=1)))
    await asyncio.sleep(0.01)
    clock["t"] += 60  # the shell was away; the command expired and must not run late
    assert await bridge.next_command(wait=0.05) is None
    assert (await task).error == "outcome_unknown"


@pytest.mark.asyncio
async def test_result_for_unknown_or_settled_command_is_ignored() -> None:
    bridge = ComputerBridge(ControlGate(enabled=True))
    assert bridge.submit_result("nope", True) is False


@pytest.mark.asyncio
async def test_vision_decider_retries_malformed_reply_once() -> None:
    replies = ["not a decision", GOOD]

    async def run(*args: Any, **kwargs: Any) -> dict[str, object]:
        return {
            "returncode": 0,
            "stdout": json.dumps({"result": replies.pop(0), "is_error": False}),
        }

    decider = ClaudeVisionDecider(
        binary=Path("claude"), run=run, env={"SIRO_COMPUTER_CLOUD_SCREEN": "1"}
    )
    assert (await decider.decide("g", [], _obs())).kind == "act" and replies == []
    replies[:] = ["bad", "still bad"]
    with pytest.raises(DecisionError):
        await decider.decide("g", [], _obs())


@pytest.mark.asyncio
async def test_shell_parked_in_a_long_poll_counts_as_online() -> None:
    clock = {"t": 100.0}
    bridge = ComputerBridge(ControlGate(enabled=True), clock=lambda: clock["t"])
    assert not bridge.executor_online
    poll = asyncio.create_task(bridge.next_command(wait=5.0))
    await asyncio.sleep(0.01)
    clock["t"] += 15  # a 20 s long poll is older than the 10 s window while still waiting
    assert bridge.executor_online
    bridge.stop()
    poll.cancel()
    await asyncio.gather(poll, return_exceptions=True)
    assert bridge.executor_online  # last poll just ended
    clock["t"] += 15
    assert not bridge.executor_online


def test_parse_decision_accepts_combo_alias_and_hold() -> None:
    decision = parse_decision(
        '{"kind":"act","action":{"kind":"key","combo":"ctrl+a","hold_ms":300},"confidence":0.7}'
    )
    assert decision.action == InputAction("key", key="ctrl+a", hold_ms=300)
