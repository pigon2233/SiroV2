"""Disposable synthetic Gateway UI fixture; never uses the owner's live data."""
import asyncio
import tempfile
import hashlib,json
from pathlib import Path
import uvicorn
from siro.adapters.skill_worker import SkillDispatcher, WorkerSupervisor
from siro.persistence.skills import SQLiteSkillRegistry
from siro.persistence.sqlite import SQLiteStore
from siro.services.presentation.gateway import create_app
from siro.services.tools.orchestrator import ToolCatalog, ToolOrchestrator, SQLiteToolProposalRepository
from siro.services.tools.skill_candidates import SkillCandidatePreparer
from siro.services.tools.skill_activation import SkillActivationOwner

async def main():
    root = None
    try:
      with tempfile.TemporaryDirectory(prefix='siro-activation-browser-') as name:
        root=Path(name)
        store=SQLiteStore(root/'synthetic.sqlite3')
        await store.initialize()
        catalog=ToolCatalog(())
        registry=SQLiteSkillRegistry(store)
        owner=SkillActivationOwner(catalog, registry, SkillDispatcher(registry, WorkerSupervisor(profile='python-stdlib-single')), root/'managed')
        tools=ToolOrchestrator(SQLiteToolProposalRepository(store), {}, catalog=catalog)
        app=create_app(allowed_origins={'http://127.0.0.1:18034'}, runtime_profile='candidate', tool_orchestrator=tools, skill_candidates=SkillCandidatePreparer(catalog), skill_activation=owner)
        sources=['src/siro/persistence/skills.py','src/siro/services/tools/orchestrator.py','src/siro/services/presentation/gateway.py','src/siro/services/presentation/static/index.html','src/siro/services/tools/skill_activation.py']
        (Path(__file__).parent/'browser-source-binding.json').write_text(json.dumps({'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources},'private_data':False,'temporary_workspace':str(root)},indent=2)+'\n')
        try:
          await uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=18034, log_level='warning')).serve()
        finally:
          try:
            await owner.close()
          except asyncio.CancelledError:
            pass
          print('owned_jobs_after_shutdown:',len(owner._jobs),flush=True)
        assert not owner._jobs
    finally:
      if root is not None:
        print('temporary_workspace_removed:',not root.exists(),flush=True)

if __name__=='__main__': asyncio.run(main())
