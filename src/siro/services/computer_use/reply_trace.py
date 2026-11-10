"""Opt-in bounded local raw-reply evidence. No capture, input, credential or network calls."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from siro.services.computer_use.interface import Decision, DecisionError
from siro.services.computer_use.perception import _SECRET, Observation, allowed_processes
from siro.services.computer_use.process_names import process_in

TRACE_ENV = "SIRO_COMPUTER_TRACE_REPLIES"
MAX_RECORDS = 400
_records = 0


def record_reply(
    text: str,
    observation: Observation,
    env: Mapping[str, str] | None,
    *,
    goal: str,
    model: str,
    error: str = "",
    kind: str = "decision",
) -> None:
    global _records
    values = os.environ if env is None else env
    target = values.get("SIRO_COMPUTER_DUMP_FRAMES", "").strip()
    if values.get(TRACE_ENV, "0") != "1" or not target or _records >= MAX_RECORDS:
        return
    if observation.blocked_reason or observation.focus_is_secret or not observation.image_png_b64:
        return
    if not process_in(observation.process, allowed_processes(values), values):
        return
    try:
        image = base64.b64decode(observation.image_png_b64, validate=True)
        digest = hashlib.sha256(image).hexdigest()
        directory = Path(target)
        directory.mkdir(parents=True, exist_ok=True)
        suffix = ".jpg" if image.startswith(b"\xff\xd8") else ".png"
        image_name = digest + suffix
        image_path = directory / image_name
        if not image_path.exists():
            image_path.write_bytes(image)
        body: dict[str, Any] = {
            "version": 1,
            "kind": kind,
            "process": observation.process,
            "seq": observation.seq,
            "taken_at": observation.taken_at,
            "pid": observation.pid,
            "window_id": observation.window_id,
            "image": image_name,
            "sha256": digest,
            "image_size": observation.image_size,
            "image_rect": observation.image_rect,
            "window_rect": observation.window_rect,
            "screen": observation.screen,
            "model": model,
            "goal": _SECRET.sub("[redacted]", goal[:500]),
            "raw": _SECRET.sub("[redacted]", text[:8192]),
            "error": error[:100],
        }
        _records += 1
        (directory / f"reply-{time.time_ns()}-{observation.seq}-{_records}.json").write_text(
            json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError):
        return  # diagnostic failure never changes control semantics


def parse_reply(
    text: str, observation: Observation, env: Mapping[str, str] | None, *, goal: str, model: str
) -> Decision:
    from siro.services.computer_use.decision import parse_decision

    try:
        result = parse_decision(text)
    except DecisionError as error:
        record_reply(text, observation, env, goal=goal, model=model, error=str(error))
        raise
    record_reply(text, observation, env, goal=goal, model=model)
    return result
