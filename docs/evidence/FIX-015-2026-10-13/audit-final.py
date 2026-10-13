"""Scan explicit public repair inputs; record findings without displaying secret values."""
from __future__ import annotations
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'docs/evidence/FIX-015-2026-10-13'
SOURCE=['src/siro/persistence/sqlite.py','src/siro/cli.py','tests/integration/test_sqlite_backup_lifecycle.py','tests/integration/test_backup_cli_cancellation.py']
HYGIENE=['tests/contract/test_model_adapters.py','tests/integration/test_provider_completion.py','tests/integration/test_companion_launcher.py']
DOCS=['docs/STATUS.md','docs/CONTRACTS.md','docs/DECISIONS.md']+[f'docs/runtime-evolution/{name}.md' for name in ['ARCHITECTURE_REVIEW','CAPABILITY_MATRIX','COMPATIBILITY_PLAN','FIX_REGISTER','HERMES_GAP_ANALYSIS','MIGRATION_PLAN','REGRESSION_BASELINE','RISK_REGISTER','RUNTIME_EVOLUTION_ROADMAP','RUNTIME_EVOLUTION_SPEC']]
EXCLUDED_PREFIXES=('push-','public-checkpoint','publish_checkpoint','audit-','secrets-')
EVIDENCE=[p.relative_to(ROOT).as_posix() for p in sorted(OUT.rglob('*')) if p.is_file() and not p.name.startswith(EXCLUDED_PREFIXES) and p.suffix in {'.py','.json','.log','.md','.patch'} and 'secret-scan' not in p.name]

def scan(files:list[str],name:str)->dict:
    completed=subprocess.run([str(ROOT/'.venv/bin/detect-secrets'),'scan','--no-verify',*files],cwd=ROOT,capture_output=True,text=True,check=True)
    report=json.loads(completed.stdout)
    (OUT/f'secrets-{name}-raw.json').write_text(json.dumps(report,indent=2)+'\n')
    return report['results']

def main()->None:
    metadata={'cutoff_utc':datetime.datetime.now(datetime.UTC).isoformat(),'no_private_inputs':True,'excluded':'push/authentication audit metadata, secret scanner outputs; models/audio/databases/local helper never scanned','inputs':{'source':SOURCE,'git_hygiene':HYGIENE,'docs':DOCS,'evidence':EVIDENCE},'input_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCE+HYGIENE+DOCS+EVIDENCE}}
    (OUT/'secrets-inputs.json').write_text(json.dumps(metadata,indent=2)+'\n')
    result={name:scan(files,name) for name,files in [('source',SOURCE),('git-hygiene',HYGIENE),('docs',DOCS),('evidence',EVIDENCE)]}
    (OUT/'secrets-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:{'files_with_findings':len(v),'findings':sum(len(x) for x in v.values())} for k,v in result.items()}))

if __name__=='__main__':main()
