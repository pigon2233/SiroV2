"""Per-game play notes: what worked, what did not, how the controls behave.

Notes are short lessons written after a run (see ``reflect``) and shown to the decider the next
time the same program is in front. They are plain data: never executed, scrubbed of secret-looking
text, capped in number and length, and the owner can read or delete them.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from siro.services.computer_use.decision import StepRecord, cloud_screen_allowed
from siro.services.computer_use.perception import _SECRET
from siro.services.tools.claude import ClaudeUnavailable, ask_claude

MAX_NOTES = 20
MAX_NOTE_CHARS = 200
MAX_NEW_NOTES = 5
PLAYBOOK_DIR_NAME = "computer-playbooks"


@dataclass(frozen=True, slots=True)
class Note:
    text: str
    run_id: str
    at: float


def playbook_dir(env: dict[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    return Path(values.get("SIRO_DATA_DIR") or ".siro-data") / PLAYBOOK_DIR_NAME


def _clean(text: str) -> str:
    return _SECRET.sub("[redacted]", " ".join(text.split()))[:MAX_NOTE_CHARS].strip()


def _key(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


class PlaybookStore:
    def __init__(self, directory: Path, clock: Callable[[], float] = time.time) -> None:
        self._dir = directory
        self._clock = clock

    def _path(self, game: str) -> Path:
        safe = re.sub(r"[^a-z0-9._-]", "_", game.strip().lower())[:60] or "unknown"
        return self._dir / f"{safe}.json"

    def notes(self, game: str) -> list[Note]:
        try:
            raw = json.loads(self._path(game).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        out: list[Note] = []
        for item in raw if isinstance(raw, list) else []:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                out.append(
                    Note(item["text"], str(item.get("run_id", "")), float(item.get("at", 0)))
                )
        return out

    def texts(self, game: str) -> list[str]:
        return [n.text for n in self.notes(game)]

    def add(self, game: str, texts: Sequence[str], run_id: str) -> int:
        """Add new lessons (deduplicated, scrubbed); the oldest fall off past MAX_NOTES."""
        current = self.notes(game)
        seen = {_key(n.text) for n in current}
        added = 0
        for text in texts[:MAX_NEW_NOTES]:
            cleaned = _clean(str(text))
            if len(cleaned) < 8 or _key(cleaned) in seen:
                continue
            seen.add(_key(cleaned))
            current.append(Note(cleaned, run_id, self._clock()))
            added += 1
        if added:
            self._write(game, current[-MAX_NOTES:])
        return added

    def remove(self, game: str, index: int) -> bool:
        current = self.notes(game)
        if not 0 <= index < len(current):
            return False
        del current[index]
        self._write(game, current)
        return True

    def clear(self, game: str) -> None:
        self._path(game).unlink(missing_ok=True)

    def _write(self, game: str, notes: Sequence[Note]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = [{"text": n.text, "run_id": n.run_id, "at": n.at} for n in notes]
        fd, tmp = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        os.replace(tmp, self._path(game))


def notes_block(texts: Sequence[str]) -> str:
    if not texts:
        return ""
    lines = "\n".join(f"- {t}" for t in texts)
    header = "Notes from earlier runs on this program (hints, not facts about the current screen):"
    return f"\n\n{header}\n{lines}"


REFLECT_PROMPT = (
    "You review one finished run of an AI that controls a game or app on the owner's PC. "
    "Write at most {max_new} NEW short, reusable lessons for next time (controls that work or do "
    "not, how screens behave, mistakes to avoid, what a good next step looks like). Each lesson is "
    "one sentence under {chars} characters, specific to this program, with no personal data. "
    "Skip anything already in the existing notes. If nothing useful was learned, return an empty "
    'list. Reply with JSON only: {{"notes":["..."]}}\n'
    "Program: {game}\nGoal: {goal}\nHow it ended: {state} ({reason})\n"
    "Existing notes:\n{existing}\nSteps (saw | did | outcome | screen changed):\n{steps}"
)


def parse_notes(text: str) -> list[str]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        raw = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return []
    notes = raw.get("notes") if isinstance(raw, dict) else None
    if not isinstance(notes, list):
        return []
    return [str(n) for n in notes if isinstance(n, str)][:MAX_NEW_NOTES]


def reflect_prompt(
    game: str,
    goal: str,
    state: str,
    reason: str,
    existing: Sequence[str],
    steps: Sequence[StepRecord],
) -> str:
    step_lines = "\n".join(
        f"{s.step}. {s.seen or '-'} | {s.action} | {s.outcome} | {s.screen_changed}"
        for s in steps[-30:]
    )
    return REFLECT_PROMPT.format(
        max_new=MAX_NEW_NOTES,
        chars=MAX_NOTE_CHARS,
        game=game,
        goal=goal[:300],
        state=state,
        reason=reason[:200],
        existing="\n".join(f"- {t}" for t in existing) or "(none)",
        steps=step_lines or "(no steps)",
    )


class ClaudeReflector:
    """Writes lessons with the logged-in `claude` CLI, text only (no screenshots)."""

    def __init__(self, *, run: object | None = None, env: dict[str, str] | None = None) -> None:
        self._run = run
        self._env = env

    async def reflect(
        self,
        game: str,
        goal: str,
        state: str,
        reason: str,
        existing: Sequence[str],
        steps: Sequence[StepRecord],
    ) -> list[str]:
        if not cloud_screen_allowed(self._env):
            return []
        prompt = reflect_prompt(game, goal, state, reason, existing, steps)
        kwargs: dict[str, object] = {"search": False, "prefix": "", "limit": 12000}
        if self._run is not None:
            kwargs["run"] = self._run
        try:
            answer = await ask_claude({"task": prompt}, **kwargs)  # type: ignore[arg-type]
        except (ClaudeUnavailable, ValueError, OSError):
            return []
        return parse_notes(str(answer.get("answer", "")))
