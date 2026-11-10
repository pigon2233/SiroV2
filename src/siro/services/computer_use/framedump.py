"""Optional full-size frame dump for offline decider benchmarks (SIRO_COMPUTER_DUMP_FRAMES=<dir>).

Wraps any Decider. Saves the exact screenshot the model saw (already cropped to the allowlisted
game window) plus goal and the model's answer, so scripts/computer_decider_bench.py can replay it.
Local files only; off unless the env var names a directory. Never raises into the control loop.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from siro.services.computer_use.decision import Decider, Decision, StepRecord, VerifyResult
from siro.services.computer_use.perception import Observation

DUMP_ENV = "SIRO_COMPUTER_DUMP_FRAMES"
MAX_FRAMES = 400


class DumpingDecider:
    def __init__(self, inner: Decider, directory: Path) -> None:
        self._inner = inner
        self._dir = directory
        self._count = 0

    async def decide(
        self,
        goal: str,
        history: Sequence[StepRecord],
        observation: Observation,
        *,
        strategy: str = "",
    ) -> Decision:
        decision = await self._inner.decide(goal, history, observation, strategy=strategy)
        self._save(goal, observation, decision)
        return decision

    async def verify(self, expect: str, before_seen: str, observation: Observation) -> VerifyResult:
        return await self._inner.verify(expect, before_seen, observation)

    def _save(self, goal: str, observation: Observation, decision: Decision) -> None:
        if not observation.image_png_b64 or self._count >= MAX_FRAMES:
            return
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            stem = f"{time.strftime('%Y%m%dT%H%M%S')}-{observation.seq:04d}-{self._count:03d}"
            (self._dir / f"{stem}.png").write_bytes(base64.b64decode(observation.image_png_b64))
            action = decision.action
            meta = {
                "goal": goal,
                "process": observation.process,
                "image_size": list(observation.image_size or ()),
                "model": {
                    "kind": decision.kind,
                    "seen": decision.seen,
                    "scene": decision.scene,
                    "x": action.x if action else None,
                    "y": action.y if action else None,
                    "key": action.key if action else "",
                },
            }
            (self._dir / f"{stem}.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            self._count += 1
        except (OSError, ValueError):
            return


def maybe_dump(decider: Decider, env: Mapping[str, str]) -> Decider:
    target = env.get(DUMP_ENV, "").strip()
    return DumpingDecider(decider, Path(target)) if target else decider
