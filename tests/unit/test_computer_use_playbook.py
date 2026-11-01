from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from siro.services.computer_use.bridge import ComputerBridge
from siro.services.computer_use.decision import Decision, StepRecord
from siro.services.computer_use.http import ComputerRuns
from siro.services.computer_use.loop import DecisionLoop
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.playbook import (
    MAX_NOTE_CHARS,
    MAX_NOTES,
    ClaudeReflector,
    PlaybookStore,
    notes_block,
    parse_notes,
)
from siro.services.computer_use.safety import ControlGate

RECT = [100, 100, 800, 600]


class FakeDesktop:
    """Minimal Windows-shell stand-in: a two-click game answering observe/input commands."""

    def __init__(self, bridge: ComputerBridge) -> None:
        self.bridge, self.scene = bridge, "menu"
        self.task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self._serve())

    async def close(self) -> None:
        assert self.task is not None
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)

    async def _serve(self) -> None:
        while True:
            command = await self.bridge.next_command(wait=0.05)
            if command is None:
                continue
            if command["op"] == "observe":
                report = {
                    "title": "Cool Game", "process": "game.exe", "rect": RECT,
                    "screen": [1920, 1080],
                    "fingerprint": self.scene, "image_png_b64": "AAAA", "image_size": [1920, 1080],
                }  # fmt: skip
                self.bridge.submit_result(command["id"], True, data=report)
                continue
            action = command["payload"]
            point = (action["x"], action["y"])
            if self.scene == "menu" and point == (300, 300):
                self.scene = "playing"
            elif self.scene == "playing" and point == (500, 400):
                self.scene = "won"
            self.bridge.submit_result(command["id"], True)


def solver(obs: Observation, history: Sequence[StepRecord]) -> Decision:
    from siro.services.computer_use.safety import InputAction

    if obs.fingerprint == "menu":
        return Decision("act", InputAction("click", x=300, y=300), "scene changes", "r", 0.9)
    if obs.fingerprint == "playing":
        return Decision("act", InputAction("click", x=500, y=400), "scene changes", "r", 0.9)
    return Decision("done", None, "", "won", 0.95, "banner says YOU WIN")


def test_store_dedups_scrubs_caps_and_keeps_provenance(tmp_path: Path) -> None:
    store = PlaybookStore(tmp_path, clock=lambda: 42.0)
    assert (
        store.add("Game.EXE", ["Press Z to confirm menus", "press  z to CONFIRM menus!"], "r1") == 1
    )
    assert (
        store.add("game.exe", ["key sk-" + "a" * 24 + " leaked", "x"], "r2") == 1
    )  # too-short dropped
    notes = store.notes("GAME.exe")
    assert [n.run_id for n in notes] == ["r1", "r2"] and notes[0].at == 42.0
    assert "sk-" not in notes[1].text and len(notes[1].text) <= MAX_NOTE_CHARS
    assert store.add("game.exe", ["n" * 500], "r3") == 1
    assert len(store.notes("game.exe")[-1].text) == MAX_NOTE_CHARS
    for i in range(30):
        store.add("game.exe", [f"lesson number {i} about the game screen"], f"r{i}")
    assert len(store.notes("game.exe")) == MAX_NOTES  # oldest fall off
    assert store.notes("game.exe")[-1].text.endswith("screen")


def test_store_remove_clear_and_corrupt_file(tmp_path: Path) -> None:
    store = PlaybookStore(tmp_path)
    store.add("g.exe", ["first lesson here", "second lesson here"], "r")
    assert store.remove("g.exe", 0) and store.texts("g.exe") == ["second lesson here"]
    assert not store.remove("g.exe", 5)
    store.clear("g.exe")
    assert store.texts("g.exe") == []
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert store.texts("bad") == []
    assert store.texts("../../etc/passwd") == []  # path-like names stay inside the directory


