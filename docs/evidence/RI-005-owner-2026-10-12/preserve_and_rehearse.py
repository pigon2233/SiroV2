"""Exact scoped D50 source-only rollback; no live database or service operations."""
from pathlib import Path
import difflib,hashlib,json,subprocess,tempfile
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
EXISTING=('src/siro/cli.py','src/siro/services/presentation/gateway.py')
NEW=('src/siro/adapters/data_ownership.py','tests/integration/test_data_owner_callers.py','tests/integration/test_data_owner_lifecycle.py')
SCOPE=(*EXISTING,*NEW)
baseline=json.loads((OUT/'baseline.json').read_text())['hashes']
assert len(baseline)==268
assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value for name,value in baseline.items() if name not in EXISTING)
assert all(name not in baseline for name in NEW)
final={};patch=[]
for name in SCOPE:
 raw=(ROOT/name).read_bytes();final[name]=hashlib.sha256(raw).hexdigest()
 p=OUT/'after'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
 old=(OUT/'before'/name).read_bytes() if name in EXISTING else b''
 patch.extend(difflib.unified_diff(old.decode().splitlines(keepends=True),raw.decode().splitlines(keepends=True),fromfile='a/'+name if old else '/dev/null',tofile='b/'+name))
path=OUT/'repair.patch';path.write_text(''.join(patch))
with tempfile.TemporaryDirectory(prefix='siro-d50-source-rehearsal-') as directory:
 rehearsal=Path(directory)
 for name in SCOPE:
  p=rehearsal/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
 for options in (('--check','--reverse'),('--reverse',)):
  subprocess.run(['git','apply','--no-index',*options,str(path)],cwd=rehearsal,check=True,capture_output=True)
 assert all(hashlib.sha256((rehearsal/name).read_bytes()).hexdigest()==baseline[name] for name in EXISTING)
 assert all(not(rehearsal/name).exists() for name in NEW)
 for options in (('--check',),()):
  subprocess.run(['git','apply','--no-index',*options,str(path)],cwd=rehearsal,check=True,capture_output=True)
 assert all(hashlib.sha256((rehearsal/name).read_bytes()).hexdigest()==value for name,value in final.items())
assert not rehearsal.exists()
assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value for name,value in final.items())
result={'status':'PASS','baseline_files':268,'unchanged_existing_files':266,'changed_existing_files':list(EXISTING),'new_files':list(NEW),'final_sha256':final,'patch_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'disposable_reverse_reapply':True,'rehearsal_workspace_removed':True,'live_source_unchanged_by_rehearsal':True,'D47_D48_D49_preserved':True,'runtime_restarted':False,'private_data_read':False,'database_rollback':False}
(OUT/'preservation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
