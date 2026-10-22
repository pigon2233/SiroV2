"""SIRO's research notes: read back from her own finished runs, never stored as owner facts.

A note is the text she wrote at the end of a completed self run. Its sources are only the
pages the journal shows she actually read, not links the model merely mentions. Whether
she has told the owner about a note is a small local list beside the database.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from siro.persistence.sqlite import SQLiteStore
from siro.services.activity.monitor import redact_url
from siro.services.agent.self_activity import READ_TOOL, SELF_SESSION

MAX_NOTE = 1200
MAX_SHARED = 200
FRESH = timedelta(days=1)


def note_for(c: sqlite3.Connection, run_id: str) -> dict[str, object] | None:
    run = c.execute(
        "SELECT * FROM agent_runs WHERE run_id=? AND session_id=?", (run_id, SELF_SESSION)
    ).fetchone()
    if run is None or run["state"] != "completed":
        return None
    final = c.execute(
        "SELECT payload_json FROM agent_steps WHERE run_id=? AND kind='final' "
        "ORDER BY step_index DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    text = str(json.loads(final[0]).get("text", "")).strip() if final is not None else ""
    if not text:
        return None
    sources: list[dict[str, object]] = []
    for row in c.execute(
        "SELECT observation_json FROM run_journal_calls WHERE run_id=? AND capability=? "
        "AND observation_json IS NOT NULL ORDER BY batch_index, call_index",
        (run_id, READ_TOOL),
    ):
        seen = json.loads(row[0])
        if not isinstance(seen, dict) or "error" in seen:
            continue
        url = redact_url(seen.get("url"))
        if url is not None and url.get("url") and url not in [s["url"] for s in sources]:
            sources.append({"url": url, "title": str(seen.get("title") or "")[:120]})
    # Links in Codex answers are what Codex says it read; SIRO did not open them itself.
    reported: list[dict[str, object]] = []
    for row in c.execute(
        "SELECT observation_json FROM run_journal_calls WHERE run_id=? AND capability=? "
        "AND observation_json IS NOT NULL",
        (run_id, "codex.ask"),
    ):
        seen = json.loads(row[0])
        answer = seen.get("answer") if isinstance(seen, dict) else None
        for raw in re.findall(r"https?://[^\s)\]>」，。]+", str(answer or "")):  # noqa: RUF001
            url = redact_url(raw)
            if url is not None and url.get("url") and url not in reported:
                reported.append(url)
    return {
        "run_id": run_id,
        "topic": run["goal"],
        "created_at": run["created_at"],
        "updated_at": run["updated_at"],
        "text": text[:MAX_NOTE],
        "truncated": len(text) > MAX_NOTE,
        "sources": sources,
        "reported_by_codex": reported[:10],
        "open_questions": [line.strip() for line in text.splitlines() if "待查" in line][:5],
    }


class SelfNotes:
    def __init__(self, store: SQLiteStore, shared_path: Path) -> None:
        self._store = store
        self._path = shared_path
        self._shared = self._load()

    def _load(self) -> list[str]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [item for item in data if isinstance(item, str)][-MAX_SHARED:]

    def _save(self) -> None:
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._shared), encoding="utf-8")
        os.replace(temporary, self._path)

    async def notes(self, limit: int = 20) -> list[dict[str, object]]:
        def read(c: sqlite3.Connection) -> list[dict[str, object]]:
            ids = [
                str(row[0])
                for row in c.execute(
                    "SELECT run_id FROM agent_runs WHERE session_id=? AND state='completed' "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (SELF_SESSION, limit),
                )
            ]
            return [note for run_id in ids if (note := note_for(c, run_id)) is not None]

        notes = await self._store.run_transaction(read)
        return [{**note, "shared": note["run_id"] in self._shared} for note in notes]

    async def note(self, run_id: str) -> dict[str, object] | None:
        found = await self._store.run_transaction(lambda c: note_for(c, run_id))
        return None if found is None else {**found, "shared": run_id in self._shared}

    async def unshared(self, now: datetime | None = None) -> list[str]:
        """Fresh notes with a real source that she has not told the owner about yet."""
        since = ((now or datetime.now(UTC)) - FRESH).isoformat()
        return [
            str(note["run_id"])
            for note in await self.notes()
            if not note["shared"]
            and (note["sources"] or note["reported_by_codex"])
            and str(note["updated_at"]) >= since
        ]

    def mark_shared(self, run_id: str) -> None:
        if run_id not in self._shared:
            self._shared = [*self._shared, run_id][-MAX_SHARED:]
            self._save()


def share_text(note: dict[str, object]) -> tuple[str, str]:
    """The chat message (note plus sources) and one short spoken line."""
    sources = note["sources"]
    assert isinstance(sources, list)
    links = "\n".join(
        f"- {source['title'] or source['url']['url']}：{source['url']['url']}"  # noqa: RUF001
        for source in sources
    )
    text = f"我剛剛自己查了「{note['topic']}」。\n\n{note['text']}"
    if links:
        text += f"\n\n我讀過的頁面：\n{links}"  # noqa: RUF001
    reported = note.get("reported_by_codex") or []
    assert isinstance(reported, list)
    if reported:
        text += "\n\nCodex 提供的來源（我沒有直接打開）：\n" + "\n".join(  # noqa: RUF001
            f"- {item['url']}" for item in reported
        )
    return text, f"我剛剛查了{note['topic']}，整理在對話裡了。"  # noqa: RUF001
