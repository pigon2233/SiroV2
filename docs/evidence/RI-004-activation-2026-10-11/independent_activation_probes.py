"""Synthetic owner controls with real temp SQLite and explicit controlled seams."""
from __future__ import annotations
import asyncio
import json
import tempfile
import threading
from pathlib import Path
from siro.adapters.skill_worker import SkillDispatcher,WorkerSupervisor
from siro.persistence.skills import SQLiteSkillRegistry
from siro.persistence.sqlite import SQLiteStore
from siro.services.tools import skill_activation as activation
from siro.services.tools.skill_candidates import SkillCandidatePreparer,CAPABILITY
from siro.services.tools.orchestrator import ToolCatalog
from siro.services.tools.execution import ExecutionContext,ExecutionCleanupError

async def fixture(root):
 store=SQLiteStore(root/'synthetic.sqlite3'); await store.initialize()
 registry=SQLiteSkillRegistry(store); catalog=ToolCatalog(())
 owner=activation.SkillActivationOwner(catalog,registry,SkillDispatcher(registry,WorkerSupervisor(profile='python-stdlib-single')),root/'managed')
 await owner.initialize()
 preparer=SkillCandidatePreparer(catalog)
 try: report=await preparer.prepare(CAPABILITY)
 finally: await preparer.close()
 review=await owner.remember(report)
 await owner.install(review['review_id'],review['package_hash']); await owner.enable(review['package_hash'])
 return owner,registry,catalog,review['package_hash']

async def cleanup_failure_revoke(root):
 owner,registry,catalog,h=await fixture(root)
 entered=asyncio.Event()
 async def fail_cleanup(*args):
  entered.set()
  try: await asyncio.Future()
  except asyncio.CancelledError: raise ExecutionCleanupError('synthetic owned worker cleanup failed')
 owner._dispatcher.execute=fail_cleanup
 job=asyncio.create_task(owner.execute({'text':'synthetic'},ExecutionContext('synthetic','synthetic','synthetic',authorized=True)))
 await entered.wait()
 try: await owner.revoke(h); result={'returned':'success'}
 except BaseException as error: result={'exception':type(error).__name__,'detail':str(error)}
 jobs=await asyncio.gather(job,return_exceptions=True)
 persisted=await registry.is_enabled('siro.text.checklist','1.0.0')
 new=activation.SkillActivationOwner(ToolCatalog(()),registry,SkillDispatcher(registry,WorkerSupervisor(profile='python-stdlib-single')),root/'managed')
 await new.initialize()
 row={'case':'cleanup_failure_revoke','observed_revoke':result,'in_memory_enabled':owner.snapshot()['enabled'],'registry_enabled_after_revoke':persisted,'fresh_owner_restored_enabled':new.snapshot()['enabled'],'job_result':type(jobs[0]).__name__,'controlled_seam':'dispatcher stub throws typed cleanup failure when cancelled; real temp registry/receipt/initialize','expected':'durable disable remains effective even if owned drain raises typed cleanup failure'}
 await new.revoke(h); await new.close(); await owner.close()
 return row

async def cancelled_initialize(root):
 owner,registry,catalog,h=await fixture(root)
 fresh=activation.SkillActivationOwner(ToolCatalog(()),registry,SkillDispatcher(registry,WorkerSupervisor(profile='python-stdlib-single')),root/'managed')
 original=activation._restored; entered=threading.Event(); release=threading.Event()
 def blocked(path):
  result=original(path); entered.set(); assert release.wait(2); return result
 activation._restored=blocked
 task=asyncio.create_task(fresh.initialize())
 try:
  assert await asyncio.to_thread(entered.wait,2)
  task.cancel(); await asyncio.sleep(.01); task.cancel(); release.set()
  try: await task; outcome='success'
  except BaseException as error: outcome=type(error).__name__
  row={'case':'cancelled_initialize','caller_result':outcome,'fresh_owner_enabled_after_cancel':fresh.snapshot()['enabled'],'fresh_catalog_tool_names':[x.name for x in fresh._catalog.definitions()],'controlled_seam':'actual offloop restored reads then blocked publication; repeat caller cancellation','expected':'cancelled initialize cannot publish available enabled descriptor after epoch invalidation'}
 finally:
  release.set(); activation._restored=original; await asyncio.gather(task,return_exceptions=True)
 await fresh.close(); await owner.revoke(h); await owner.close()
 return row

async def main():
 with tempfile.TemporaryDirectory(prefix='siro-independent-activation-') as d:
  root=Path(d).resolve()
  rows=[await cleanup_failure_revoke(root/'revoke'),await cancelled_initialize(root/'initialize')]
 artifact={'synthetic_only':True,'real_temporary_sqlite_package_receipt':True,'os_boundary_not_retested_by_cleanup_stub':True,'private_data_used':False,'live_service_touched':False,'rows':rows,'temporary_fixture_removed':not root.exists()}
 Path(__file__).with_name('independent-control-probes-before.json').write_text(json.dumps(artifact,indent=2)+'\n')
 print(json.dumps(artifact,indent=2))

if __name__=='__main__': asyncio.run(main())
