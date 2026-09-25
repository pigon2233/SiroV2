from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from siro.core.consolidation import ConsolidationCandidate, Consolidator
from siro.core.memory import MemoryKind
from siro.persistence.consolidation import SQLiteConsolidationRepository
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken


class CrashAfterCommit:
    def __init__(self, repository: SQLiteConsolidationRepository) -> None:
        self._repository = repository

    async def start_or_resume(self, *args: object, **kwargs: object) -> tuple[str, int]:
        return await self._repository.start_or_resume(*args, **kwargs)  # type: ignore[arg-type]

    async def commit_candidate(self, *args: object, **kwargs: object) -> bool:
        await self._repository.commit_candidate(*args, **kwargs)  # type: ignore[arg-type]
        os._exit(91)

    async def finish_run(self, *args: object, **kwargs: object) -> None:
        await self._repository.finish_run(*args, **kwargs)  # type: ignore[arg-type]


async def run(path: Path, source_ids: tuple[UUID, ...]) -> None:
    store = SQLiteStore(path)
    await store.initialize()
    candidate = ConsolidationCandidate("crash candidate", MemoryKind.SELF, source_ids, 0.8)
    await Consolidator(CrashAfterCommit(SQLiteConsolidationRepository(store))).run(
        "real-crash", "siro", (candidate,), CancellationToken(), now=datetime.now(UTC)
    )


if __name__ == "__main__":
    asyncio.run(run(Path(sys.argv[1]), tuple(UUID(value) for value in json.loads(sys.argv[2]))))
