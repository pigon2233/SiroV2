"""Run final D48 tests against the exact captured pre-card production module only."""
from pathlib import Path
import hashlib,json,sys,types
import pytest
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
p=OUT/'before/src/siro/core/releases.py'
raw=p.read_bytes()
expected=json.loads((OUT/'baseline.json').read_text())['hashes']['src/siro/core/releases.py']
assert hashlib.sha256(raw).hexdigest()==expected
module=types.ModuleType('siro.core.releases');module.__file__=str(p)
sys.modules[module.__name__]=module
exec(compile(raw,str(p),'exec'),module.__dict__)
print('captured_precard_sha256:',expected,flush=True)
raise SystemExit(pytest.main([str(ROOT/'tests/integration/test_release_data_retention.py'),str(ROOT/'tests/integration/test_release_manager.py'),'-q']))
