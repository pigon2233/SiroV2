"""Verification-only reproduction; production/test sources remain unchanged."""
from pathlib import Path
import tempfile
import subprocess
import os
import sys

root = Path(__file__).resolve().parents[4]
s = (root / "tests/integration/test_bounded_execution.py").read_text()
s = s[s.index('@pytest.mark.parametrize("profile"'):]
s = s.replace('["legacy", "candidate"]', '["candidate"]', 1)
s = s.replace('self.requests.append(request)', 'self.requests.append(request)\n            os.environ["SIRO_RUNTIME_PROFILE"] = "legacy"', 1)
s = s.replace('model = Model()', """model = Model()
    from siro.services.tools import execution
    bounded_calls: list[object] = []
    original = execution.execute_bounded_argv
    async def spy(*args: object, **kwargs: object) -> object:
        bounded_calls.append(args)
        return await original(*args, **kwargs)
    monkeypatch.setattr(execution, "execute_bounded_argv", spy)""", 1)
s = s.replace('assert len(model.requests) == 2', 'assert len(model.requests) == 2\n    assert bounded_calls == [], "environment mutation bypasses bounded executor"', 1)
with tempfile.TemporaryDirectory(prefix="siro-rt004-verification-") as td:
    target = Path(td) / "test_profile_probe.py"
    target.write_text('from __future__ import annotations\nimport os,sys\nfrom pathlib import Path\nimport pytest\n' + s)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", str(target)], cwd=root, env=env)
    if result.returncode == 0:
        print("CONFIRMED: candidate controller completed with zero bounded executor calls after in-process profile mutation.")
    raise SystemExit(result.returncode)
