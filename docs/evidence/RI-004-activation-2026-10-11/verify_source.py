"""Public source-only preservation and disposable exact-card rollback rehearsal."""
from pathlib import Path
import difflib
import hashlib
import json
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
EXISTING=('src/siro/persistence/skills.py','src/siro/services/tools/orchestrator.py','src/siro/services/presentation/gateway.py','src/siro/services/presentation/static/index.html')
NEW=('src/siro/services/tools/skill_activation.py','tests/integration/test_skill_activation.py','tests/integration/test_skill_activation_foundation.py','tests/integration/test_skill_activation_lifecycle.py','tests/integration/test_skill_activation_review.py','tests/integration/test_skill_activation_product.py','tests/integration/test_frontend_skill_activation.py')
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    baseline=json.loads((OUT/'baseline.json').read_text())['hashes'];assert len(baseline)==258
    changed=[p for p,h in baseline.items() if sha((ROOT/p).read_bytes())!=h]
    assert set(changed)==set(EXISTING),changed
    scope=EXISTING+NEW
    captured={p:(ROOT/p).read_bytes() for p in scope}
    before={p:(OUT/'before'/p).read_bytes() for p in EXISTING}
    assert all(sha(b)==baseline[p] for p,b in before.items())
    patch=[]
    for p,b in captured.items():
        old=before.get(p,b'')
        assert b.endswith(b'\n')
        dest=OUT/'after'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
        patch.append(f'diff --git a/{p} b/{p}\n')
        patch.extend(difflib.unified_diff(old.decode().splitlines(True),b.decode().splitlines(True),fromfile=f'a/{p}' if p in EXISTING else '/dev/null',tofile=f'b/{p}'))
    target=OUT/'repair.patch';target.write_text(''.join(patch))
    env={'PATH':os.defpath,'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null','GIT_CONFIG_NOSYSTEM':'1','GIT_TERMINAL_PROMPT':'0'}
    with tempfile.TemporaryDirectory(prefix='siro-activation-rollback-') as name:
        temp=Path(name)
        for p,b in captured.items():
            dest=temp/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
        for args in (['--reverse','--check'],['--reverse'],['--check'],[]):
            subprocess.run(['git','apply',*args,str(target)],cwd=temp,env=env,check=True,capture_output=True,timeout=15)
            if args==['--reverse']:
                assert all(sha((temp/p).read_bytes())==baseline[p] for p in EXISTING)
                assert all(not (temp/p).exists() for p in NEW)
        assert all((temp/p).read_bytes()==b for p,b in captured.items())
    assert not temp.exists()
    assert all((ROOT/p).read_bytes()==b for p,b in captured.items())
    report={'status':'PASS','baseline_files':258,'unchanged_existing_files':254,'changed_existing_files':list(EXISTING),'new_files':list(NEW),'final_sha256':{p:sha(b) for p,b in captured.items()},'patch_sha256':sha(target.read_bytes()),'disposable_reverse_reapply':True,'live_source_unchanged':True,'runtime_restarted':False,'private_data_read':False,'database_rollback':False}
    (OUT/'preservation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
