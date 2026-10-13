"""Verify captured CLI/Gateway missing ownership; new lower helper is a positive control."""
from pathlib import Path
import hashlib,json,sys,types
import pytest
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
expected=json.loads((OUT/'baseline.json').read_text())['hashes']
for name,path in (('siro.cli','src/siro/cli.py'),('siro.services.presentation.gateway','src/siro/services/presentation/gateway.py')):
 source=OUT/'before'/path;raw=source.read_bytes()
 assert hashlib.sha256(raw).hexdigest()==expected[path]
 module=types.ModuleType(name);module.__file__=str(source)
 sys.modules[name]=module;exec(compile(raw,str(source),'exec'),module.__dict__)
 print('captured source SHA256:',path,expected[path],flush=True)
raise SystemExit(pytest.main([str(ROOT/'tests/integration/test_data_owner_callers.py'),'-q','-k','not actual_cli_repeated_sigint and not actual_gateway_process']))
