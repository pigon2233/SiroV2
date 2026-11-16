"""Two OS processes share one Claude budget file without lost or torn updates."""

from __future__ import annotations

import asyncio
import json
import multiprocessing
from pathlib import Path
from typing import Any

from siro.adapters.models.claude_budget import ClaudeBudget

PER_PROCESS = 60
LIMIT = 2 * PER_PROCESS


def _hammer(path: str, name: str, start: Any, results: Any) -> None:
    """Reserve PER_PROCESS slots and peek between each, reporting what was seen."""
    budget = ClaudeBudget(Path(path), limit=LIMIT)

    async def run() -> dict[str, int]:
        seen = {"allowed": 0, "refused": 0, "unreadable": 0}
        for _ in range(PER_PROCESS):
            view = await budget.try_reserve(name)
            if view.allowed:
                seen["allowed"] += 1
            elif view.reason == "unreadable":
                seen["unreadable"] += 1
            else:
                seen["refused"] += 1
            if budget.peek().reason == "unreadable":
                seen["unreadable"] += 1
        return seen

    start.wait(30)
    try:
        results.put((name, asyncio.run(run())))
    except BaseException as error:
        results.put((name, {"error": repr(error)}))
        raise


def test_two_processes_lose_no_updates_and_never_tear_the_file(tmp_path: Path) -> None:
    path = tmp_path / "claude-budget.json"
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    workers = [
        context.Process(target=_hammer, args=(str(path), f"proc{index}", start, results))
        for index in range(2)
    ]
    for worker in workers:
        worker.start()
    start.set()
    reports = dict(results.get(timeout=120) for _ in workers)
    for worker in workers:
        worker.join(timeout=30)
        assert worker.exitcode == 0

    for name, seen in reports.items():
        assert seen == {"allowed": PER_PROCESS, "refused": 0, "unreadable": 0}, name

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert len(stored["calls"]) == LIMIT
    assert sorted(set(stored["callers"])) == ["proc0", "proc1"]
    assert stored["callers"].count("proc0") == PER_PROCESS
    assert stored["callers"].count("proc1") == PER_PROCESS
    assert not list(tmp_path.glob("*.tmp"))

    last = asyncio.run(ClaudeBudget(path, limit=LIMIT).try_reserve("after"))
    assert not last.allowed
    assert last.reason == "budget"
