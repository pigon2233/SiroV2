"""Secret scan only the explicit public D52 source/document/evidence scope."""
from __future__ import annotations
import datetime,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'docs/evidence/RI-005-launcher-2026-10-13'
SOURCE=list(json.loads((OUT/'source-freeze.json').read_text())['source_sha256'])
DOCS=['docs/STATUS.md','docs/CONTRACTS.md','docs/DECISIONS.md']+[f'docs/runtime-evolution/{n}.md' for n in ['ARCHITECTURE_REVIEW','CAPABILITY_MATRIX','COMPATIBILITY_PLAN','FIX_REGISTER','HERMES_GAP_ANALYSIS','MIGRATION_PLAN','REGRESSION_BASELINE','RISK_REGISTER','RUNTIME_EVOLUTION_ROADMAP','RUNTIME_EVOLUTION_SPEC']]
EVIDENCE=[p.relative_to(ROOT).as_posix() for p in sorted(OUT.rglob('*')) if p.is_file() and p.suffix in {'.py','.json','.log','.md','.patch'} and not p.name.startswith(('audit-','secrets-','publish-','review-secrets'))]

def main()->None:
    inputs={'cutoff_utc':datetime.datetime.now(datetime.UTC).isoformat(),'scope':{'source':SOURCE,'docs':DOCS,'evidence':EVIDENCE},'excluded':'secret/audit outputs and publication metadata; no private .siro-data/.codex/db/audio/models/local auth helper input','input_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCE+DOCS+EVIDENCE}}
    (OUT/'secrets-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    all_results={}
    for kind,files in inputs['scope'].items():
        cmd=[str(ROOT/'.venv/bin/detect-secrets'),'scan','--no-verify',*files]
        result=json.loads(subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,check=True).stdout)
        (OUT/f'secrets-{kind}-raw.json').write_text(json.dumps(result,indent=2)+'\n')
        all_results[kind]=result['results']
    (OUT/'secrets-results.json').write_text(json.dumps(all_results,indent=2)+'\n')
    print(json.dumps({k:{'files':len(v),'findings':sum(len(xs) for xs in v.values())} for k,v in all_results.items()}))

if __name__=='__main__':main()
