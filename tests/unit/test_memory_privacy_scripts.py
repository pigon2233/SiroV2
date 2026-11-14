"""Memory privacy report (read-only) and the owner's per-category cloud opt-in."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from uuid import UUID, uuid4

import pytest

from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryKind
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository

NOW = datetime(2026, 11, 14, 4, tzinfo=UTC)
SCRIPTS = Path(__file__).parents[2] / "scripts"


def _load(name: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _source(text: str, privacy: Privacy = Privacy.LOCAL_ONLY) -> UserTextEvent:
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="synthetic",
        occurred_at=NOW,
        received_at=NOW,
        trace_id="synthetic",
        session_id="synthetic",
        turn_id=str(uuid4()),
        sequence=1,
        priority=Priority.INTERACTIVE,
        privacy=privacy,
        payload=UserTextPayload(text=text, language="zh"),
    )


async def _database(path: Path) -> dict[str, UUID]:
    store = SQLiteStore(path)
    await store.initialize()
    await IdentityService(SQLiteIdentityRepository(store)).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="synthetic",
            core_values=("honesty",),
            creator_relationship="synthetic owner",
        ),
        now=NOW,
    )
    repo = SQLiteMemoryRepository(store)
    texts = {
        "name": "主人希望我叫她 kiwi",
        "like": "主人喜歡 bluetea",
        "sleep": "主人每天十二點睡覺 nightowl",
        "secret": "主人的銀行密碼是 hunter2",
        "other": "主人提到 festival",
        "cloud": "主人喜歡 greentea",
        "parent": "主人喜歡 redtea",
        "child": "主人偏好 redtea 冷的",
    }
    ids: dict[str, UUID] = {}
    for key, text in texts.items():
        privacy = Privacy.CLOUD_ALLOWED if key == "cloud" else Privacy.LOCAL_ONLY
        event = _source(text, privacy)
        memory = Memory(uuid4(), "siro", text, (event.event_id,), NOW, kind=MemoryKind.EPISODIC)
        await repo.add(memory, event)
        ids[key] = memory.memory_id
    await store.run_transaction(
        lambda c: c.execute(
            "INSERT INTO memory_derivations(parent_memory_id,child_memory_id,revision) "
            "VALUES(?,?,1)",
            (str(ids["parent"]), str(ids["child"])),
        )
    )
    return ids


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_report_counts_levels_and_categories_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _load("report_memory_privacy", monkeypatch)
    database = tmp_path / "siro.db"
    asyncio.run(_database(database))
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = _digest(database)
    result = report.report(database, examples=2)
    assert _digest(database) == before
    assert result["read_only"] is True
    assert result["total"] == 8
    assert result["by_level"]["local_only"] == 7
    assert result["by_level"]["cloud_allowed"] == 1
    table = result["by_level_and_category"]
    assert table["local_only/sensitive"]["count"] == 1
    assert table["local_only/name"]["count"] == 1
    assert table["local_only/routine"]["count"] == 1
    assert table["local_only/other"]["count"] == 1
    assert result["promotable"] == {"name": 1, "preference": 1, "routine": 1}
    assert result["linked_skipped"] == 2
    assert "唯讀" in report.render(result)
    assert report.categorize("我的身分證字號喜歡寫在這") == "sensitive"
    assert report.categorize("我的 api key 是 abc") == "sensitive"
    assert report.level(["local_only", "cloud_allowed"]) == "local_only"
    assert report.level(["trusted_lan", "cloud_allowed"]) == "trusted_lan"
    assert report.level([None]) == "unknown"
    assert report.level([]) == "no_source"
    assert report.main(["--database", str(tmp_path / "missing.db")]) == 2


def test_opt_in_promotes_only_confirmed_categories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    promote = _load("promote_memory_privacy", monkeypatch)
    report = sys.modules["report_memory_privacy"]
    database = tmp_path / "siro.db"
    ids = asyncio.run(_database(database))
    prompts: list[str] = []
    said: list[str] = []
    # name: yes; preference: per item, decline; routine: skip; final: yes.
    answers = iter(["y", "s", "n", "", "y"])

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    assert promote.run(database, ask, said.append, now=NOW) == 0
    text = "\n".join(said)
    assert "hunter2" not in text
    assert "redtea" not in text
    assert "greentea" not in text

    repo = SQLiteMemoryRepository(SQLiteStore(database))

    async def cloud(query: str) -> list[Memory]:
        return await repo.search("siro", query, route_privacy=Privacy.CLOUD_ALLOWED)

    async def local(query: str) -> list[Memory]:
        return await repo.search("siro", query, route_privacy=Privacy.LOCAL_ONLY)

    promoted = asyncio.run(cloud("kiwi"))
    assert [item.text for item in promoted] == ["主人希望我叫她 kiwi"]
    assert promoted[0].memory_id != ids["name"]
    assert asyncio.run(cloud("bluetea")) == []
    assert asyncio.run(cloud("nightowl")) == []
    assert asyncio.run(cloud("hunter2")) == []
    assert len(asyncio.run(local("kiwi"))) == 1
    assert len(asyncio.run(local("bluetea"))) == 1
    revisions = asyncio.run(repo.revisions(ids["name"]))
    assert revisions[-1].reason.startswith(promote.REASON)
    with sqlite3.connect(database) as connection:
        deleted = connection.execute(
            "SELECT status FROM memories WHERE memory_id = ?", (str(ids["name"]),)
        ).fetchone()
        assert deleted == ("deleted",)
        privacy = connection.execute(
            "SELECT json_extract(envelope_json,'$.privacy'),type FROM events "
            "WHERE json_extract(envelope_json,'$.source') = 'owner.privacy_opt_in'"
        ).fetchall()
        assert privacy == [("cloud_allowed", "memory.corrected.v1")]
    log = [
        json.loads(line)
        for line in (tmp_path / promote.LOG_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert [entry["old_memory_id"] for entry in log] == [str(ids["name"])]
    assert report.report(database)["promotable"] == {"preference": 1, "routine": 1}


def test_opt_in_changes_nothing_without_final_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    promote = _load("promote_memory_privacy", monkeypatch)
    database = tmp_path / "siro.db"
    asyncio.run(_database(database))
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = _digest(database)
    answers = iter(["y", "y", "y", "n"])
    said: list[str] = []
    assert promote.run(database, lambda _prompt: next(answers), said.append, now=NOW) == 0
    assert "已取消" in said[-1]
    assert _digest(database) == before
    assert not (tmp_path / promote.LOG_NAME).exists()
