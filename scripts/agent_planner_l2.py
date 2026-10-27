"""L2: the codex CLI model (SIRO_CODEX_MODEL, default gpt-6-luna) plans and verifies local files."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.coordinator import Coordinator
from siro.services.agent.planning_adapters import CodexPlannerModel, OrchestratorToolPort
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.tools.codex import DEFAULT_MODEL as CODEX_DEFAULT_MODEL
from siro.services.tools.codex import codex_binary, codex_ready
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


async def main() -> int:
    binary = codex_binary()
    if not codex_ready(binary):
        print("SKIP: codex CLI is not installed or logged in")
        return 2
    name = os.environ.get("SIRO_CODEX_MODEL", CODEX_DEFAULT_MODEL)
    model = CodexPlannerModel(binary, name)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.txt").write_text("The launch code word is PINEAPPLE.", encoding="utf-8")
        (root / "b.txt").write_text("Backup contact: Dana, extension 4412.", encoding="utf-8")

        async def read_file(arguments: dict[str, object]) -> object:
            return (root / Path(str(arguments["path"])).name).read_text(encoding="utf-8")

        store = SQLiteStore(root / "siro.db")
        await store.initialize()
        orch = ToolOrchestrator(SQLiteToolProposalRepository(store), {"file.read": read_file})
        port = OrchestratorToolPort(orch, SQLiteAgentRunRepository(store), backend=f"codex:{name}")
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        coordinator = Coordinator(
            model,
            port,
            read_tools={"file.read": schema},
            expected_models=frozenset({name}),
        )
        report = await coordinator.run(
            "l2", "Read a.txt and b.txt, then tell me the code word and the backup contact."
        )
    print(report.to_json())
    return 0 if report.state.value == "completed" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
