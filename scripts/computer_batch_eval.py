#!/usr/bin/env python3
"""Offline TWO-target planning probe; never executes/observes input or claims gameplay success."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from computer_click_eval import load_cases, score_click

from siro.services.computer_use.batch_decision import BatchPlanner
from siro.services.computer_use.decision import Decision
from siro.services.computer_use.hybrid import VisualSelector
from siro.services.computer_use.ocr import WindowsTextReader


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("SIRO_COMPUTER_BATCH_BENCH_ENABLED") != "1":
        parser.error("explicit SIRO_COMPUTER_BATCH_BENCH_ENABLED=1 required")
    _, cases = load_cases(Path("docs/verification/COMPUTER-USE/stage2/cases.json"))
    by_id = {c["id"]: (c, o) for c, o in cases}
    targets = [by_id[n][0] for n in ("combat-right-defend", "combat-end-turn")]
    observation = by_id["combat-end-turn"][1]
    rows = []
    for backend in ("ollama", "claude"):
        start = time.monotonic()
        try:
            planner = BatchPlanner(
                WindowsTextReader(
                    Path("docs/verification/COMPUTER-USE/stage2/ocr"), cache_only=True
                ),
                VisualSelector(backend, dict(os.environ), timeout=90),
            )
            async with asyncio.timeout(90):
                plan = await planner.plan(
                    "Play the rightmost Defend card, then click End Turn. "
                    "Do not click enemies or other cards.",
                    observation,
                )
            hits = []
            for action, target in zip(plan.actions, targets, strict=False):
                hits.append(
                    score_click(Decision("act", action), target["expect"]["click_boxes"])[0]
                )
            rows.append(
                {
                    "backend": backend,
                    "seconds": time.monotonic() - start,
                    "actions": [[a.x, a.y] for a in plan.actions],
                    "per_target_hit": hits,
                    "both_targets_hit": len(plan.actions) == 2 and all(hits),
                }
            )
        except Exception as error:
            rows.append(
                {
                    "backend": backend,
                    "seconds": time.monotonic() - start,
                    "error": type(error).__name__ + ":" + str(error),
                    "both_targets_hit": False,
                }
            )
    report = {
        "probe": (
            "one two-target localization prompt on an existing combat frame; "
            "NOT validated gameplay sequence"
        ),
        "no_input_executed": True,
        "num_ctx": 8192,
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
