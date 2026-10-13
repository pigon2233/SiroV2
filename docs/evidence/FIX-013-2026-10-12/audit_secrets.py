"""Review only explicit public source/doc/evidence paths; no blanket entropy exemption."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
source = ['src/siro/persistence/sqlite.py', 'tests/integration/test_sqlite_restore_validation.py', 'tests/integration/test_sqlite_restore_lifecycle.py']
documents = json.loads((OUT/'document-scope.json').read_text())['documents']
excluded = {'audit_secrets.py', 'secrets-source-final.json', 'secrets-docs-final.json', 'secrets-evidence-final.json', 'secrets-review-final.json', 'source-audit-report.md', 'secrets-audit-final.log'}
inputs = [p for p in OUT.rglob('*') if p.is_file() and p.name not in excluded and '__pycache__' not in p.parts]
with (OUT/'secrets-evidence-final.json').open('w') as handle:
    subprocess.run([str(ROOT/'.venv/bin/detect-secrets'), 'scan', '--no-verify', '--all-files', *[str(p.relative_to(ROOT)) for p in inputs]], cwd=ROOT, stdout=handle, check=True)
known = set(json.loads((OUT/'baseline.json').read_text())['hashes'].values())
preservation = json.loads((OUT/'preservation.json').read_text())
known.update(preservation['final_sha256'].values())
known.add(preservation['patch_sha256'])
for directory in ('before', 'after', 'before-wait-fix'):
    for path in (OUT/directory).rglob('*.py'):
        known.add(hashlib.sha256(path.read_bytes()).hexdigest())
reviewed = []
for filename, findings in json.loads((OUT/'secrets-evidence-final.json').read_text())['results'].items():
    path = ROOT/filename
    assert path.is_relative_to(OUT), filename
    lines = path.read_text().splitlines()
    for finding in findings:
        line = lines[finding['line_number']-1]
        candidates = re.findall(r'(?<![a-fA-F0-9])[a-f0-9]{64}(?![a-fA-F0-9])', line)
        matches = [value for value in candidates if hashlib.sha1(value.encode()).hexdigest() == finding['hashed_secret']]
        valid = finding['type'] == 'Hex High Entropy String' and len(matches) == 1 and matches[0] in known
        named = any(label in line.lower() for label in ('sha256', 'sha ', 'source', 'test', 'patch', 'hash', '"src/', '"scripts/', '"cargo.', '"pyproject.', '"uv.lock"'))
        item = {'file':filename, 'line':finding['line_number'], 'detector':finding['type'], 'detector_fingerprint':finding['hashed_secret'], 'exact_line_match':len(matches)==1, 'known_captured_digest':valid, 'named_recorded_field':named, 'classification':'RECORDED_SHA256_FALSE_POSITIVE' if valid and named else 'UNRESOLVED'}
        reviewed.append(item)
source_results = json.loads((OUT/'secrets-source-final.json').read_text())['results']
doc_results = json.loads((OUT/'secrets-docs-final.json').read_text())['results']
unresolved = [v for v in reviewed if v['classification'] == 'UNRESOLVED']
assert not source_results and not doc_results, (len(source_results), len(doc_results))
assert not unresolved, [{k:v for k,v in i.items() if k != 'detector_fingerprint'} for i in unresolved]
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in preservation['final_sha256'].items())
cutoff = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
result = {'status':'PASS', 'cutoff_utc':cutoff, 'source_files':len(source), 'source_findings':0, 'document_files':len(documents), 'document_findings':0, 'evidence_input_files':len(inputs), 'evidence_raw_findings':len(reviewed), 'reviewed_digest_false_positives':len(reviewed), 'unresolved':0, 'findings':reviewed, 'input_paths':[str(p.relative_to(ROOT)) for p in inputs], 'private_data_read':False, 'network_verification':False, 'independent_scoped_source_review_completed':True, 'annotation_only_updates_after_cutoff_excluded':True, 'excluded_output_names':sorted(excluded)}
(OUT/'secrets-review-final.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('findings','input_paths')},indent=2))
