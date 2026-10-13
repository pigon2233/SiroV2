"""Run final FIX-013 tests against the exact captured pre-card SQLite module."""
from pathlib import Path
import hashlib
import json
import sys
import types
import pytest

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
source = OUT / 'before/src/siro/persistence/sqlite.py'
raw = source.read_bytes()
expected = json.loads((OUT / 'baseline.json').read_text())['hashes']['src/siro/persistence/sqlite.py']
assert hashlib.sha256(raw).hexdigest() == expected
module = types.ModuleType('siro.persistence.sqlite')
module.__file__ = str(source)
sys.modules[module.__name__] = module
exec(compile(raw, str(source), 'exec'), module.__dict__)
print('captured_precard_sha256:', expected, flush=True)
raise SystemExit(pytest.main([
    str(ROOT / 'tests/integration/test_sqlite_restore_validation.py'),
    str(ROOT / 'tests/integration/test_sqlite_restore_lifecycle.py'), '-q',
]))
