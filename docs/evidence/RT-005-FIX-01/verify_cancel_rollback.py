"""Separate real-file cancellation verification and isolated prior-source rollback rehearsal."""
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
    name='cancel-verification'
    async def stream(self, request, cancellation):
        yield ModelChunk('tool_request',tool_call=ToolCall('call-0','computer.execute',{}))
        yield ModelChunk('finished')

async def verify(data):
    store=SQLiteStore(data/'siro.db'); await store.initialize()
    entered,release=asyncio.Event(),asyncio.Event()
    async def handler(arguments):
        entered.set()
        try:
            await release.wait()
            (data/'effect.txt').write_text('unexpected effect')
            return {'ok':True}
        finally:
            await asyncio.sleep(.02)
            (data/'cleanup.txt').write_text('cleaned')
    orchestrator=ToolOrchestrator(SQLiteToolProposalRepository(store),{'computer.execute':handler})
    controller=IntegratedCompanion(data,Model(),GatewayHub(),MinimalWebBodyAdapter(WebSocketBodyTransport()),privacy=Privacy.LOCAL_ONLY,tool_orchestrator=orchestrator,runtime_profile='candidate',auto_authorize=lambda:True)
    task=asyncio.create_task(controller.respond('cancel','synthetic goal'))
    await asyncio.wait_for(entered.wait(),10)
    start=asyncio.get_running_loop().time()
    await controller.cancel('active','stop',session_id='cancel')
    elapsed=asyncio.get_running_loop().time()-start
    assert elapsed<5 and (data/'cleanup.txt').read_text()=='cleaned'
    release.set();await task
    assert not (data/'effect.txt').exists()
    result=await controller.recovery_readback('cancel')
    assert result['state']=='cancelled'
    assert not any(orchestrator._active.values())
    print(f'Real file cleanup precedes terminal; no effect/new dispatch, elapsed={elapsed:.3f}s: PASS')
    return result

with tempfile.TemporaryDirectory(prefix='siro-cancel-rollback-') as directory:
    root=Path(directory); result=asyncio.run(verify(root/'data'))
    expected=root/'expected.json';expected.write_text(json.dumps(result))
    previous=root/'previous';shutil.copytree('src/siro',previous/'siro')
    for path in ['services/tools/orchestrator.py','services/presentation/gateway.py','adapters/browser.py']:
        shutil.copyfile(Path('docs/evidence/RT-005-FIX-01/before/src/siro')/path,previous/'siro'/path)
    script='''
import asyncio,json,sys
from pathlib import Path
from siro.adapters.body.web import MinimalWebBodyAdapter,WebSocketBodyTransport
from siro.ports.models import ModelChunk,Privacy
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
class Text:
 name='safe-rollback-text'
 async def stream(self,request,cancellation):
  yield ModelChunk('text','safe')
  yield ModelChunk('finished')
async def main():
 data=Path(sys.argv[1])
 c=IntegratedCompanion(data,Text(),GatewayHub(),MinimalWebBodyAdapter(WebSocketBodyTransport()),privacy=Privacy.LOCAL_ONLY,runtime_profile='legacy')
 await c.startup()
 assert await c.recovery_readback('cancel')==json.loads(Path(sys.argv[2]).read_text())
 await c.respond('new-text','synthetic safe goal')
 assert (await c.recovery_readback('new-text'))['state']=='completed'
 assert (data/'cleanup.txt').read_text()=='cleaned' and not (data/'effect.txt').exists()
asyncio.run(main())
'''
    outcome=subprocess.run([sys.executable,'-c',script,str(root/'data'),str(expected)],env={**os.environ,'PYTHONPATH':str(previous)},capture_output=True,text=True,timeout=20)
    assert outcome.returncode==0,outcome.stderr
    print('Temporary exact pre-FIX source, legacy text-only restart, retained journal/unknown, zero replay: PASS')
    print('Candidate arguments-only dispatch after reverting is unsafe; deployed rollback NOT VERIFIED')
