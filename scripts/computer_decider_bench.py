"""Offline benchmark for computer-use deciders on saved screenshots (no input is ever sent).

  python scripts/computer_decider_bench.py <cases.json> --decider ollama --model gemma4:e4b
  python scripts/computer_decider_bench.py <cases.json> --decider groq --out result.json

cases.json = {"cases": [{"id", "image", "goal", "process"?, "expect": {...}}]}; image paths are
relative to the cases file. expect: kinds (accepted decision kinds, default ["act"]),
click_boxes ([[x0,y0,x1,y1],...] in screenshot pixels; a click must land in one),
keys (accepted keys, case-insensitive), avoid_boxes (a click inside any of these fails).
Frames for new cases come from SIRO_COMPUTER_DUMP_FRAMES=<dir> during real play.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image

from siro.services.computer_use.decision import DECIDER_ENV, Decision, make_decider
from siro.services.computer_use.perception import Observation


def score(decision: Decision, expect: dict[str, Any]) -> tuple[bool, str]:
    kinds = expect.get("kinds") or ["act"]
    if decision.kind not in kinds:
        return False, f"kind:{decision.kind}"
    action = decision.action
    if decision.kind != "act" or action is None:
        return True, "ok"
    if action.kind in {"click", "move"} and action.x is not None and action.y is not None:
        point = (action.x, action.y)
        for box in expect.get("avoid_boxes") or []:
            if _inside(point, box):
                return False, "avoid_box"
        boxes = expect.get("click_boxes")
        if boxes and not any(_inside(point, b) for b in boxes):
            return False, f"miss@{point[0]},{point[1]}"
    elif action.kind == "key":
        keys = [k.lower() for k in expect.get("keys") or []]
        if keys and action.key.lower() not in keys:
            return False, f"key:{action.key}"
        if expect.get("click_boxes") and not keys:
            return False, "key_instead_of_click"
    elif expect.get("click_boxes") or expect.get("keys"):
        return False, f"action:{action.kind}"
    return True, "ok"


def _inside(point: tuple[int, int], box: list[int]) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def observation_for(path: Path, process: str) -> Observation:
    with Image.open(path) as image:
        size = image.size
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return Observation(
        seq=1, taken_at=0.0, window_title="", process=process,
        window_rect=(0, 0, *size), screen=size, fingerprint=path.name,
        image_png_b64=data, image_size=size, image_rect=(0, 0, *size),
    )  # fmt: skip


async def run(cases_path: Path, env: dict[str, str]) -> dict[str, Any]:
    spec = json.loads(cases_path.read_text(encoding="utf-8"))
    decider = make_decider(env)
    rows: list[dict[str, Any]] = []
    for case in spec["cases"]:
        obs = observation_for(cases_path.parent / case["image"], case.get("process", "game.exe"))
        started = time.monotonic()
        try:
            decision = await decider.decide(case["goal"], [], obs)
            passed, why = score(decision, case.get("expect", {}))
            point = [decision.action.x, decision.action.y] if decision.action else None
            detail = {"kind": decision.kind, "point": point, "seen": decision.seen[:120]}
        except Exception as error:
            passed, why, detail = False, f"error:{type(error).__name__}:{error}"[:120], {}
        rows.append({
            "id": case["id"], "pass": passed, "why": why,
            "seconds": round(time.monotonic() - started, 2), **detail,
        })  # fmt: skip
    times = [r["seconds"] for r in rows]
    return {
        "decider": env.get(DECIDER_ENV, "ollama"),
        "model": env.get("SIRO_COMPUTER_OLLAMA_MODEL") or env.get("SIRO_COMPUTER_GROQ_MODEL") or "",
        "cases": len(rows),
        "passed": sum(r["pass"] for r in rows),
        "median_seconds": round(statistics.median(times), 2) if times else 0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--decider", choices=["ollama", "groq", "claude"], default="ollama")
    parser.add_argument("--model", default="")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    env = dict(os.environ)
    env[DECIDER_ENV] = args.decider
    env.pop("SIRO_COMPUTER_DUMP_FRAMES", None)  # never re-dump while benchmarking
    if args.model:
        key = {"ollama": "SIRO_COMPUTER_OLLAMA_MODEL", "groq": "SIRO_COMPUTER_GROQ_MODEL"}.get(
            args.decider
        )
        if key:
            env[key] = args.model
    env.setdefault("SIRO_COMPUTER_CLOUD_SCREEN", "1" if args.decider != "ollama" else "0")
    result = asyncio.run(run(args.cases, env))
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(f"{result['decider']} {result['model']}: {result['passed']}/{result['cases']} "
          f"median {result['median_seconds']}s")  # fmt: skip
    for row in result["rows"]:
        if not row["pass"]:
            print(f"  FAIL {row['id']}: {row['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
