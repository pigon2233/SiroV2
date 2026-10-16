"""Synthetic cross-task check; no provider network or private database access."""
import asyncio
import json
import tempfile
from pathlib import Path
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelChunk, ToolCall, Privacy
from siro.services.agent.context import ContextBudgetModel
from siro.services.agent.native_context import GPTOSSBudget
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

class Model:
    name = 'synthetic-gpt-oss'
    def __init__(self):
        self.calls = 0
    async def stream(self, request, cancellation):
        self.calls += 1
        if self.calls == 1:
            for n in range(2):
                yield ModelChunk('tool_request', tool_call=ToolCall(f'call-{n}', 'computer.execute', {}))
        else:
            yield ModelChunk('text', 'done')
        yield ModelChunk('finished')

async def case(root, native):
    model = Model()
    adapter = OpenAICompatibleAdapter(base_url='https://api.groq.com/openai', api_key='synthetic-unused', model='openai/gpt-oss-20b')
    wrapped = ContextBudgetModel(model, max_bytes=65536, token_budget=GPTOSSBudget(Path('.siro-data/tokenizers/gpt-oss-20b'), adapter.request_payload) if native else None)
    effects = []
    async def handler(arguments):
        effects.append('synthetic-effect')
        return {'ok': True}
    store = SQLiteStore(root / 'siro.db')
    await store.initialize()
    orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {'computer.execute': handler})
    controller = IntegratedCompanion(root, wrapped, GatewayHub(), MinimalWebBodyAdapter(WebSocketBodyTransport()), privacy=Privacy.CLOUD_ALLOWED, runtime_profile='candidate', tool_orchestrator=orchestrator, auto_authorize=lambda: True)
    await controller.respond('audit', 'synthetic two-tool goal')
    run = await controller.recovery_readback('audit')
    return {'native': native, 'provider_calls': model.calls, 'effects': len(effects), 'state': run['state'], 'error': run['error']}

async def main():
    with tempfile.TemporaryDirectory(prefix='siro-review-') as d:
        results = [await case(Path(d)/str(native), native) for native in (False, True)]
    assert results[0]['state'] == 'completed'
    assert results[1]['effects'] == 2 and results[1]['error'] == 'ContextBudgetUnavailable'
    print(json.dumps(results, indent=2))
asyncio.run(main())
