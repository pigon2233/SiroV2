from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

from siro.services.computer_use.dataset import label_of, load_game
from siro.services.computer_use.decision import Decision
from siro.services.computer_use.demos import DemoRecorder
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import InputAction


def _obs() -> Observation:
    buffer = io.BytesIO()
    Image.new("RGB", (160, 120), (30, 60, 90)).save(buffer, "PNG")
    return Observation(
        seq=1, taken_at=0.0, window_title="t", process="game.exe", window_rect=(0, 0, 160, 120),
        screen=(1920, 1080), fingerprint="f",
        image_png_b64=base64.b64encode(buffer.getvalue()).decode(),
        image_size=(160, 120), image_rect=(0, 0, 160, 120),
    )  # fmt: skip


def _record(root: Path, name: str, actions: list[InputAction | None]) -> None:
    clock = {"t": hash(name) % 100000 + 1.0}
    recorder = DemoRecorder(root, clock=lambda: clock["t"])
    run = recorder.begin("Game.exe", "goal")
    for action in actions:
        kind = "act" if action else "wait"
        index = run.step(_obs(), Decision(kind, action, "e", "r", 0.9, seen="s"), action)
        if action:
            run.set_changed(index, action.key != "x")
    run.finish("done", "ok")


def test_label_of_distinguishes_tap_hold_and_wait() -> None:
    assert label_of({"action": None}) == "wait"
    assert label_of({"action": {"kind": "key", "key": "Z", "hold_ms": 0}}) == "key:z"
    assert label_of({"action": {"kind": "key", "key": "left", "hold_ms": 500}}) == "key:left:hold"
    assert label_of({"action": {"kind": "click"}}) == "click"


def test_stats_baseline_split_and_sheet(tmp_path: Path) -> None:
    z, left = InputAction("key", key="z"), InputAction("key", key="left", hold_ms=400)
    x = InputAction("key", key="x")
    for i in range(4):
        _record(tmp_path, f"run{i}", [z, z, left, None, x])
    data = load_game(tmp_path, "GAME.exe")
    stats = data.stats()
    assert stats["runs"] == 4 and stats["samples"] == 20 and stats["with_frame"] == 20
    assert stats["labels"]["key:z"] == 8 and stats["labels"]["wait"] == 4
    assert stats["baseline_accuracy"] == 0.4  # always guessing "key:z"
    assert stats["changed_rate"]["key:x"] == 0.0 and stats["changed_rate"]["key:z"] == 1.0
    train, val = data.split(0.25, seed=1)
    assert len(train) + len(val) == 20
    assert {s.run for s in train}.isdisjoint({s.run for s in val}) and len(
        {s.run for s in val}
    ) == 1
    assert data.split(0.25, seed=1) == (train, val)  # deterministic
    out = tmp_path / "sheet" / "s.png"
    assert data.contact_sheet(out, count=6) == 6 and Image.open(out).size == (240 * 4, 200 * 2)


def test_missing_game_corrupt_lines_and_single_run(tmp_path: Path) -> None:
    assert load_game(tmp_path, "nothing.exe").samples == []
    _record(tmp_path, "only", [InputAction("key", key="z")])
    run = next((tmp_path / "game.exe").iterdir())
    with (run / "steps.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("\n{broken json")
    data = load_game(tmp_path, "game.exe")
    assert len(data.samples) == 1
    train, val = data.split(0.5)
    assert len(train) == 1 and val == []  # one run cannot be split without leaking
    assert data.contact_sheet(tmp_path / "none.png", count=0) == 0
