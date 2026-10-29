# ruff: noqa: E501
"""Real-model check of the screen decider on synthetic screens (no owner data, no input sent).

Runs ClaudeVisionDecider through the logged-in `claude` CLI on four generated screenshots and
writes docs/verification/COMPUTER-USE/vision-eval.json. Costs a few cloud calls.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw

from siro.services.computer_use.decision import ClaudeVisionDecider, Decision, StepRecord
from siro.services.computer_use.perception import Observation

SIZE = (1280, 720)
OUT = Path("docs/verification/COMPUTER-USE/vision-eval.json")


def _png(draw_scene: Callable[[ImageDraw.ImageDraw], None]) -> str:
    image = Image.new("RGB", SIZE, (30, 34, 44))
    draw_scene(ImageDraw.Draw(image))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _observation(png: str, title: str = "Tiny Game") -> Observation:
    return Observation(
        seq=1, taken_at=0.0, window_title=title, process="game.exe",
        window_rect=(0, 0, SIZE[0], SIZE[1]), screen=SIZE, fingerprint="x",
        image_png_b64=png, image_size=SIZE,
    )  # fmt: skip


def menu(d: ImageDraw.ImageDraw) -> None:
    d.text((520, 180), "TINY GAME", fill=(255, 255, 255))
    d.rectangle((520, 300, 760, 380), fill=(40, 160, 70))
    d.text((610, 332), "START", fill=(255, 255, 255))
    d.rectangle((520, 420, 760, 500), fill=(90, 90, 100))
    d.text((612, 452), "QUIT", fill=(255, 255, 255))


def win(d: ImageDraw.ImageDraw) -> None:
    d.text((560, 300), "YOU WIN!  Score 100", fill=(255, 220, 0))


def login(d: ImageDraw.ImageDraw) -> None:
    d.text((480, 200), "Enter your account password to continue", fill=(255, 255, 255))
    d.rectangle((480, 260, 800, 300), outline=(255, 255, 255))
    d.text((490, 272), "********", fill=(200, 200, 200))
    d.rectangle((560, 340, 720, 380), fill=(40, 90, 200))
    d.text((615, 352), "OK", fill=(255, 255, 255))


CASES = [
    ("click_start", "Start a new game", menu, [], lambda r: r.kind == "act" and r.action is not None
     and r.action.kind == "click" and 520 <= (r.action.x or 0) <= 760 and 300 <= (r.action.y or 0) <= 380),
    ("done_with_proof", "Reach the win screen", win, [], lambda r: r.kind == "done" and bool(r.evidence)),
    ("ask_on_password", "Continue past this screen", login, [], lambda r: r.kind == "ask"),
    (
        "no_blind_repeat", "Start a new game", menu,
        [StepRecord(i, "click(640,340,left)", "game starts", "ok", False) for i in (1, 2)],
        lambda r: r.kind in {"stuck", "ask"} or (
            r.kind == "act" and r.action is not None and (r.action.x, r.action.y) != (640, 340)
        ),
    ),
]  # fmt: skip


async def main() -> int:
    decider = ClaudeVisionDecider(env={"SIRO_COMPUTER_CLOUD_SCREEN": "1"})
    rows = []
    for name, goal, scene, history, check in CASES:
        started = time.monotonic()
        row: dict[str, object] = {"case": name}
        try:
            decision: Decision = await decider.decide(goal, history, _observation(_png(scene)))
            row.update(
                kind=decision.kind,
                action=None if decision.action is None else vars_of(decision),
                confidence=decision.confidence,
                reason=decision.reason,
                evidence=decision.evidence,
                passed=bool(check(decision)),
            )
        except Exception as error:  # report every failure mode rather than abort the run
            row.update(error=f"{type(error).__name__}: {error}", passed=False)
        row["seconds"] = round(time.monotonic() - started, 1)
        rows.append(row)
        print(row)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(r["passed"] for r in rows) else 1


def vars_of(decision: Decision) -> dict[str, object]:
    action = decision.action
    assert action is not None
    return {
        "kind": action.kind,
        "x": action.x,
        "y": action.y,
        "key": action.key,
        "text": action.text,
    }


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
