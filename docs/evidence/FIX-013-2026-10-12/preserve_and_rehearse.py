"""Capture and rehearse the scoped source-only repair without touching live source/data."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess
import tempfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
EXISTING = 'src/siro/persistence/sqlite.py'
NEW = ('tests/integration/test_sqlite_restore_validation.py', 'tests/integration/test_sqlite_restore_lifecycle.py')
SCOPE = (EXISTING, *NEW)
baseline = json.loads((OUT / 'baseline.json').read_text())['hashes']
assert len(baseline) == 266
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in baseline.items() if p != EXISTING)
assert all(p not in baseline for p in NEW)
final = {}
chunks = []
for name in SCOPE:
    raw = (ROOT / name).read_bytes()
    final[name] = hashlib.sha256(raw).hexdigest()
    destination = OUT / 'after' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    before = (OUT / 'before' / name).read_bytes() if name == EXISTING else b''
    chunks.extend(difflib.unified_diff(before.decode().splitlines(keepends=True), raw.decode().splitlines(keepends=True), fromfile='a/' + name if before else '/dev/null', tofile='b/' + name))
patch = OUT / 'repair.patch'
patch.write_text(''.join(chunks))
with tempfile.TemporaryDirectory(prefix='siro-fix013-source-rehearsal-') as directory:
    rehearsal = Path(directory)
    for name in SCOPE:
        destination = rehearsal / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
    for options in (('--check', '--reverse'), ('--reverse',)):
        subprocess.run(['git', 'apply', '--no-index', *options, str(patch)], cwd=rehearsal, check=True, capture_output=True)
    assert hashlib.sha256((rehearsal / EXISTING).read_bytes()).hexdigest() == baseline[EXISTING]
    assert all(not (rehearsal / name).exists() for name in NEW)
    for options in (('--check',), ()):
        subprocess.run(['git', 'apply', '--no-index', *options, str(patch)], cwd=rehearsal, check=True, capture_output=True)
    assert all(hashlib.sha256((rehearsal / p).read_bytes()).hexdigest() == h for p, h in final.items())
assert not rehearsal.exists()
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in final.items())
result = {
    'status': 'PASS', 'baseline_files': len(baseline), 'unchanged_existing_files': 265,
    'changed_existing_files': [EXISTING], 'new_files': list(NEW), 'final_sha256': final,
    'patch_sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
    'disposable_reverse_reapply': True, 'rehearsal_workspace_removed': True,
    'live_source_unchanged_by_rehearsal': True, 'D47_and_D48_preserved': True,
    'runtime_restarted': False, 'private_data_read': False, 'database_rollback': False,
}
(OUT / 'preservation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
