"""Offline Claude verifier predicate probe; no action, bridge, capture or input.

This measures CURRENT-scene predicates derived from existing manual scene labels,
NOT game transitions, input registration, successful play, or a held-out dataset.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from computer_click_eval import load_cases

from siro.services.computer_use.decision import ClaudeVisionDecider, cloud_screen_allowed

PREDICATES = {
    "menu": "The main menu with Single Player or Continue Game options is visible.",
    "combat": "Combat with hand cards and an End Turn button is visible.",
    "event": "An event/dialogue scene with Continue near the bottom is visible.",
}


async def probe(path: Path, out: Path, timeout: int) -> None:
    values = dict(os.environ)
    if not (
        values.get("SIRO_COMPUTER_VERIFY_BENCH_ENABLED") == "1"
        and values.get("SIRO_COMPUTER_CLAUDE_VERIFY") == "1"
        and cloud_screen_allowed(values)
    ):
        raise ValueError(
            "offline verify probe off: requires VERIFY_BENCH_ENABLED, CLAUDE_VERIFY "
            "and CLOUD_SCREEN flags"
        )
    _, cases = load_cases(path)
    brain = ClaudeVisionDecider(env=values, timeout=timeout)
    result: dict[str, Any] = {
        "kind": "static_scene_predicate_NOT_transition_validation",
        "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "recorded_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "label_source": "stage2 manual_visual_review scenario metadata; no new or real-run frames",
        "rows": [],
    }
    rows: list[dict[str, Any]] = []
    seen = set()
    for case, observation in cases:
        if case["sha256"] in seen:
            continue
        seen.add(case["sha256"])
        scene = case["scenario"]
        for positive in (True, False):
            expected = "confirmed" if positive else "denied"
            predicate = PREDICATES[scene if positive else "combat" if scene != "combat" else "menu"]
            start = time.perf_counter()
            error = ""
            try:
                actual = await asyncio.wait_for(
                    brain.verify(
                        predicate,
                        "Unknown: static offline frame; no action was performed.",
                        observation,
                    ),
                    timeout=timeout + 2,
                )
                status = actual.status
                detail = actual.detail
            except Exception as exc:
                status = "unknown"
                detail = ""
                error = type(exc).__name__ + ":" + str(exc)[:200]
            rows.append(
                {
                    "image": case["image"],
                    "sha256": case["sha256"],
                    "scene": scene,
                    "predicate": predicate,
                    "expected": expected,
                    "actual": status,
                    "detail": detail,
                    "error": error,
                    "correct": status == expected,
                    "seconds": time.perf_counter() - start,
                }
            )
            result["rows"] = rows
            result["summary"] = {
                "correct": sum(row["correct"] for row in rows),
                "count": len(rows),
                "avg_seconds": statistics.mean(row["seconds"] for row in rows),
                "median_seconds": statistics.median(row["seconds"] for row in rows),
            }
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(case["image"], expected, status, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 60:
        parser.error("timeout must be 1..60 seconds")
    asyncio.run(probe(args.cases, args.out, args.timeout))


if __name__ == "__main__":
    main()
