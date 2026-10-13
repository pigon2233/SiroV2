"""Run final public source checks in an owned real shallow Git checkout."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time

repo = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
root = Path(tempfile.mkdtemp(prefix="f16g-"))
scratch = Path(tempfile.mkdtemp(prefix="f16t-"))
checkout = root / "checkout"
(root / "config").mkdir()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
paths = [
    "rust-toolchain.toml", "scripts/check", "scripts/check_secrets.py",
    "tests/integration/test_ci_secret_gate.py", "runtime/siro-runtime/src/linux.rs",
    ".github/workflows/check.yml", "tests/integration/test_unknown_effect_approval.py",
    "src/siro/services/audio/tts.py", "tests/integration/test_tts_import_boundary.py",
]
env = {
    "HOME": "/home/jasonliao", "LANG": "C.UTF-8",
    "PATH": "/home/jasonliao/.local/bin:/home/jasonliao/.cargo/bin:/usr/local/bin:/usr/bin:/bin",
    "TMPDIR": str(scratch), "XDG_CONFIG_HOME": str(root / "config"),
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_LFS_SKIP_SMUDGE": "1",
}
state = {"public_parent": head, "temporary_root": str(root), "scratch": str(scratch),
         "status": "RUNNING", "main_private_tree_scanned": False,
         "source_scope": {p: hashlib.sha256((repo / p).read_bytes()).hexdigest() for p in paths}}
state_path = evidence / "git-check-result.json"
state_path.write_text(json.dumps(state, indent=2) + "\n")
started = time.monotonic()
with (evidence / "git-check-final.log").open("w") as log:
    subprocess.run(["git", "clone", "--depth", "1", "https://github.com/pigon2233/SiroV2.git", str(checkout)],
                   cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    subprocess.run(["git", "fetch", "--depth", "1", "origin", head], cwd=checkout, env=env,
                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
    subprocess.run(["git", "checkout", "--detach", head], cwd=checkout, env=env,
                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
    for path in paths:
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / path, target)
    state["fetch_head_exists"] = (checkout / ".git/FETCH_HEAD").is_file()
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    result = subprocess.run([str(checkout / "scripts/check")], cwd=checkout, env=env,
                            stdout=log, stderr=subprocess.STDOUT, timeout=1800)
state.update(status="PASS" if result.returncode == 0 else "FAIL", exit_code=result.returncode,
             elapsed_seconds=round(time.monotonic() - started, 3), children_joined=True)
for path, expected in state["source_scope"].items():
    assert hashlib.sha256((repo / path).read_bytes()).hexdigest() == expected
shutil.rmtree(root)
shutil.rmtree(scratch)
state["temporary_roots_removed"] = not root.exists() and not scratch.exists()
state_path.write_text(json.dumps(state, indent=2) + "\n")
print(json.dumps(state))
