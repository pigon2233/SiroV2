"""Narrow loader for Codex-authored visual activity packs (siro.visual.pack.v0).

The pack is data only. This module verifies paths, sizes, digests, model
compatibility and curve shape before anything reaches the renderer; it never
executes asset content and never changes the Body v1 asset manifest.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

PACK_SCHEMA = "siro.visual.pack.v0"
RUNTIME_SCHEMA = "siro.visual.pack.runtime.v0"
BODY_IDS = (
    "ParamAngleX",
    "ParamAngleY",
    "ParamAngleZ",
    "ParamBodyAngleX",
    "ParamBodyAngleY",
    "ParamBodyAngleZ",
)
ACTIVITY_KINDS = frozenset(
    {"idle", "attention", "nod", "thinking", "reading_pose", "speaking_pose"}
)
MAX_PACK_BYTES = 64 * 1024
MAX_MOTION_BYTES = 512 * 1024
MAX_VALUE = 90.0
# Points per motion3 segment type: linear, bezier, stepped, inverse stepped.
_SEGMENT_POINTS = {0: 1, 1: 3, 2: 1, 3: 1}


class VisualPackError(ValueError):
    """The pack cannot be used; the reason is safe to show to the owner."""


@dataclass(frozen=True, slots=True)
class VisualActivity:
    kind: str
    duration: float
    loop: bool
    entry_seconds: float
    exit_seconds: float
    resume_seconds: float
    curves: dict[str, tuple[float, ...]]


@dataclass(frozen=True, slots=True)
class VisualPack:
    pack_id: str
    version: str
    digest: str
    activities: dict[str, VisualActivity]

    def renderer_payload(self) -> dict[str, object]:
        return {
            "schema": RUNTIME_SCHEMA,
            "pack_id": self.pack_id,
            "version": self.version,
            "digest": self.digest,
            "body_ids": list(BODY_IDS),
            "gaze": "unsupported",
            "activities": {
                activity.kind: {
                    "duration": activity.duration,
                    "loop": activity.loop,
                    "entry": activity.entry_seconds,
                    "exit": activity.exit_seconds,
                    "resume": activity.resume_seconds,
                    "curves": {key: list(value) for key, value in activity.curves.items()},
                }
                for activity in self.activities.values()
            },
        }


def _read(path: Path, limit: int, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise VisualPackError(f"{label} is missing")
    data = path.read_bytes()
    if len(data) > limit:
        raise VisualPackError(f"{label} exceeds {limit} bytes")
    return data


def _json(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VisualPackError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise VisualPackError(f"{label} must be a JSON object")
    return value


def _seconds(value: object, label: str, *, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise VisualPackError(f"{label} must be a number")
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= maximum:
        raise VisualPackError(f"{label} must be within (0, {maximum}] seconds")
    return number


def _transition(entry: object, key: str, label: str) -> float:
    if not isinstance(entry, dict):
        raise VisualPackError(f"{label} {key} must be an object")
    return _seconds(entry.get("duration"), f"{label} {key} duration", maximum=2.0)


def _segments(raw: object, duration: float, label: str) -> tuple[float, ...]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise VisualPackError(f"{label} has no segments")
    values: list[float] = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, int | float):
            raise VisualPackError(f"{label} has a non-numeric segment value")
        number = float(item)
        if not math.isfinite(number):
            raise VisualPackError(f"{label} has a non-finite segment value")
        values.append(number)
    if values[0] != 0:
        raise VisualPackError(f"{label} must start at time 0")
    last_time = values[0]
    index = 2
    while index < len(values):
        kind = int(values[index])
        if values[index] != kind or kind not in _SEGMENT_POINTS:
            raise VisualPackError(f"{label} has an unknown segment type")
        end = index + 1 + 2 * _SEGMENT_POINTS[kind]
        if end > len(values):
            raise VisualPackError(f"{label} has a truncated segment")
        for point in range(index + 1, end, 2):
            time, value = values[point], values[point + 1]
            if time < last_time - 1e-9 or time > duration + 1e-6:
                raise VisualPackError(f"{label} segment times are out of order")
            if abs(value) > MAX_VALUE:
                raise VisualPackError(f"{label} value exceeds {MAX_VALUE}")
            last_time = time
        index = end
    if index == 2 or abs(last_time - duration) > 1e-6:
        raise VisualPackError(f"{label} must end at the activity duration")
    return tuple(values)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_visual_pack(pack_dir: Path, model_root: Path) -> VisualPack:
    """Validate a pack against the model files that the renderer actually serves."""

    pack_bytes = _read(pack_dir / "pack.json", MAX_PACK_BYTES, "pack.json")
    pack = _json(pack_bytes, "pack.json")
    if pack.get("schema") != PACK_SCHEMA:
        raise VisualPackError(f"pack schema must be {PACK_SCHEMA}")
    pack_id, version = pack.get("pack_id"), pack.get("version")
    if not isinstance(pack_id, str) or not pack_id or not isinstance(version, str) or not version:
        raise VisualPackError("pack_id and version are required")
    compatibility = pack.get("compatibility")
    if not isinstance(compatibility, dict) or not compatibility:
        raise VisualPackError("pack compatibility is required")
    root = model_root.resolve()
    for relative, expected in compatibility.items():
        target = (root / str(relative)).resolve()
        if not target.is_relative_to(root):
            raise VisualPackError("compatibility path escapes the renderer root")
        actual = _sha256(_read(target, 64 * 1024 * 1024, f"model file {relative}"))
        if actual != expected:
            raise VisualPackError(f"model file {relative} does not match the pack")
    activities_raw = pack.get("activities")
    if not isinstance(activities_raw, list) or not activities_raw:
        raise VisualPackError("pack has no activities")
    activities: dict[str, VisualActivity] = {}
    for entry in activities_raw:
        if not isinstance(entry, dict):
            raise VisualPackError("activity entries must be objects")
        kind = entry.get("activity")
        if kind not in ACTIVITY_KINDS or kind in activities:
            raise VisualPackError(f"activity {kind!r} is unknown or repeated")
        assert isinstance(kind, str)
        file_name = entry.get("file")
        if (
            not isinstance(file_name, str)
            or Path(file_name).name != file_name
            or not file_name.endswith(".motion3.json")
        ):
            raise VisualPackError(f"{kind} motion file must be a plain motion3 file name")
        data = _read(pack_dir / file_name, MAX_MOTION_BYTES, f"{kind} motion")
        if _sha256(data) != entry.get("sha256"):
            raise VisualPackError(f"{kind} motion digest does not match the pack")
        if entry.get("write_mask") != list(BODY_IDS):
            raise VisualPackError(f"{kind} write mask must be the six body parameters")
        duration = _seconds(entry.get("duration"), f"{kind} duration", maximum=60.0)
        loop = entry.get("loop")
        if not isinstance(loop, bool):
            raise VisualPackError(f"{kind} loop must be true or false")
        motion = _json(data, f"{kind} motion")
        meta = motion.get("Meta")
        if motion.get("Version") != 3 or not isinstance(meta, dict):
            raise VisualPackError(f"{kind} must be motion3 version 3")
        if meta.get("Duration") != entry.get("duration") or meta.get("Loop") is not loop:
            raise VisualPackError(f"{kind} motion metadata disagrees with the pack")
        curves_raw = motion.get("Curves")
        if not isinstance(curves_raw, list):
            raise VisualPackError(f"{kind} has no curves")
        curves: dict[str, tuple[float, ...]] = {}
        for curve in curves_raw:
            if not isinstance(curve, dict) or curve.get("Target") != "Parameter":
                raise VisualPackError(f"{kind} may only target parameters")
            curve_id = curve.get("Id")
            if curve_id not in BODY_IDS or curve_id in curves:
                raise VisualPackError(f"{kind} writes a parameter outside the body mask")
            assert isinstance(curve_id, str)
            curves[curve_id] = _segments(curve.get("Segments"), duration, f"{kind} {curve_id}")
        if set(curves) != set(BODY_IDS):
            raise VisualPackError(f"{kind} must define every body parameter")
        activities[kind] = VisualActivity(
            kind=kind,
            duration=duration,
            loop=bool(loop),
            entry_seconds=_transition(entry.get("entry"), "entry", kind),
            exit_seconds=_transition(entry.get("exit"), "exit", kind),
            resume_seconds=_transition(entry.get("resume"), "resume", kind),
            curves=curves,
        )
    if "idle" not in activities:
        raise VisualPackError("pack must provide an idle resting activity")
    return VisualPack(
        pack_id=pack_id, version=version, digest=_sha256(pack_bytes), activities=activities
    )
