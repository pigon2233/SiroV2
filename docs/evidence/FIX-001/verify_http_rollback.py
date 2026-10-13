"""Separate HTTP behavior verification and isolated source rollback reader rehearsal."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from fastapi.testclient import TestClient
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelChunk, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub, create_app
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


class Model:
    name = "http-verification"

    def __init__(self, continuation):
        self.rounds = 0
        self.continuation = continuation

    async def stream(self, request, cancellation):
        self.rounds += 1
        yield ModelChunk("text", "partial")
        yield ModelChunk("tool_request", tool_call=ToolCall(f"http-{self.rounds}", "computer.execute", {}))
        if self.continuation and self.rounds == 1:
            yield ModelChunk("finished")
        else:
            raise ConnectionError("isolated disconnect")


with tempfile.TemporaryDirectory(prefix="siro-fix001-") as temp:
    root = Path(temp)
    for profile in ("legacy", "candidate"):
        for continuation in (False, True):
            data = root / f"{profile}-{continuation}"
            model = Model(continuation)
            store = SQLiteStore(data / "siro.db")
            marker = data / "effect.txt"

            async def effect(arguments):
                with marker.open("a") as f:
                    f.write("confirmed\n")
                return {"confirmed": True}

            orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {"computer.execute": effect})
            controller = IntegratedCompanion(data, model, GatewayHub(), MinimalWebBodyAdapter(WebSocketBodyTransport()), privacy=Privacy.LOCAL_ONLY, runtime_profile=profile, tool_orchestrator=orchestrator, auto_authorize=lambda: True)
            app = create_app(on_startup=controller.startup, on_turn=controller.respond, on_recovery=controller.recovery_readback)
            with TestClient(app) as client:
                token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()["token"]
                headers = {"authorization": f"Bearer {token}"}
                response = client.post("/v1/conversations/http/turns", headers=headers, json={"text": "synthetic goal"})
                assert response.status_code == 200, response.text
                readback = client.get("/v1/agent-runs/http", headers=headers)
                assert readback.status_code == 200
                result = readback.json()
                assert result["state"] == "failed" and result["error"] == "ConnectionError"
                assert model.rounds == 1 + int(continuation)
                assert (marker.read_text() if marker.exists() else "") == ("confirmed\n" if continuation else "")
            print(f"HTTP {profile} continuation={continuation}: PASS")
            if profile == "candidate" and continuation:
                rollback_data, rollback_result = data, result
    # Prior caller source only, preserving schema/reader/guard. No dispatch after rollback.
    previous = root / "previous"
    shutil.copytree("src/siro", previous / "siro")
    for relative, snapshot in [("services/presentation/integrated.py", "integrated.py"), ("core/companion.py", "companion.py")]:
        shutil.copyfile(Path("docs/evidence/FIX-001/before") / snapshot, previous / "siro" / relative)
    expected = root / "expected.json"
    expected.write_text(json.dumps(rollback_result))
    script = '''
import asyncio, json, sys
from pathlib import Path
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.ports.models import ModelChunk, Privacy
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
class TextOnly:
 name='rollback-text-only'
 async def stream(self, request, cancellation):
  yield ModelChunk('text','safe text')
  yield ModelChunk('finished')
async def main():
 c=IntegratedCompanion(Path(sys.argv[1]),TextOnly(),GatewayHub(),MinimalWebBodyAdapter(WebSocketBodyTransport()),privacy=Privacy.LOCAL_ONLY,runtime_profile='legacy')
 await c.startup()
 assert await c.recovery_readback('http') == json.loads(Path(sys.argv[2]).read_text())
 await c.respond('fresh-text','synthetic text goal')
 assert (await c.recovery_readback('fresh-text'))['state']=='completed'
 assert (Path(sys.argv[1])/'effect.txt').read_text()=='confirmed\\n'
asyncio.run(main())
'''
    outcome = subprocess.run([sys.executable, "-c", script, str(rollback_data), str(expected)], env={**os.environ, "PYTHONPATH": str(previous)}, capture_output=True, text=True, timeout=20)
    assert outcome.returncode == 0, outcome.stderr
    print("Temporary prior-source legacy readback / text-only restart / unchanged effect: PASS")
    print("Deployed rollback and re-enabling failed-intent tool dispatch: NOT VERIFIED / prohibited")
