"""One actual SIRO vision decision, no input. Read a transient frame from stdin."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

from siro.services.computer_use.decision import ClaudeVisionDecider
from siro.services.computer_use.perception import sanitize

CONFIG = Path("/mnt/c/Users/pepepig/siro-computer/computer.env")
GOAL = (
    "Continue playing Undertale from the current screen. Never choose reset, erase, or start over. "
    "If uncertain or the screen cannot be understood, ask the owner. Choose one next step."
)


async def main() -> None:
    started = time.monotonic()
    output: dict[str, object] = {"mode": "readonly", "input_sent": False}
    try:
        if Path(tempfile.gettempdir()).resolve() != Path("/dev/shm"):
            raise RuntimeError("memory_scratch_required")
        entries = {}
        for line in CONFIG.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                if key in {"SIRO_COMPUTER_CLOUD_SCREEN", "SIRO_COMPUTER_ALLOWED_PROCESSES"}:
                    entries[key] = value.strip()
        if entries.get("SIRO_COMPUTER_CLOUD_SCREEN") != "1":
            raise RuntimeError("cloud_screen_not_authorized")
        if "undertale.exe" not in {
            name.strip().lower()
            for name in entries.get("SIRO_COMPUTER_ALLOWED_PROCESSES", "").split(",")
        }:
            raise RuntimeError("game_not_allowlisted")
        frame = json.loads(sys.stdin.readline(8_100_000))
        width, height = frame["width"], frame["height"]
        if not isinstance(width, int) or not isinstance(height, int):
            raise ValueError("invalid_dimensions")
        obs = sanitize(
            {
                "title": "UNDERTALE", "process": "undertale.exe", "rect": [0, 0, width, height],
                "screen": [width, height], "image_png_b64": frame["image"],
                "image_size": [width, height], "image_rect": [0, 0, width, height],
            }, seq=1, now=time.monotonic(),
        )  # fmt: skip
        if obs.blocked_reason or not obs.image_png_b64:
            raise ValueError("invalid_frame")
        result = await ClaudeVisionDecider(env={"SIRO_COMPUTER_CLOUD_SCREEN": "1"}).decide(
            GOAL, [], obs
        )
        action = result.action
        safe_keys = {"z", "x", "enter", "space", "up", "down", "left", "right"}
        output.update(
            kind=result.kind,
            action_kind=action.kind if action else None,
            key=(action.key.lower() if action and action.key.lower() in safe_keys else "other")
            if action and action.kind == "key"
            else None,
            confidence=result.confidence,
        )
    except Exception as error:
        # Do not echo model text, command arguments, screenshots or private game dialogue.
        output["error_type"] = type(error).__name__
        if isinstance(error, RuntimeError) and str(error) in {
            "memory_scratch_required",
            "cloud_screen_not_authorized",
            "game_not_allowlisted",
        }:
            output["error_code"] = str(error)
    output["seconds"] = round(time.monotonic() - started, 3)
    print(json.dumps(output), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
