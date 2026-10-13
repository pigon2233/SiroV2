"""Read-only source/AST binding; run once scoped source and tests are frozen."""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SCOPE=(
 'src/siro/adapters/skill_worker.py',
 'src/siro/services/tools/patch_verification.py',
 'src/siro/services/tools/patch_verification_runner.py',
 'src/siro/adapters/isolated_python.py',
 'src/siro/adapters/python_restrictions.py',
 'src/siro/adapters/strict_skill_runner.py',
 'tests/integration/test_strict_skill_worker.py',
)
PROTECTED=(
 'src/siro/core/skills.py',
 'src/siro/persistence/skills.py',
 'src/siro/persistence/sqlite.py',
 'src/siro/adapters/process_execution.py',
 'src/siro/skill_worker.py',
 'src/siro/services/tools/execution.py',
 'src/siro/services/tools/skill_candidates.py',
 'src/siro/services/tools/orchestrator.py',
 'src/siro/services/presentation/gateway.py',
)

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def tree(path): return ast.parse(path.read_text(encoding='utf-8'))
def find(nodes,name): return next(node for node in nodes if getattr(node,'name',None)==name)
def same(a,b): return ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
def body_same(a,b): return [ast.dump(n,include_attributes=False) for n in a]==[ast.dump(n,include_attributes=False) for n in b]

def main():
 baseline=json.loads((OUT/'baseline.json').read_text())['hashes']
 before=tree(OUT/'before'/SCOPE[0]); after=tree(ROOT/SCOPE[0])
 unchanged={name:same(find(before.body,name),find(after.body,name)) for name in ('_prepare_skill','_join_owned','_prepare_request','_remove_request','_request','_reject_constant','SkillDispatcher')}
 bw=find(before.body,'WorkerSupervisor'); aw=find(after.body,'WorkerSupervisor')
 unchanged['trusted_local_execute_one_body']=body_same(find(bw.body,'_execute_one').body,find(aw.body,'_execute_one').body[1:])
 unchanged['trusted_local_execute_body']=body_same(find(bw.body,'execute').body,find(aw.body,'execute').body[1:])
 unchanged['default_concurrency_owner_initialization']=same(find(bw.body,'__init__').body[0],find(aw.body,'__init__').body[-1])
 before_runner=tree(OUT/'before'/SCOPE[2]); after_runner=tree(ROOT/SCOPE[2])
 unchanged['patch_runner_main_and_probe']=same(find(before_runner.body,'main'),find(after_runner.body,'main'))
 assert all(unchanged.values()), unchanged
 protected={name:{'sha256':digest(ROOT/name),'unchanged':digest(ROOT/name)==baseline[name]} for name in PROTECTED if name in baseline}
 assert all(row['unchanged'] for row in protected.values())
 assert len(protected)==len(PROTECTED), (len(protected),len(PROTECTED))
 for name in SCOPE[:6]:
  t=tree(ROOT/name)
  if '/adapters/' in name:
   imports=[node.module for node in ast.walk(t) if isinstance(node,ast.ImportFrom)]
   assert all(not (module or '').startswith('siro.services') for module in imports), (name,imports)
 from siro.services.tools import patch_verification
 spec=importlib.util.spec_from_file_location('siro.services.tools._independent_before_verifier',OUT/'before'/SCOPE[1])
 assert spec and spec.loader
 old=importlib.util.module_from_spec(spec); sys.modules[spec.name]=old; spec.loader.exec_module(old)
 oldmounts=old._mounts(); newmounts=patch_verification._mounts()
 assert oldmounts==newmounts and oldmounts is not None
 oldargv=old._sandbox_argv('/bin/bwrap',Path('/synthetic-workspace'),oldmounts)
 newargv=patch_verification._sandbox_argv('/bin/bwrap',Path('/synthetic-workspace'),newmounts)
 assert oldargv==newargv
 result={'status':'PASS','scope':'exact six production plus one new test; source/AST/public-private compatibility only','source_sha256':{name:digest(ROOT/name) for name in SCOPE},'unchanged_ast':unchanged,'protected_baseline_files':protected,'patch_facade_runtime_mounts_argv_equal':True,'adapter_reverse_service_import_absent':True,'private_data_used':False,'live_service_touched':False,'no_registry_activation':True}
 (OUT/'independent-source-binding.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,indent=2))

if __name__=='__main__': main()
