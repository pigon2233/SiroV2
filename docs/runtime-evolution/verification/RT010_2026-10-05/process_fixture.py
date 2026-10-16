"""One fresh OS process per synthetic turn; real controller/Core/SQLite."""
import asyncio
import json
import sys
from pathlib import Path
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.ports.models import ModelChunk, Privacy
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion

directory, session, goal, answer = sys.argv[1:]

class Model:
    name = "independent-local"
    async def stream(self, request, cancellation):
        (Path(directory) / "request.json").write_text(json.dumps(
            [{"role": m.role, "content": m.content} for m in request.messages]))
        yield ModelChunk("text", answer)
        yield ModelChunk("finished")

async def main():
    controller = IntegratedCompanion(Path(directory), Model(), GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY, runtime_profile="candidate")
    await controller.startup()
    await controller.respond(session, goal)
    row = await controller.recovery_readback(session)
    assert row["state"] == "completed" and row["backend"] == "independent-local"

asyncio.run(main())
