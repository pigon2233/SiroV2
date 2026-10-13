"""Verify each entropy finding against exact captured public bytes, never blanket hex exemptions."""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'docs/evidence/FIX-015-2026-10-13'

def main()->None:
    inputs=json.loads((OUT/'secrets-inputs.json').read_text())
    base=json.loads((OUT/'baseline.json').read_text())['hashes']
    known={}
    for path,value in base.items():
        p=ROOT/path
        if path in {'src/siro/cli.py','src/siro/persistence/sqlite.py'}:
            p=OUT/'before'/path
        assert hashlib.sha256(p.read_bytes()).hexdigest()==value, path
        known[value]={'kind':'verified-captured-baseline','path':path}
    for path,expected in inputs['input_sha256'].items():
        actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
        assert actual==expected, path
        known[actual]={'kind':'verified-actual-public-input','path':path}
    for expression in ('HEAD','HEAD^{tree}','HEAD^'):
        value=subprocess.run(['git','rev-parse',expression],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
        known[value]={'kind':'current-public-git-object','ref':expression}
    cli=(ROOT/'src/siro/cli.py').read_text().replace('        loop = asyncio.get_running_loop()\n','').replace('            loop.call_soon_threadsafe(lambda: None)\n','')
    known[hashlib.sha256(cli.encode()).hexdigest()]={'kind':'exact-intermediate-CLI-reconstruction','from':'final CLI minus the two selector-wakeup lines'}
    test=(ROOT/'tests/integration/test_backup_cli_cancellation.py').read_text()
    test=test.replace('["success", "cancelled", "primary_error", "late_success"]','["success", "cancelled", "primary_error"]')
    test=test.replace('if outcome in {"primary_error", "late_success"}:','if outcome == "primary_error":')
    test=test.replace('            except asyncio.CancelledError:\n                if outcome == "primary_error":\n                    raise problem from None\n','            except asyncio.CancelledError:\n                raise problem from None\n')
    test=test.replace('        elif outcome == "late_success":\n            with pytest.raises(KeyboardInterrupt):\n                cli._backup(arguments)\n','')
    known[hashlib.sha256(test.encode()).hexdigest()]={'kind':'exact-five-case-test-reconstruction','from':'final six-case file minus captured late_success patch'}
    review=[];unresolved=[]
    results=json.loads((OUT/'secrets-results.json').read_text())
    assert all(not results[k] for k in ('source','git-hygiene','docs'))
    for path,findings in results['evidence'].items():
        lines=(ROOT/path).read_text().splitlines()
        for finding in findings:
            line=finding['line_number']
            tokens=re.findall(r'(?<![a-zA-Z0-9])[a-fA-F0-9]{32,128}(?![a-zA-Z0-9])',lines[line-1])
            matches=[v for v in tokens if v in known and hashlib.sha1(v.encode()).hexdigest()==finding['hashed_secret']]
            row={'file':path,'line':line,'type':finding['type'],'hashed_secret':finding['hashed_secret']}
            if matches:
                row['binding']=known[matches[0]];review.append(row)
            else:
                row['field']=lines[line-1].split(':',1)[0].strip();unresolved.append(row)
    result={'cutoff_utc':inputs['cutoff_utc'],'source_findings':0,'git_hygiene_findings':0,'docs_findings':0,'reviewed_count':len(review),'unresolved_count':len(unresolved),'findings':review,'unresolved':unresolved}
    (OUT/'secrets-evidence-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('reviewed_count','unresolved_count')}))
    assert not unresolved,'unresolved public evidence cannot be published'

if __name__=='__main__':main()
