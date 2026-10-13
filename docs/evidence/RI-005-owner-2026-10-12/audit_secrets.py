"""Audit only explicit public artifacts, with exact finding-by-finding digest binding."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
preservation = json.loads((OUT / 'preservation.json').read_text())
source = list(preservation['final_sha256'])
documents = json.loads((OUT / 'document-scope.json').read_text())['documents']
excluded = {'audit_secrets.py', 'secrets-source-final.json', 'secrets-docs-final.json',
            'secrets-evidence-final.json', 'secrets-review-final.json', 'secrets-audit-final.log',
            'secrets-unresolved.json', 'secrets-history-review.json', 'source-audit-report.md'}
inputs = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name not in excluded
                and '__pycache__' not in p.parts)
for names, filename in ((source, 'secrets-source-final.json'),
                        (documents, 'secrets-docs-final.json'),
                        ([str(p.relative_to(ROOT)) for p in inputs], 'secrets-evidence-final.json')):
    with (OUT / filename).open('w') as output:
        subprocess.run([str(ROOT / '.venv/bin/detect-secrets'), 'scan', '--no-verify',
                        '--all-files', *names], cwd=ROOT, stdout=output, check=True)
known = set(json.loads((OUT / 'baseline.json').read_text())['hashes'].values())
for filename in ('preservation.json', 'preservation-before-temporary-target.json'):
    captured = json.loads((OUT / filename).read_text())
    known.update(captured['final_sha256'].values())
    known.add(captured['patch_sha256'])
for path in inputs:
    known.add(hashlib.sha256(path.read_bytes()).hexdigest())
history = json.loads((OUT / 'secrets-history-review.json').read_text()) if (OUT / 'secrets-history-review.json').exists() else []
reviewed = []
for filename, findings in json.loads((OUT / 'secrets-evidence-final.json').read_text())['results'].items():
    path = ROOT / filename
    assert path.is_relative_to(OUT), filename
    lines = path.read_text().splitlines()
    for finding in findings:
        line = lines[finding['line_number'] - 1]
        matches = [v for v in re.findall(r'(?<![a-fA-F0-9])[a-f0-9]{64}(?![a-fA-F0-9])', line)
                   if hashlib.sha1(v.encode()).hexdigest() == finding['hashed_secret']]
        exact = finding['type'] == 'Hex High Entropy String' and len(matches) == 1
        named = any(label in line.lower() for label in ('sha256', 'sha ', 'source', 'test', 'patch',
                    'hash', 'probe', 'review', '.json', '.py', '.patch',
                    '"src/', '"scripts/', '"cargo.', '"pyproject.', '"uv.lock"'))
        historical = exact and any(i['file'] == filename and i['line'] == finding['line_number']
                        and i.get('digest') == matches[0] and i['exact_line'] == line
                        and i['reason'] for i in history)
        synthetic_path = finding['type'] == 'Base64 High Entropy String' and any(
                        i.get('kind') == 'SYNTHETIC_TEMPORARY_PATH'
                        and i['file'] == filename and i['line'] == finding['line_number']
                        and i['detector_fingerprint'] == finding['hashed_secret']
                        and i['exact_line'] == line and i['reason'] for i in history)
        valid = (exact and ((matches[0] in known and named) or historical)) or synthetic_path
        item = {'file': filename, 'line': finding['line_number'], 'detector': finding['type'],
                'detector_fingerprint': finding['hashed_secret'], 'exact_digest_match': exact,
                'known_artifact_digest': exact and matches[0] in known,
                'individual_historical_binding': historical,
                'classification': ('SYNTHETIC_TEMPORARY_PATH_FALSE_POSITIVE' if synthetic_path
                        else 'RECORDED_SHA256_FALSE_POSITIVE' if valid else 'UNRESOLVED')}
        if not valid:
            item['exact_line'] = line
        reviewed.append(item)
unresolved = [v for v in reviewed if v['classification'] == 'UNRESOLVED']
(OUT / 'secrets-unresolved.json').write_text(json.dumps(unresolved, indent=2) + '\n')
source_results = json.loads((OUT / 'secrets-source-final.json').read_text())['results']
doc_results = json.loads((OUT / 'secrets-docs-final.json').read_text())['results']
assert not source_results and not doc_results, (len(source_results), len(doc_results))
assert not unresolved, [(v['file'], v['line'], v['detector']) for v in unresolved]
assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
           for name, digest in preservation['final_sha256'].items())
result = {'status': 'PASS', 'cutoff_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
          'source_files': len(source), 'source_findings': 0, 'document_files': len(documents),
          'document_findings': 0, 'evidence_input_files': len(inputs), 'evidence_raw_findings': len(reviewed),
          'reviewed_digest_false_positives': sum(v['classification'] == 'RECORDED_SHA256_FALSE_POSITIVE' for v in reviewed),
          'reviewed_synthetic_path_false_positives': sum(v['classification'] == 'SYNTHETIC_TEMPORARY_PATH_FALSE_POSITIVE' for v in reviewed),
          'unresolved': 0, 'findings': reviewed,
          'input_paths': [str(p.relative_to(ROOT)) for p in inputs], 'excluded_outputs': sorted(excluded),
          'private_data_read': False, 'network_verification': False,
          'annotation_only_updates_after_cutoff_excluded': True}
(OUT / 'secrets-review-final.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('findings', 'input_paths')}, indent=2))
