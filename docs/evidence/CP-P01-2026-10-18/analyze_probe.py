"""Summarise renderer_probe.py output: continuity, mouth release, breath, expression, events."""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

BODY = ["ParamAngleX", "ParamAngleY", "ParamAngleZ", "ParamBodyAngleX", "ParamBodyAngleY",
        "ParamBodyAngleZ"]


def window(frames: list[dict], start: float, end: float) -> list[dict]:
    return [row for row in frames if start <= row["t"] < end]


def main(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text())
    frames, marks, events = data["frames"], data["marks"], data["events"]
    dts = [b["t"] - a["t"] for a, b in zip(frames, frames[1:], strict=False)]
    worst = {}
    for id_ in BODY:
        deltas = [abs(b[id_] - a[id_]) for a, b in zip(frames, frames[1:], strict=False)]
        top = max(range(len(deltas)), key=deltas.__getitem__)
        worst[id_] = {
            "max_frame_delta": round(deltas[top], 4),
            "at_t": frames[top + 1]["t"],
            "activity": frames[top + 1]["activity"],
            "median_frame_delta": round(statistics.median(deltas), 4),
        }
    switches = []
    for mark in marks:
        t = mark["frame_t"]
        before = window(frames, t - 0.2, t)
        after = window(frames, t, t + 0.6)
        if not before or not after:
            continue
        jump = max(abs(after[0][i] - before[-1][i]) for i in BODY)
        steps = max(
            abs(b[i] - a[i]) for a, b in zip([before[-1], *after], after, strict=False) for i in BODY
        )
        prior = (
            max(abs(before[-1][i] - before[-2][i]) for i in BODY) if len(before) > 1 else None
        )
        switches.append({"label": mark["label"], "t": t, "first_frame_jump": round(jump, 4),
                         "prior_frame_step": None if prior is None else round(prior, 4),
                         "max_step_next_0.6s": round(steps, 4)})
    mark_t = {mark["label"]: mark["frame_t"] for mark in marks}
    speech1, cancel, speech2 = mark_t["speech 1"], mark_t["cancel"], mark_t["speech 2"]
    mouth = {}
    for label, (a, b) in {
        "speech1_before_cancel": (speech1, cancel),
        "0-0.3s_after_cancel": (cancel + 0.02, cancel + 0.3),
        "0.3-1.5s_after_cancel": (cancel + 0.3, speech2),
        "speech2": (speech2 + 0.02, speech2 + 2.4),
    }.items():
        values = [row["ParamMouthOpenY"] for row in window(frames, a, b)]
        mouth[label] = {"min": round(min(values), 4), "max": round(max(values), 4),
                        "nonzero": sum(v > 1e-3 for v in values), "n": len(values)}
    breath = [row["ParamBreath"] for row in frames]
    timeline = []
    for row in frames:
        if not timeline or timeline[-1][1] != row["activity"]:
            timeline.append((row["t"], row["activity"]))
    summary = {
        "frames": len(frames),
        "median_dt_s": round(statistics.median(dts), 4),
        "max_dt_s": round(max(dts), 4),
        "page_errors": data["page_errors"],
        "activity_timeline": timeline,
        "events": Counter(f"{e['event']}:{e.get('activity')}:{e.get('reason', '')}" for e in events),
        "body_continuity": worst,
        "switches": switches,
        "mouth": mouth,
        "breath": {"min": round(min(breath), 4), "max": round(max(breath), 4)},
        "expressions": sorted({row["expression"] for row in frames}),
    }
    return summary


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1])), ensure_ascii=False, indent=1, default=list))
