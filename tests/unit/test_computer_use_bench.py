from __future__ import annotations

import asyncio
import base64
import io
import sys
from pathlib import Path

from PIL import Image

from siro.services.computer_use.decision import Decision
from siro.services.computer_use.framedump import DumpingDecider, maybe_dump
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import InputAction

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import computer_decider_bench as bench


def _click(x: int, y: int) -> Decision:
    return Decision("act", InputAction("click", x=x, y=y), "x", "r", 0.9)


def test_click_must_land_in_box() -> None:
    expect = {"click_boxes": [[10, 10, 50, 50]]}
    assert bench.score(_click(20, 20), expect) == (True, "ok")
    assert bench.score(_click(80, 20), expect)[0] is False


def test_avoid_box_and_kind() -> None:
    assert bench.score(_click(20, 20), {"avoid_boxes": [[0, 0, 30, 30]]})[1] == "avoid_box"
    wait = Decision("wait", None, "", "", 0.5)
    assert bench.score(wait, {"kinds": ["wait", "act"]})[0] is True
    assert bench.score(wait, {})[1] == "kind:wait"


def test_key_expectation() -> None:
    key = Decision("act", InputAction("key", key="Z"), "x", "r", 0.9)
    assert bench.score(key, {"keys": ["z", "enter"]})[0] is True
    assert bench.score(key, {"click_boxes": [[0, 0, 5, 5]]})[1] == "key_instead_of_click"


def _png() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


class _Inner:
    async def decide(self, goal, history, observation, *, strategy=""):
        return _click(3, 4)

    async def verify(self, expect, before_seen, observation):
        raise AssertionError


def test_dump_wrapper_saves_frame_and_meta(tmp_path: Path) -> None:
    obs = Observation(1, 0.0, "t", "game.exe", None, (8, 8), "f", _png(), (8, 8))
    result = asyncio.run(DumpingDecider(_Inner(), tmp_path).decide("g", [], obs))
    assert result.kind == "act"
    assert len(list(tmp_path.glob("*.png"))) == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_maybe_dump_is_off_without_env() -> None:
    inner = _Inner()
    assert maybe_dump(inner, {}) is inner  # type: ignore[arg-type]
