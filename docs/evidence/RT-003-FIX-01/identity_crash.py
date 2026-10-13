"""Crash before/after atomic candidate proposal insert/binding; isolated synthetic data."""
import asyncio
import os
from pathlib import Path
import sys

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelChunk, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

class Model:
    name = 'identity-crash'
    async def stream(self, request, cancellation):
        yield ModelChunk('tool_request', tool_call=ToolCall('call-0', 'computer.execute', {}))
        yield ModelChunk('finished')

async def main():
    path, phase = Path(sys.argv[1]), sys.argv[2]
    store = SQLiteStore(path/'siro.db')
    await store.initialize()
    repository = SQLiteToolProposalRepository(store)
    original = repository.put
    async def crashing_put(proposal, **kwargs):
        if phase == 'before':
            os._exit(42)
        await original(proposal, **kwargs)
        os._exit(42)
    repository.put = crashing_put
    async def forbidden(arguments):
        raise AssertionError('effect before crash boundary')
    orchestrator = ToolOrchestrator(repository, {'computer.execute': forbidden})
    controller = IntegratedCompanion(path, Model(), GatewayHub(), MinimalWebBodyAdapter(WebSocketBodyTransport()), privacy=Privacy.LOCAL_ONLY, tool_orchestrator=orchestrator, runtime_profile='candidate', auto_authorize=lambda: True)
    await controller.respond('identity-crash', 'synthetic goal')
    raise AssertionError('did not crash')
asyncio.run(main())