def test_parse_notes_and_block() -> None:
    assert parse_notes('sure {"notes":["a note that is fine", 5, "another one here"]}') == [
        "a note that is fine",
        "another one here",
    ]
    assert parse_notes("no json") == [] and parse_notes('{"notes":"x"}') == []
    assert notes_block([]) == "" and "- hello" in notes_block(["hello"])


@pytest.mark.asyncio
async def test_reflector_needs_consent_and_parses_reply() -> None:
    calls: list[Any] = []

    async def run(argv: tuple[str, ...], **kwargs: Any) -> dict[str, object]:
        calls.append(argv)
        reply = {
            "result": '{"notes":["Z advances text, X cancels in this game"]}',
            "is_error": False,
        }
        return {"returncode": 0, "stdout": json.dumps(reply)}

    steps = [StepRecord(1, "key(z)", "next line", "ok", True, "intro text")]
    off = ClaudeReflector(run=run, env={})
    assert await off.reflect("g.exe", "goal", "done", "ok", [], steps) == [] and calls == []
    on = ClaudeReflector(run=run, env={"SIRO_COMPUTER_CLOUD_SCREEN": "1"})
    from siro.services.tools import claude as claude_module

    claude_module_binary = claude_module.claude_binary
    claude_module.claude_binary = lambda: Path("claude")  # type: ignore[assignment]
    try:
        notes = await on.reflect("g.exe", "goal", "done", "ok", ["old"], steps)
    finally:
        claude_module.claude_binary = claude_module_binary  # type: ignore[assignment]
    assert notes == ["Z advances text, X cancels in this game"]
    assert "--tools" in calls[0] and "WebSearch" not in calls[0]


class Recorder:
    def __init__(self) -> None:
        self.goals: list[str] = []

    async def decide(
        self, goal: str, history: Sequence[StepRecord], observation: Observation, **_kwargs
    ) -> Decision:
        self.goals.append(goal)
        return solver(observation, history)


@pytest.mark.asyncio
async def test_loop_shows_saved_notes_to_the_decider(tmp_path: Path) -> None:
    store = PlaybookStore(tmp_path)
    store.add("game.exe", ["The START button is green and in the middle"], "r0")
    bridge = ComputerBridge(ControlGate(enabled=True))
    desktop = FakeDesktop(bridge)
    desktop.start()
    await asyncio.sleep(0.02)
    decider = Recorder()
    loop = DecisionLoop(bridge, decider, allowed=frozenset({"game.exe"}), settle=0, playbook=store)
    report = await loop.run("win the game")
    await desktop.close()
    assert report.success and loop.process == "game.exe"
    assert all("START button is green" in g and g.startswith("win the game") for g in decider.goals)


class FixedReflector:
    def __init__(self, lessons: list[str]) -> None:
        self.lessons = lessons
        self.seen: list[Any] = []

    async def reflect(self, *args: Any) -> list[str]:
        self.seen.append(args)
        return self.lessons


@pytest.mark.asyncio
async def test_run_learns_notes_after_finishing(tmp_path: Path) -> None:
    bridge = ComputerBridge(ControlGate(enabled=True))
    desktop = FakeDesktop(bridge)
    desktop.start()
    await asyncio.sleep(0.02)
    store = PlaybookStore(tmp_path)
    reflector = FixedReflector(["Click START first, then the second button"])
    runs = ComputerRuns(bridge, Recorder(), playbook=store, reflector=reflector)
    import siro.services.computer_use.http as http_module

    original = http_module.DecisionLoop
    http_module.DecisionLoop = lambda b, d, **kw: original(  # type: ignore[assignment]
        b, d, allowed=frozenset({"game.exe"}), settle=0, **kw
    )
    try:
        assert runs.start("win the game")
        assert runs._task is not None
        await runs._task
    finally:
        http_module.DecisionLoop = original  # type: ignore[assignment]
        await desktop.close()
    assert runs.learned == 1 and store.texts("game.exe") == [
        "Click START first, then the second button"
    ]
    assert reflector.seen[0][0] == "game.exe" and reflector.seen[0][2] == "done"
    assert runs.status()["learned_notes"] == 1
