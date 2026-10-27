"""L2: real cloud model plans/verifies over a local text file. Needs SIRO_OPENAI_API_KEY/MODEL."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.coordinator import Coordinator
from siro.services.agent.planning_adapters import CloudPlannerModel, OrchestratorToolPort
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


async def main() -> int:
    key, name = os.environ.get("SIRO_OPENAI_API_KEY"), os.environ.get("SIRO_OPENAI_MODEL")
    if not key or not name:
        print("SKIP: SIRO_OPENAI_API_KEY and SIRO_OPENAI_MODEL are required")
        return 2
    model = OpenAICompatibleAdapter(
        base_url=os.environ.get("SIRO_OPENAI_BASE_URL", "https://api.groq.com/openai"),
        api_key=key,
        model=name,
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.txt").write_text("The launch code word is PINEAPPLE.", encoding="utf-8")
        (root / "b.txt").write_text("Backup contact: Dana, extension 4412.", encoding="utf-8")

        async def read_file(arguments: dict[str, object]) -> object:
            return (root / Path(str(arguments["path"])).name).read_text(encoding="utf-8")

        store = SQLiteStore(root / "siro.db")
        await store.initialize()
        orch = ToolOrchestrator(SQLiteToolProposalRepository(store), {"file.read": read_file})
        port = OrchestratorToolPort(orch, SQLiteAgentRunRepository(store), backend=f"cloud:{name}")
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        coordinator = Coordinator(
            CloudPlannerModel(model),
            port,
            read_tools={"file.read": schema},
            expected_models=frozenset({model.name}),
        )
        report = await coordinator.run(
            "l2", "Read a.txt and b.txt, then tell me the code word and the backup contact."
        )
    print(report.to_json())
    return 0 if report.state.value == "completed" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
