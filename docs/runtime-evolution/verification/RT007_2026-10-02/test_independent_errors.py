from __future__ import annotations
import asyncio
from pathlib import Path
import pytest
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelChunk, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools import orchestrator as mod

class Hub(GatewayHub):
    def __init__(self):
        super().__init__()
        self.events = []
    async def broadcast(self, message, *, urgent=False):
        self.events.append(message)

@pytest.mark.asyncio
@pytest.mark.parametrize('cause', ['schema', 'revoked'])
async def test_rejected_model_tool_has_terminal_run(tmp_path: Path, cause: str):
    enabled = True
    requests = []
    executed = []
    class Model:
        name = 'independent-error-fixture'
        async def stream(self, request, cancellation):
            nonlocal enabled
            requests.append(request)
            if len(requests) == 1:
                if cause == 'revoked':
                    enabled = False
                args = {'argv': []} if cause == 'schema' else {'argv': ['synthetic']}
                yield ModelChunk('tool_request', tool_call=ToolCall('call', 'computer.execute', args))
            else:
                yield ModelChunk('text', 'tool failure acknowledged')
            yield ModelChunk('finished')
    async def execute(arguments):
        executed.append(arguments)
        if not arguments.get('argv'):
            raise ValueError('invalid argv rejected by existing handler')
        return {}
    store = SQLiteStore(tmp_path/'siro.db')
    await store.initialize()
    extra = {}
    # Before RT-007: old handler rejects malformed argv inside execute, resulting
    # in a FAILED observation and normal continuation. After: real catalog path.
    if hasattr(mod, 'ToolCatalog'):
        extra['catalog'] = mod.ToolCatalog((mod.ToolDescriptor('computer.execute', mod.DEFAULT_MODEL_TOOLS[1], execute, lambda: enabled, 'python.argv', 'computer'),))
    subject = mod.ToolOrchestrator(mod.SQLiteToolProposalRepository(store), {'computer.execute': execute}, **extra)
    hub = Hub()
    controller = IntegratedCompanion(tmp_path, Model(), hub, MinimalWebBodyAdapter(WebSocketBodyTransport()), privacy=Privacy.LOCAL_ONLY, tool_orchestrator=subject, runtime_profile='candidate', auto_authorize=lambda: True)
    error = None
    try:
        await controller.respond('session', 'synthetic goal')
    except Exception as exc:
        error = type(exc).__name__
    row = await store.run_transaction(lambda c:c.execute('SELECT state,error FROM agent_runs').fetchone())
    terminal = [e for e in hub.events if e['type'] == 'assistant_terminal']
    print('ERROR_PATH', {'cause':cause, 'raised':error, 'run_state':row[0], 'terminal_count':len(terminal), 'handler_calls':len(executed), 'model_rounds':len(requests)})
    await hub.shutdown()
    assert len(terminal) == 1, 'Rejected model request left the run without terminal UI'
    assert row[0] in {'failed','completed','cancelled'}, 'Rejected model request left persistent run active'
