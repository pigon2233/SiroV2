"""Create a public checkpoint while preserving the complete local private history."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
os.chdir(ROOT)
scope = json.loads((OUT / 'push-review-final-scope.json').read_text())
paths = set(scope['paths']) - {':memory:.ses'}
paths.add('docs/evidence/PUBLIC_PUSH_SCOPE.md')
verification = json.loads((OUT / 'push-public-profile-checksums.json').read_text())
assert len(verification['files']) == 5 and all(p['match'] for p in verification['files'])
assert not any(p.startswith(('.siro-data/', '.codex/', 'docs/runtime-evolution/verification/',
                            'docs/evidence/FIX-015-2026-10-13/')) for p in paths)
assert 'tests/integration/test_sqlite_backup_lifecycle.py' not in paths
assert not any(p.endswith(('.wav', '.safetensors', '.onnx', '.bin')) for p in paths)
assert not any(Path(p).is_symlink() for p in paths)
local_head = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
public_parent = '5d83b0565862afafbb511d4dbf90d43d2a21c051'
backup = 'local-backup/pre-public-push-2026-10-13'
with tempfile.TemporaryDirectory(prefix='siro-public-git-index-') as raw:
    env = {**os.environ, 'GIT_INDEX_FILE': str(Path(raw) / 'index')}
    subprocess.run(['git', 'read-tree', '--empty'], env=env, check=True)
    subprocess.run(['git', '--literal-pathspecs', 'add', '--pathspec-from-file=-',
                    '--pathspec-file-nul'], input=b'\0'.join(p.encode() for p in sorted(paths)) + b'\0',
                   env=env, check=True)
    tree = subprocess.check_output(['git', 'write-tree'], env=env).decode().strip()
    actual = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', tree]).decode().splitlines()
    assert set(actual) == paths
    commit = subprocess.check_output(['git', 'commit-tree', tree, '-p', public_parent],
                input=b'Publish verified runtime evolution checkpoint through D50\n\n'
                      b'Keep private runtime/model/audio and machine settings local; '
                      b'preserve original local history separately.\n', env=env).decode().strip()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip() == local_head
    assert subprocess.check_output(['git', 'branch', '--show-current']).decode().strip() == 'main'
    assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
    subprocess.run(['git', 'branch', '-m', 'main', backup], check=True)
    subprocess.run(['git', 'branch', 'main', commit], check=True)
    subprocess.run(['git', 'symbolic-ref', 'HEAD', 'refs/heads/main'], check=True)
    subprocess.run(['git', 'read-tree', commit], check=True)
    assert subprocess.check_output(['git', 'rev-parse', backup]).decode().strip() == local_head
    reachable = subprocess.check_output(['git', 'rev-list', '--objects', commit,
                                        '^' + public_parent]).decode().splitlines()
    assert not any(' .siro-data/' in p or ' .codex/' in p or p.endswith('.wav') for p in reachable)
    assert local_head not in subprocess.check_output(['git', 'rev-list', commit]).decode().splitlines()
result = {'status': 'PUBLIC_CHECKPOINT_READY', 'local_history_backup_branch': backup,
          'original_local_head': local_head, 'public_commit': commit, 'public_tree': tree,
          'public_parent': public_parent, 'public_files': len(paths), 'private_ancestor_published': False,
          'working_files_removed_or_reset': False, 'profile_public_checksums_verified': 5,
          'push_completed': False}
(OUT / 'public-checkpoint-ready.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
