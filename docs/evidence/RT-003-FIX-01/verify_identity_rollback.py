"""Independent production-path identity/no-replay verification and compatibility rollback rehearsal."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelChunk, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

class Model:
    name='identity-verification'
    async def stream(self, request, cancellation):
        if request.messages[-1].role=='tool':
            assert request.messages[-1].tool_call_id=='call-0'
            yield ModelChunk('text','done')
        else:
            yield ModelChunk('tool_request',tool_call=ToolCall('call-0','computer.execute',{}))
        yield ModelChunk('finished')

async def verify(data):
    store=SQLiteStore(data/'siro.db')
    await store.initialize()
    marker=data/'effect.txt'
    async def effect(arguments):
        with marker.open('a') as f:
            f.write('once\n')
        return {'confirmed':True}
    def build():
        repository=SQLiteToolProposalRepository(store)
        orchestrator=ToolOrchestrator(repository,{'computer.execute':effect})
        controller=IntegratedCompanion(data,Model(),GatewayHub(),MinimalWebBodyAdapter(WebSocketBodyTransport()),privacy=Privacy.LOCAL_ONLY,tool_orchestrator=orchestrator,runtime_profile='candidate',auto_authorize=lambda:True)
        return controller,repository,orchestrator
    controller,repository,orchestrator=build()
    for index in range(3):
        if index==2:
            controller,repository,orchestrator=build()
        await controller.respond('same',f'goal-{index}')
        result=await controller.recovery_readback('same')
        assert result['state']=='completed' and result['calls'][0]['call_id']=='call-0'
    assert marker.read_text()=='once\n'*3
    # Retain a new pending mapped row to prove post-rollback approval guard.
    controller._auto_authorize=lambda:False
    await controller.respond('same','pending')
    pending=await controller.recovery_readback('same')
    proposal_id=pending['calls'][0]['proposal_id']
    proposal=await repository.get(proposal_id)
    assert proposal.call_id=='call-0'
    print('Three runs, one restart, original provider pairing, real file effects=3: PASS')
    return pending,proposal_id

with tempfile.TemporaryDirectory(prefix='siro-identity-rollback-') as directory:
    root=Path(directory)
    pending,proposal_id=asyncio.run(verify(root/'data'))
    expected=root/'expected.json'; expected.write_text(json.dumps(pending))
    previous=root/'previous'
    shutil.copytree('src/siro',previous/'siro')
    # Keep new identity reader/reconciliation/guard; revert caller only, tools disabled.
    shutil.copyfile('docs/evidence/RT-003-FIX-01/before/src/siro/services/presentation/integrated.py',previous/'siro/services/presentation/integrated.py')
    script='''
import asyncio,json,sys
from pathlib import Path
from siro.adapters.body.web import MinimalWebBodyAdapter,WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ModelChunk,Privacy
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import SQLiteToolProposalRepository,ToolOrchestrator
class Text:
 name='safe-rollback-text'
 async def stream(self,request,cancellation):
  yield ModelChunk('text','safe')
  yield ModelChunk('finished')
async def main():
 data=Path(sys.argv[1]); repository=SQLiteToolProposalRepository(SQLiteStore(data/'siro.db'))
 async def forbidden(arguments): raise AssertionError('rollback replay')
 orchestrator=ToolOrchestrator(repository,{'computer.execute':forbidden})
 c=IntegratedCompanion(data,Text(),GatewayHub(),MinimalWebBodyAdapter(WebSocketBodyTransport()),privacy=Privacy.LOCAL_ONLY,runtime_profile='legacy',tool_orchestrator=orchestrator)
 await c.startup()
 assert await c.recovery_readback('same')==json.loads(Path(sys.argv[2]).read_text())
 proposal=await orchestrator.get(sys.argv[3]);assert proposal.call_id=='call-0'
 await orchestrator.resolve(proposal.proposal_id,approved=True,arguments=proposal.arguments)
 try: await orchestrator.execute(proposal.proposal_id)
 except ValueError as e: assert 'recovered' in str(e)
 else: raise AssertionError('rollback accepted old approval')
 await c.respond('text','safe goal')
 assert (await c.recovery_readback('text'))['state']=='completed'
 assert (data/'effect.txt').read_text()=='once\\n'*3
asyncio.run(main())
'''
    outcome=subprocess.run([sys.executable,'-c',script,str(root/'data'),str(expected),proposal_id],env={**os.environ,'PYTHONPATH':str(previous)},capture_output=True,text=True,timeout=20)
    assert outcome.returncode==0,outcome.stderr
    print('Temporary caller rollback + retained reader/guard: original IDs/readback, fenced approval, text restart, zero replay: PASS')
    print('Full old binary without compatibility reader/guard: NOT a safe rollback; deployed rollback NOT VERIFIED')
