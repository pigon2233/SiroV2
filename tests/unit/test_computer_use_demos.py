from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image

from siro.services.computer_use.decision import Decision
from siro.services.computer_use.demos import DemoRecorder, demos_dir
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import InputAction


def _obs(width: int = 640, height: int = 480) -> Observation:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buffer, "PNG")
    return Observation(
        seq=1, taken_at=0.0, window_title="Secret Title", process="game.exe",
        window_rect=(0, 0, width, height), screen=(1920, 1080), fingerprint="f",
        image_png_b64=base64.b64encode(buffer.getvalue()).decode(), image_size=(width, height),
        image_rect=(0, 0, width, height),
    )  # fmt: skip


def _decision(action: InputAction | None, kind: str = "act") -> Decision:
    return Decision(kind, action, "screen changes", "r", 0.9, seen="menu screen")


def test_records_small_frame_action_and_effect_without_private_text(tmp_path: Path) -> None:
    recorder = DemoRecorder(tmp_path, clock=lambda: 1000.0)
    run = recorder.begin("Game.EXE", "win")
    action = InputAction("type", text="my private note", x=320, y=240)
    index = run.step(_obs(), _decision(InputAction("click", x=320, y=240)), action)
    run.set_changed(index, True)
    run.step(_obs(), _decision(None, "wait"), None)
    run.finish("done", "all good")
    steps = [json.loads(line) for line in (run.path / "steps.jsonl").read_text().splitlines()]
    assert steps[0]["action"]["text_len"] == 15 and "private" not in json.dumps(steps)
    assert steps[0]["action"]["x"] == 0.5 and steps[0]["action"]["y"] == 0.5
    assert steps[0]["changed"] is True and steps[0]["seen"] == "menu screen"
    assert steps[1]["kind"] == "wait" and steps[1]["action"] is None
    frame = Image.open(run.path / steps[0]["frame"])
    assert frame.size == (320, 240)
    meta = json.loads((run.path / "meta.json").read_text())
    assert meta["state"] == "done" and meta["steps"] == 2 and "Secret Title" not in json.dumps(meta)


def test_prune_by_run_count_and_clear(tmp_path: Path) -> None:
    clock = {"t": 1000.0}
    recorder = DemoRecorder(tmp_path, max_runs=2, clock=lambda: clock["t"])
    for _ in range(4):
        clock["t"] += 10
        run = recorder.begin("g.exe", "goal")
        run.step(_obs(64, 48), _decision(InputAction("key", key="z")), InputAction("key", key="z"))
        run.finish("done", "ok")
    assert len(recorder.runs()) == 2  # oldest dropped, newest kept
    assert {r["process"] for r in recorder.summary()} == {"g.exe"}
    assert recorder.clear("other.exe") == 0 and len(recorder.runs()) == 2
    assert recorder.clear("g.exe") == 2 and recorder.runs() == []


def test_size_cap_keeps_the_newest_run(tmp_path: Path) -> None:
    clock = {"t": 1000.0}
    recorder = DemoRecorder(tmp_path, max_bytes=1, clock=lambda: clock["t"])
    for _ in range(3):
        clock["t"] += 10
        run = recorder.begin("g.exe", "goal")
        run.step(_obs(64, 48), _decision(None, "wait"), None)
    assert len(recorder.runs()) == 1


def test_demos_dir_default(tmp_path: Path) -> None:
    assert demos_dir({"SIRO_DATA_DIR": str(tmp_path)}) == tmp_path / "computer-demos"
