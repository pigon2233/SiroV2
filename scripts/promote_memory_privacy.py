# ruff: noqa: RUF001  # User-facing Chinese text uses full-width punctuation.
"""Opt in, category by category, to letting everyday memories reach cloud prompts.

Run in WSL with SIRO stopped. Only the categories 稱呼、喜好、作息 are offered; passwords,
identity and money (report_memory_privacy.SENSITIVE) are never offered and stay local_only.
Nothing changes until you answer yes for a category and confirm the final summary.

A memory's privacy comes from its source events, which are never edited. For each memory
you approve, the script records your consent as a new cloud_allowed `memory.corrected.v1`
event, adds a copy of the memory backed only by that event, and soft-deletes the old
local_only memory with a revision. Every change is appended to
`memory-privacy-promotions.jsonl` next to the database.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))

from report_memory_privacy import (
    LABELS,
    PROMOTABLE,
    MemoryRow,
    default_database,
    open_read_only,
    read_memories,
)

from siro.adapters.data_ownership import (
    DataOwnerBusyError,
    DataOwnerUnavailableError,
    exclusive_data_owner,
)
from siro.contracts.events import (
    MemoryCorrectedEvent,
    MemoryCorrectedPayload,
    Priority,
    Privacy,
)
from siro.core.memory import Memory, MemoryKind
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore

REASON = "owner opted this memory into cloud_allowed"
LOG_NAME = "memory-privacy-promotions.jsonl"

Ask = Callable[[str], str]


def candidates(database: Path) -> dict[str, list[MemoryRow]]:
    """Promotable memories per category; linked or revoked memories are left alone."""
    with closing(open_read_only(database)) as connection:
        memories = read_memories(connection)
    grouped: dict[str, list[MemoryRow]] = {key: [] for key in PROMOTABLE}
    for item in memories:
        if (
            item.category in grouped
            and item.level != "cloud_allowed"
            and not item.linked
            and not item.revoked
        ):
            grouped[item.category].append(item)
    return grouped


def choose(
    grouped: dict[str, list[MemoryRow]], ask: Ask, say: Callable[[str], None]
) -> list[MemoryRow]:
    chosen: list[MemoryRow] = []
    for key in PROMOTABLE:
        items = grouped[key]
        if not items:
            continue
        say(f"\n【{LABELS[key]}】{len(items)} 筆：")
        for index, item in enumerate(items, 1):
            say(f"  {index}. [{item.kind}] {' '.join(item.text.split())}")
        answer = ask(
            f"把「{LABELS[key]}」這 {len(items)} 筆改成 cloud_allowed？[y=全部 / s=逐筆 / N=跳過] "
        )
        answer = answer.strip().lower()
        if answer == "y":
            chosen.extend(items)
        elif answer == "s":
            for index, item in enumerate(items, 1):
                if ask(f"  第 {index} 筆改成 cloud_allowed？[y/N] ").strip().lower() == "y":
                    chosen.append(item)
    return chosen


def consent_event(item: MemoryRow, now: datetime) -> MemoryCorrectedEvent:
    return MemoryCorrectedEvent(
        event_id=uuid4(),
        type="memory.corrected.v1",
        source="owner.privacy_opt_in",
        occurred_at=now,
        received_at=now,
        trace_id="memory-privacy-opt-in",
        sequence=0,
        priority=Priority.BACKGROUND,
        privacy=Privacy.CLOUD_ALLOWED,
        payload=MemoryCorrectedPayload(
            memory_id=UUID(item.memory_id),
            revision=item.revision + 1,
            reason=REASON,
            importance=0.1,
        ),
    )


async def promote(
    database: Path, chosen: list[MemoryRow], *, now: datetime
) -> list[dict[str, str]]:
    repository = SQLiteMemoryRepository(SQLiteStore(database))
    log = database.parent / LOG_NAME
    done: list[dict[str, str]] = []
    for item in chosen:
        event = consent_event(item, now)
        created = datetime.fromisoformat(item.valid_from) if item.valid_from else now
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        replacement = Memory(
            memory_id=uuid4(),
            identity_id=item.identity_id,
            text=item.text,
            source_event_ids=(event.event_id,),
            created_at=created,
            kind=MemoryKind(item.kind),
            person_id=item.person_id,
            confidence=item.confidence,
            valid_to=datetime.fromisoformat(item.valid_to) if item.valid_to else None,
        )
        await repository.add(replacement, event)
        await repository.delete(
            UUID(item.memory_id), reason=f"{REASON}: {replacement.memory_id}", deleted_at=now
        )
        entry = {
            "at": now.isoformat(),
            "old_memory_id": item.memory_id,
            "new_memory_id": str(replacement.memory_id),
            "consent_event_id": str(event.event_id),
            "category": item.category,
        }
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        done.append(entry)
    return done


def run(
    database: Path,
    ask: Ask = input,
    say: Callable[[str], None] = print,
    *,
    now: datetime | None = None,
) -> int:
    grouped = candidates(database)
    if not any(grouped.values()):
        say("沒有可以改成 cloud_allowed 的稱呼、喜好、作息記憶。")
        return 0
    chosen = choose(grouped, ask, say)
    if not chosen:
        say("\n沒有選任何記憶，資料庫沒有變動。")
        return 0
    say(f"\n共 {len(chosen)} 筆會改成 cloud_allowed，之後閒聊走 Groq 時會放進提示。")
    if ask("確定寫入？[y/N] ").strip().lower() != "y":
        say("已取消，資料庫沒有變動。")
        return 0
    done = asyncio.run(promote(database, chosen, now=now or datetime.now(UTC)))
    say(f"完成 {len(done)} 筆，紀錄在 {database.parent / LOG_NAME}。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=None, help="default $SIRO_DATA_DIR/siro.db"
    )
    args = parser.parse_args(argv)
    database = (args.database or default_database()).resolve()
    try:
        with exclusive_data_owner(database):
            return run(database)
    except DataOwnerBusyError:
        print("SIRO 正在使用這個資料庫，請先停止 SIRO 再執行。")
        return 2
    except DataOwnerUnavailableError:
        print("無法取得資料庫的獨占鎖，請在 WSL（Linux）裡執行。")
        return 2
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"讀不到記憶資料庫：{error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
