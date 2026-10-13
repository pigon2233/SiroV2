"""Exact four-file source-only rollback proof in a disposable public-code copy."""
from pathlib import Path
import datetime
import difflib
import hashlib
import json
import subprocess
import sys
import tempfile

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
EXISTING=('src/siro/persistence/sqlite.py','src/siro/cli.py')
NEW=('tests/integration/test_sqlite_backup_lifecycle.py','tests/integration/test_backup_cli_cancellation.py')
SCOPE=EXISTING+NEW
FINAL='--final' in sys.argv
baseline=json.loads((OUT/'baseline.json').read_text())
assert len(baseline['hashes'])==271
assert all(name in baseline['hashes'] for name in EXISTING)
assert all(name not in baseline['hashes'] for name in NEW)
sha=lambda data:hashlib.sha256(data).hexdigest()
initial={name:sha((ROOT/name).read_bytes()) for name in baseline['hashes']}
changed={name for name,digest in initial.items() if baseline['hashes'][name]!=digest}
assert changed==set(EXISTING),sorted(changed)
unchanged={name:digest for name,digest in initial.items() if name not in EXISTING}
assert len(unchanged)==269
before={name:(OUT/'before'/name).read_bytes() for name in EXISTING}
assert all(sha(before[name])==baseline['hashes'][name] for name in EXISTING)
after={name:(ROOT/name).read_bytes() for name in SCOPE}
after_sha={name:sha(data) for name,data in after.items()}
if FINAL:
    freeze=json.loads((OUT/'rollback-root-freeze.json').read_text())
    assert freeze['source_sha256']==after_sha, 'Source differs from explicitly recorded root freeze'
patch=[]
for name in SCOPE:
    old=before[name].decode().splitlines(keepends=True) if name in before else []
    new=after[name].decode().splitlines(keepends=True)
    patch.extend(difflib.unified_diff(old,new,fromfile='a/'+name if name in before else '/dev/null',tofile='b/'+name,n=3))
patch_bytes=''.join(patch).encode()
patch_path=OUT/('rollback-repair-final.patch' if FINAL else 'rollback-repair-preliminary.patch')
patch_path.write_bytes(patch_bytes)
commands=[]
with tempfile.TemporaryDirectory(prefix='siro-fix015-source-rollback-') as directory:
    copy=Path(directory)
    for name,data in after.items():
        target=copy/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    def apply(*arguments):
        command=['git','apply','--no-index',*arguments,str(patch_path)]
        result=subprocess.run(command,cwd=copy,capture_output=True,text=True)
        commands.append({'command':['git','apply','--no-index',*arguments,'<exact_public_scope_patch>'],'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        assert result.returncode==0, result.stderr
    apply('--check','--reverse')
    apply('--reverse')
    reversed_sha={name:sha((copy/name).read_bytes()) for name in EXISTING}
    assert all(reversed_sha[name]==baseline['hashes'][name] for name in EXISTING)
    assert all(not (copy/name).exists() for name in NEW)
    apply('--check')
    apply()
    reapplied_sha={name:sha((copy/name).read_bytes()) for name in SCOPE}
    assert reapplied_sha==after_sha
    temporary_dir=directory
assert not Path(temporary_dir).exists()
assert all(sha((ROOT/name).read_bytes())==digest for name,digest in initial.items()), 'Baseline/workspace mutated during rehearsal'
assert all(sha((ROOT/name).read_bytes())==digest for name,digest in after_sha.items()), 'Final source mutated during rehearsal'
result={'status':'PASS' if FINAL else 'PRELIMINARY_REHEARSAL_PASS_AWAITING_ROOT_FREEZE','client_date':'2026-10-13','verified_utc':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),'scope':list(SCOPE),'existing_changed_paths':sorted(changed),'unchanged_baseline_count':269,'baseline_count':271,'unchanged_baseline_sha256':unchanged,'before_sha256':{name:sha(data) for name,data in before.items()},'source_sha256':after_sha,'reverse_sha256':reversed_sha,'reapplied_sha256':reapplied_sha,'new_tests_removed_on_reverse':list(NEW),'patch':patch_path.name,'patch_sha256':sha(patch_bytes),'commands':commands,'temporary_code_only_copy_removed':True,'main_workspace_rolled_back':False,'git_index_or_authhelper_access':False,'private_blob_or_runtime_data_access':False,'data_recovery_or_data_rollback_claimed':False,'final_root_freeze_bound':FINAL,'root_freeze_artifact':'rollback-root-freeze.json' if FINAL else None,'source_rollback_reintroduces_known_backup_cleanup_defect':True}
name='rollback-final.json' if FINAL else 'rollback-preliminary.json'
(OUT/name).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
report=('# FIX-015 source-only rollback verification — 2026-10-13\n\n'+f'Status: **{result["status"]}**. Only SQLiteStore, CLI and two new test files are in the exact patch. A disposable code-only copy successfully passed reverse check, reverse, reapply check and reapply; its bytes matched the captured prior dirty baseline / current source exactly. New tests disappear on reverse and return exactly on reapply.\n\n'+f'All{len(unchanged)} other baseline files stayed unchanged before and after. All271 baseline hashes and the4 current scope hashes were rechecked after the rehearsal; the temporary copy was removed. No main-workspace source rollback, Git index/authhelper changes, private blob/runtime/data access occurred.\n\n'+'This restores source bytes only; it does not restore, rewind, repair, or recover any database, backup, conversation, audio or other user data. Undoing the fix reintroduces the confirmed backup cancellation/temporary cleanup defect and must not lift its release blocker.\n\n'+'Exact scopes/digests/commands are in '+name+'; repair patch SHA is bound there. '+('The final root freeze record is matched before rehearsal.' if FINAL else 'Root freeze has not been announced; this is preliminary, not final acceptance.')+'\n')
(OUT/('rollback-final-report.md' if FINAL else 'rollback-preliminary-report.md')).write_text(report)
print(json.dumps({key:value for key,value in result.items() if key not in {'unchanged_baseline_sha256','commands'}},indent=2))
