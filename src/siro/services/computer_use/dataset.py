"""Read recorded demos (see demos.py) as a per-game dataset: stats, run-level split, contact sheet.

This is the bridge to a later training step. It only reads; nothing here trains or uploads.
Labels are coarse on purpose ("key:z", "key:left:hold", "click", "wait"): a first behavior-cloning
model predicts these, and the share of the most common one is the baseline it has to beat.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

HOLD_MS = 300  # a key held at least this long is a different label than a tap


@dataclass(frozen=True, slots=True)
class Sample:
    run: str
    index: int
    frame: Path | None
    label: str
    changed: bool | None
    seen: str


def label_of(step: dict[str, Any]) -> str:
    action = step.get("action")
    if not action:
        return "wait"
    kind = str(action.get("kind", "?"))
    if kind == "key":
        hold = ":hold" if int(action.get("hold_ms") or 0) >= HOLD_MS else ""
        return f"key:{str(action.get('key', '')).lower()}{hold}"
    return kind


@dataclass(slots=True)
class Dataset:
    process: str
    samples: list[Sample]

    @property
    def runs(self) -> list[str]:
        return sorted({s.run for s in self.samples})

    def stats(self) -> dict[str, Any]:
        labels = Counter(s.label for s in self.samples)
        total = len(self.samples)
        top = labels.most_common(1)
        changed: dict[str, list[int]] = {}
        for s in self.samples:
            if s.changed is not None:
                bucket = changed.setdefault(s.label, [0, 0])
                bucket[0] += int(s.changed)
                bucket[1] += 1
        return {
            "process": self.process,
            "runs": len(self.runs),
            "samples": total,
            "with_frame": sum(1 for s in self.samples if s.frame is not None),
            "labels": dict(labels.most_common()),
            # accuracy of always guessing the most common label: the bar a model must beat
            "baseline_accuracy": round(top[0][1] / total, 4) if top else 0.0,
            "changed_rate": {k: round(v[0] / v[1], 3) for k, v in sorted(changed.items())},
        }

    def split(self, val_fraction: float = 0.2, seed: int = 0) -> tuple[list[Sample], list[Sample]]:
        """Split by whole run (frames of one run are near-duplicates; steps would leak)."""
        runs = self.runs
        random.Random(seed).shuffle(runs)
        n_val = round(len(runs) * val_fraction)
        n_val = min(max(n_val, 1), len(runs) - 1) if len(runs) >= 2 else 0
        val_runs = set(runs[:n_val])
        return (
            [s for s in self.samples if s.run not in val_runs],
            [s for s in self.samples if s.run in val_runs],
        )

    def contact_sheet(self, out: Path, count: int = 12, seed: int = 0, columns: int = 4) -> int:
        """Save a grid of random frames with their label written on top. Returns frames drawn."""
        framed = [s for s in self.samples if s.frame is not None and s.frame.is_file()]
        random.Random(seed).shuffle(framed)
        chosen = framed[:count]
        if not chosen:
            return 0
        thumbs: list[Image.Image] = []
        for s in chosen:
            assert s.frame is not None
            image = Image.open(s.frame).convert("RGB")
            image.thumbnail((240, 180))
            canvas = Image.new("RGB", (240, 200), (20, 20, 24))
            canvas.paste(image, (0, 20))
            draw = ImageDraw.Draw(canvas)
            draw.text((4, 4), f"{s.label}  changed={s.changed}", fill=(255, 220, 120))
            thumbs.append(canvas)
        rows = (len(thumbs) + columns - 1) // columns
        sheet = Image.new("RGB", (240 * columns, 200 * rows), (0, 0, 0))
        for i, thumb in enumerate(thumbs):
            sheet.paste(thumb, ((i % columns) * 240, (i // columns) * 200))
        out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out)
        return len(thumbs)


def load_game(root: Path, process: str) -> Dataset:
    """Load every recorded run of one program (``root`` is the computer-demos directory)."""
    safe = process.strip().lower()
    game_dir = root / safe
    samples: list[Sample] = []
    if game_dir.is_dir():
        for run in sorted(p for p in game_dir.iterdir() if p.is_dir()):
            try:
                lines = (run / "steps.jsonl").read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    step = json.loads(line)
                except ValueError:
                    continue
                frame = run / step["frame"] if step.get("frame") else None
                samples.append(
                    Sample(
                        run.name,
                        int(step.get("i", 0)),
                        frame,
                        label_of(step),
                        step.get("changed"),
                        str(step.get("seen", "")),
                    )
                )
    return Dataset(safe, samples)
