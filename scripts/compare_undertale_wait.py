"""Read-only counterfactual on one actual frame; never emits input or private game text."""

from __future__ import annotations

import asyncio
import json
import re
import sys
import tempfile
import time
from pathlib import Path

from verify_computer_wait_vision import NEW_RULE
from verify_undertale_readonly import CONFIG, GOAL

import siro.services.computer_use.decision as decision_module
from siro.services.computer_use.decision import ClaudeVisionDecider, Decision, StepRecord
from siro.services.computer_use.perception import sanitize

SAFE_KEYS = {"z", "x", "enter", "space", "up", "down", "left", "right"}


def summarize(result: Decision) -> dict[str, object]:
    """Keep only bounded fields; no model text or arbitrary key names leave the process."""
    action = result.action
    key = action.key.lower() if action and action.kind == "key" else None
    description = (result.seen + " " + result.reason + " " + result.expect).lower()
    return {
        "kind": result.kind,
        "action_kind": action.kind if action else None,
        "key": key if key in SAFE_KEYS else "other" if key is not None else None,
        "confidence": result.confidence,
        "mentions_dark_or_transition": bool(
            re.search(r"black|dark|fade|transition|loading", description)
        ),
        "mentions_dialogue": bool(re.search(r"dialogue|dialog|speech|conversation", description)),
        "mentions_menu_or_title": bool(re.search(r"menu|title|logo", description)),
    }


async def main() -> None:
    output: dict[str, object] = {
        "mode": "readonly_counterfactual",
        "input_sent": False,
        "history": "simulated_waits",
        "cases": [],
    }
    prompt = decision_module.DECISION_PROMPT
    try:
        if Path(tempfile.gettempdir()).resolve() != Path("/dev/shm"):
            raise RuntimeError("memory_scratch_required")
        config: dict[str, str] = {}
        for line in CONFIG.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                if key in {"SIRO_COMPUTER_CLOUD_SCREEN", "SIRO_COMPUTER_ALLOWED_PROCESSES"}:
                    config[key] = value.strip()
        if config.get("SIRO_COMPUTER_CLOUD_SCREEN") != "1":
            raise RuntimeError("cloud_screen_not_authorized")
        if "undertale.exe" not in {
            x.strip().lower() for x in config.get("SIRO_COMPUTER_ALLOWED_PROCESSES", "").split(",")
        }:
            raise RuntimeError("game_not_allowlisted")
        frame = json.loads(sys.stdin.readline(8_100_000))
        if frame.get("same") is not True:
            raise RuntimeError("frames_not_identical")
        width, height = frame["width"], frame["height"]
        if (
            not isinstance(width, int)
            or isinstance(width, bool)
            or not 64 <= width <= 4096
            or not isinstance(height, int)
            or isinstance(height, bool)
            or not 64 <= height <= 4096
        ):
            raise ValueError("invalid_dimensions")
        obs = sanitize(
            {
                "title": "UNDERTALE",
                "process": "undertale.exe",
                "rect": [0, 0, width, height],
                "screen": [width, height],
                "image_png_b64": frame["image"],
                "image_size": [width, height],
                "image_rect": [0, 0, width, height],
            },
            seq=1,
            now=time.monotonic(),
        )
        if obs.blocked_reason or not obs.image_png_b64 or NEW_RULE not in prompt:
            raise ValueError("invalid_frame_or_prompt")
        cases: list[dict[str, object]] = []
        for variant in (
            "baseline_unknown",
            "comparison_unchanged",
            "repeated_unknown",
            "repeated_unchanged",
        ):
            decision_module.DECISION_PROMPT = (
                prompt.replace(NEW_RULE, "") if variant.endswith("unknown") else prompt
            )
            count = 3 if variant.startswith("repeated_") else 1
            history = [
                StepRecord(
                    i,
                    "(wait)",
                    "screen may change",
                    "ok",
                    None if variant.endswith("unknown") else False,
                    "simulated earlier wait",
                )
                for i in range(1, count + 1)
            ]
            started = time.monotonic()
            row: dict[str, object] = {"variant": variant, "wait_count": count}
            try:
                result = await ClaudeVisionDecider(env={"SIRO_COMPUTER_CLOUD_SCREEN": "1"}).decide(
                    GOAL, history, obs
                )
                row.update(summarize(result))
            except Exception as error:
                row["error_type"] = type(error).__name__
            row["seconds"] = round(time.monotonic() - started, 3)
            cases.append(row)
        output["cases"] = cases
        output["frames_png_identical"] = True
    except Exception as error:
        output["error_type"] = type(error).__name__
        if isinstance(error, RuntimeError) and str(error) in {
            "memory_scratch_required",
            "cloud_screen_not_authorized",
            "game_not_allowlisted",
            "frames_not_identical",
        }:
            output["error_code"] = str(error)
    finally:
        decision_module.DECISION_PROMPT = prompt
    print(json.dumps(output), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
