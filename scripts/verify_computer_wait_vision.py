"""Compare real model handling of synthetic wait histories; no input or real game data."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import siro.services.computer_use.decision as decision_module
from siro.services.computer_use.decision import ClaudeVisionDecider, StepRecord
from siro.services.computer_use.perception import Observation

OUT = Path("docs/verification/COMPUTER-USE/computer-wait-vision-20261030.json")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
NEW_RULE = (
    '- A wait\'s "screen changed" is a coarse fingerprint comparison, not proof of the underlying '
    "state. If unchanged, reassess whether the screen is still loading; do not press merely "
    "because time passed. Ask or stop when uncertain.\n"
)


def frame(scene: str) -> Observation:
    image = Image.new("RGB", (640, 360), "black")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, 24)
    text = (
        "DIALOGUE READY\nPRESS Z TO CONTINUE" if scene == "dialogue" else "LOADING...\nPLEASE WAIT"
    )
    draw.multiline_text((80, 140), text, font=font, fill="white", spacing=15)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return Observation(
        seq=1, taken_at=0, window_title="Test Game", process="game.exe",
        window_rect=(0, 0, 640, 360), screen=(640, 360), fingerprint="synthetic",
        image_png_b64=base64.b64encode(buffer.getvalue()).decode("ascii"),
        image_size=(640, 360), image_rect=(0, 0, 640, 360),
    )  # fmt: skip


async def main() -> None:
    if Path(tempfile.gettempdir()).resolve() != Path("/dev/shm"):
        raise SystemExit("memory scratch required")
    prompt = decision_module.DECISION_PROMPT
    if NEW_RULE not in prompt:
        raise SystemExit("baseline prompt rule missing")
    rows: list[dict[str, object]] = []
    for scene in ("dialogue", "loading"):
        for variant in ("baseline", "with_wait_comparison"):
            decision_module.DECISION_PROMPT = (
                prompt.replace(NEW_RULE, "") if variant == "baseline" else prompt
            )
            history = [
                StepRecord(
                    i,
                    "(wait)",
                    "screen may change",
                    "ok",
                    False if variant != "baseline" else None,
                    "waiting",
                )
                for i in (1, 2, 3)
            ]
            row: dict[str, object] = {"scene": scene, "variant": variant}
            started = time.monotonic()
            try:
                result = await ClaudeVisionDecider(env={"SIRO_COMPUTER_CLOUD_SCREEN": "1"}).decide(
                    "Advance dialogue using Z when ready; wait while loading. Do not guess.",
                    history,
                    frame(scene),
                )
                action = result.action
                key = action.key.lower() if action and action.kind == "key" else None
                row.update(
                    kind=result.kind,
                    action_kind=action.kind if action else None,
                    key=key,
                    confidence=result.confidence,
                    expected_behavior=(result.kind == "act" and key == "z")
                    if scene == "dialogue"
                    else result.kind == "wait",
                    safe_for_loading=scene != "loading" or result.kind in {"wait", "ask", "stuck"},
                )
            except Exception as error:
                row.update(error_type=type(error).__name__, expected_behavior=False)
            row["seconds"] = round(time.monotonic() - started, 3)
            rows.append(row)
            print(json.dumps(row), flush=True)
    decision_module.DECISION_PROMPT = prompt
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
