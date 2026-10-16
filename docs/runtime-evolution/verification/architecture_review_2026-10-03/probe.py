"""Isolated audit reproductions; exit 0 confirms defects, not acceptance success."""
import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelChunk, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


class Model:
    name = "audit-synthetic"

    def __init__(self, fail=False):
        self.fail = fail

    async def stream(self, request, cancellation):
        if request.messages[-1].role == "tool":
            yield ModelChunk("text", "done")
        else:
            yield ModelChunk("tool_request", tool_call=ToolCall("call-0", "computer.execute", {}))
            if self.fail:
                raise ConnectionError("synthetic interrupted provider")
        yield ModelChunk("finished")


async def build(path, executor, fail=False):
    store = SQLiteStore(path / "siro.db")
    await store.initialize()
    orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {"computer.execute": executor})
    controller = IntegratedCompanion(
        path, Model(fail), GatewayHub(), MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY, tool_orchestrator=orchestrator,
        runtime_profile="candidate", auto_authorize=lambda: True,
    )
    return controller, orchestrator


async def main():
    results = {}
    with tempfile.TemporaryDirectory(prefix="siro-architecture-audit-") as directory:
        root = Path(directory)
        effects = []

        async def effect(arguments):
            effects.append("effect")
            return {"ok": True}

        controller, orchestrator = await build(root / "reuse", effect)
        await controller.respond("same-session", "first synthetic goal")
        await controller.respond("same-session", "second synthetic goal")
        second = await controller.recovery_readback("same-session")
        assert second["error"] == "duplicate_or_excess_tool_calls" and len(effects) == 1
        results["call_id_reused_next_run"] = {"error": second["error"], "effects": len(effects)}
        results["retained_after_two_terminal_runs"] = {
            "terminated": len(controller._terminated),
            "run_contexts": len(orchestrator._run_contexts),
            "proposal_contexts": len(orchestrator._proposal_contexts),
            "seen_calls": sum(map(len, controller._seen_calls.values())),
        }
        restarted, _ = await build(root / "reuse", effect)
        try:
            await restarted.respond("same-session", "third synthetic goal after restart")
        except sqlite3.IntegrityError as error:
            assert "tool_proposals.session_id, tool_proposals.call_id" in str(error)
            results["call_id_reused_after_restart"] = str(error)
        else:
            raise AssertionError("expected persisted call ID collision")

        effects.clear()
        failed, _ = await build(root / "provider-failure", effect, fail=True)
        await failed.respond("failure", "synthetic goal")
        run = await failed.recovery_readback("failure")
        assert len(effects) == 1 and run["state"] == "completed"
        results["provider_failure_after_tool_intent"] = {"effects": len(effects), "final_state": run["state"]}

        entered, release = asyncio.Event(), asyncio.Event()
        effects.clear()

        async def slow_effect(arguments):
            entered.set()
            await release.wait()
            effects.append("after-cancel")
            return {"ok": True}

        cancelled, _ = await build(root / "cancel", slow_effect)
        task = asyncio.create_task(cancelled.respond("cancel", "synthetic goal"))
        await asyncio.wait_for(entered.wait(), 10)
        await cancelled.cancel("active", "audit", session_id="cancel")
        run = await cancelled.recovery_readback("cancel")
        assert run["state"] == "cancelled" and not task.done()
        release.set()
        await asyncio.wait_for(task, 10)
        assert effects == ["after-cancel"]
        results["arguments_only_executor_cancel"] = {"terminal_before_handler_finished": True, "effects": effects}
    print(json.dumps(results, indent=2))


asyncio.run(main())
