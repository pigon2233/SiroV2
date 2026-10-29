"""Local training-data recorder: (small frame, action, what happened) for each decision step.

Off by default (SIRO_COMPUTER_RECORD=1). Stays on this machine under the SIRO data directory,
only for allowlisted programs, never records typed text (length only) or window titles, is capped
by run count and size, and the owner can list or delete it. This is raw material for a later local
model (behavior cloning); nothing here trains or sends anything.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image

from siro.services.computer_use.decision import Decision
from siro.services.computer_use.perception import Observation
from siro.services.computer_use.safety import InputAction

DEMO_DIR_NAME = "computer-demos"
FRAME_WIDTH = 320
MAX_RUNS = 40
MAX_BYTES = 1_500_000_000


def demos_dir(env: dict[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    return Path(values.get("SIRO_DATA_DIR") or ".siro-data") / DEMO_DIR_NAME


def _safe(name: str) -> str:
    return re.sub(r"[^a-z0-9._-]", "_", name.strip().lower())[:60] or "unknown"


def _dir_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


@dataclass(slots=True)
class DemoRun:
    path: Path
    process: str
    goal: str
    clock: Callable[[], float]
    steps: list[dict[str, Any]] = field(default_factory=list)

    def step(self, observation: Observation, decision: Decision, action: InputAction | None) -> int:
        """Save the frame the decision was made on and what was done. Returns the step index."""
        index = len(self.steps)
        frame = None
        if observation.image_png_b64 and observation.image_size:
            try:
                image = Image.open(io.BytesIO(base64.b64decode(observation.image_png_b64))).convert(
                    "RGB"
                )
                height = max(1, round(image.height * FRAME_WIDTH / image.width))
                (self.path / "frames").mkdir(parents=True, exist_ok=True)
                frame = f"frames/{index:04d}.png"
                image.resize((FRAME_WIDTH, height)).save(self.path / frame, optimize=True)
            except (OSError, ValueError):
                frame = None
        width, height = observation.image_size or (0, 0)
        record: dict[str, Any] = {
            "i": index,
            "t": self.clock(),
            "frame": frame,
            "frame_size": [FRAME_WIDTH, round(height * FRAME_WIDTH / width)] if width else None,
            "kind": decision.kind,
            "action": None,
            "seen": decision.seen,
            "expect": decision.expect,
            "confidence": decision.confidence,
            "changed": None,
        }
        if action is not None:
            record["action"] = {
                "kind": action.kind,
                "key": action.key,
                "hold_ms": action.hold_ms,
                "button": action.button,
                "text_len": len(action.text),
                # pointer target relative to the frame (0..1) so it survives resizing
                "x": None if decision.action is None or decision.action.x is None or not width
                else round(decision.action.x / width, 4),
                "y": None if decision.action is None or decision.action.y is None or not height
                else round(decision.action.y / height, 4),
            }  # fmt: skip
        self.steps.append(record)
        self._write()
        return index

    def set_changed(self, index: int, changed: bool) -> None:
        if 0 <= index < len(self.steps):
            self.steps[index]["changed"] = changed
            self._write()

    def finish(self, state: str, reason: str) -> None:
        meta = {
            "process": self.process,
            "goal": self.goal[:300],
            "state": state,
            "reason": reason[:200],
            "steps": len(self.steps),
            "finished_at": self.clock(),
        }
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        self._write()

    def _write(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        text = "\n".join(json.dumps(s, ensure_ascii=False) for s in self.steps)
        (self.path / "steps.jsonl").write_text(text, encoding="utf-8")


class DemoRecorder:
    def __init__(
        self,
        root: Path,
        *,
        max_runs: int = MAX_RUNS,
        max_bytes: int = MAX_BYTES,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._root = root
        self._max_runs = max_runs
        self._max_bytes = max_bytes
        self._clock = clock

    def begin(self, process: str, goal: str) -> DemoRun:
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime(self._clock()))
        path = self._root / _safe(process) / f"{stamp}-{uuid4().hex[:6]}"
        path.mkdir(parents=True, exist_ok=True)
        self.prune()
        return DemoRun(path, _safe(process), goal, self._clock)

    def runs(self) -> list[Path]:
        if not self._root.is_dir():
            return []
        return sorted(
            (
                p
                for game in self._root.iterdir()
                if game.is_dir()
                for p in game.iterdir()
                if p.is_dir()
            ),
            key=lambda p: p.name,
        )

    def prune(self) -> None:
        """Drop the oldest runs beyond the run-count or size cap (never the newest one)."""
        runs = self.runs()
        while len(runs) > 1 and (
            len(runs) > self._max_runs or sum(_dir_bytes(p) for p in runs) > self._max_bytes
        ):
            shutil.rmtree(runs.pop(0), ignore_errors=True)

    def summary(self) -> list[dict[str, Any]]:
        out = []
        for path in self.runs():
            try:
                meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                meta = {}
            out.append(
                {"process": path.parent.name, "run": path.name, "bytes": _dir_bytes(path), **meta}
            )
        return out

    def clear(self, process: str | None = None) -> int:
        targets = [self._root / _safe(process)] if process else [self._root]
        removed = len(self.runs()) if process is None else sum(
            1 for p in self.runs() if p.parent.name == _safe(process)
        )  # fmt: skip
        for target in targets:
            shutil.rmtree(target, ignore_errors=True)
        return removed
