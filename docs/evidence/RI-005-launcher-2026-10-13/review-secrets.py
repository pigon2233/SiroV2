"""Bind every entropy finding to exact captured public bytes or measured synthetic package digest."""
from __future__ import annotations
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'docs/evidence/RI-005-launcher-2026-10-13'

def main()->None:
    inputs=json.loads((OUT/'secrets-inputs.json').read_text())
    results=json.loads((OUT/'secrets-results.json').read_text())
    assert not results['source'] and not results['docs']
    known={}
    base=json.loads((OUT/'baseline.json').read_text())['hashes']
    changed={'src/siro/core/releases.py','scripts/launch_companion.py','src/siro/services/presentation/gateway.py'}
    for path,value in base.items():
        p=OUT/'before'/path if path in changed else ROOT/path
        assert hashlib.sha256(p.read_bytes()).hexdigest()==value,path
        known[value]={'kind':'verified-captured-baseline','path':path}
    for path,expected in inputs['input_sha256'].items():
        actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
        assert actual==expected,path
        known[actual]={'kind':'verified-public-input','path':path}
    commit=json.loads((OUT/'baseline.json').read_text())['public_checkpoint']
    subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=ROOT,check=True)
    known[commit]={'kind':'already-public-current-commit','reference':'baseline public_checkpoint'}
    proc=json.loads((OUT/'process-final.json').read_text())
    assert proc['status']=='PASS'
    for result in proc['results']:
        for child in result.get('processes',[]):
            assert child['package_unchanged'] and child['origins_selected']
            assert child['ready']['release']['source_sha256']==child['source_sha256']
            known[child['source_sha256']]={'kind':'measured-signed-synthetic-package','case':result['case'],'version':child['version'],'package_before_after_unchanged':True,'ready_digest_matches':True}
    review=[];unresolved=[]
    for path,findings in results['evidence'].items():
        lines=(ROOT/path).read_text().splitlines()
        for finding in findings:
            n=finding['line_number'];values=re.findall(r'(?<![a-zA-Z0-9])[a-fA-F0-9]{32,128}(?![a-zA-Z0-9])',lines[n-1])
            matches=[v for v in values if v in known and hashlib.sha1(v.encode()).hexdigest()==finding['hashed_secret']]
            row={'file':path,'line':n,'type':finding['type'],'hashed_secret':finding['hashed_secret']}
            if matches:
                row['binding']=known[matches[0]];review.append(row)
            else:
                row['field']=lines[n-1].split(':',1)[0].strip();unresolved.append(row)
    result={'cutoff_utc':inputs['cutoff_utc'],'source_findings':0,'docs_findings':0,'reviewed_count':len(review),'unresolved_count':len(unresolved),'findings':review,'unresolved':unresolved}
    (OUT/'secrets-evidence-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('reviewed_count','unresolved_count')}))
    assert not unresolved

if __name__=='__main__':main()
