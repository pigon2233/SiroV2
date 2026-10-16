import asyncio
from pathlib import Path
import pytest
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelChunk, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

class Socket:
    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.messages = []
    async def send_json(self, message):
        if message['type'] == 'snapshot':
            self.entered.set()
            await self.release.wait()
        self.messages.append(message)
    async def close(self, **kwargs):
        pass

class Model:
    name = 'independent-synthetic'
    async def stream(self, request, cancellation):
        for i in range(10):
            yield ModelChunk('tool_request', tool_call=ToolCall(str(i), 'computer.execute', {'index': i}))
        yield ModelChunk('finished')

@pytest.mark.asyncio
async def test_actual_websocket_has_no_tool_output_after_terminal(tmp_path: Path):
    store = SQLiteStore(tmp_path / 'siro.db')
    await store.initialize()
    entered = asyncio.Event()
    async def old(arguments):
        raise AssertionError('legacy bypass')
    async def execute(arguments, context):
        if arguments['index'] == 9:
            entered.set()
            await context.cancellation.wait()
            context.check()
        return {'index': arguments['index']}
    orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {'computer.execute': old}, contextual_executors={'computer.execute': execute})
    hub = GatewayHub()
    socket = Socket()
    await hub.connect(socket, {'type': 'snapshot'})
    await socket.entered.wait()
    controller = IntegratedCompanion(tmp_path, Model(), hub, MinimalWebBodyAdapter(WebSocketBodyTransport()), privacy=Privacy.LOCAL_ONLY, tool_orchestrator=orchestrator, runtime_profile='candidate', auto_authorize=lambda: True)
    task = asyncio.create_task(controller.respond('session', 'synthetic goal'))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        await controller.cancel('active', 'stop')
        await task
        socket.release.set()
        for _ in range(100):
            await asyncio.sleep(.001)
        types = [m['type'] for m in socket.messages]
        terminal = types.index('assistant_terminal')
        late = types[terminal + 1:]
        print('ACTUAL_DELIVERY', types, 'LATE', late)
        assert not any(t in {'tool_result', 'tool_started', 'assistant_delta'} for t in late)
    finally:
        socket.release.set()
        await hub.shutdown()
        if not task.done():
            await controller.cancel('active', 'cleanup')
            await task
