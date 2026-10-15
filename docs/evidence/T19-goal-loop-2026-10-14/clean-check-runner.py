"""Check D57 goal loop in an owned public Git checkout, excluding private runtime data."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

repo = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
root = Path(tempfile.mkdtemp(prefix="g57g-"))
scratch = Path(tempfile.mkdtemp(prefix="g57t-"))
checkout = root / "checkout"
(root / "config").mkdir()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
paths = [
    "runtime/siro-runtime/src/linux.rs",
    "src/siro/core/cognition.py",
    "src/siro/core/goal_tasks.py",
    "src/siro/persistence/goals.py",
    "src/siro/persistence/migrations/014_goal_tasks.sql",
    "src/siro/services/agent/goal_tasks.py",
    "src/siro/services/presentation/gateway.py",
    "src/siro/services/presentation/static/index.html",
    "tests/integration/test_goal_task_loop.py",
    "tests/integration/test_goal_task_api.py",
    "tests/integration/test_frontend_goal_tasks.py",
    "tests/integration/test_goal_startup_isolation.py",
    "src/siro/services/tools/orchestrator.py",
    "tests/integration/test_cancel_budget_reserve.py",
    "tests/integration/test_run_journal.py",
]
env = {
    "HOME": "/home/jasonliao",
    "LANG": "C.UTF-8",
    "PATH": "/home/jasonliao/.local/bin:/home/jasonliao/.cargo/bin:/usr/local/bin:/usr/bin:/bin",
    "TMPDIR": str(scratch),
    "XDG_CONFIG_HOME": str(root / "config"),
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_LFS_SKIP_SMUDGE": "1",
}
state = {
    "public_parent": head,
    "temporary_root": str(root),
    "scratch": str(scratch),
    "status": "RUNNING",
    "main_private_tree_scanned": False,
    "source_scope": {
        path: hashlib.sha256((repo / path).read_bytes()).hexdigest() for path in paths
    },
}
state_path = evidence / "clean-check-result.json"
state_path.write_text(json.dumps(state, indent=2) + "\n")
started = time.monotonic()
exit_code = 1
try:
    with (evidence / "clean-check.log").open("w") as log:
        for command, directory, timeout in (
            (
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "https://github.com/pigon2233/SiroV2.git",
                    str(checkout),
                ],
                root,
                120,
            ),
            (["git", "fetch", "--depth", "1", "origin", head], checkout, 60),
            (["git", "checkout", "--detach", head], checkout, 30),
        ):
            subprocess.run(
                command,
                cwd=directory,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=timeout,
            )
        for path in paths:
            target = checkout / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / path, target)
        state["fetch_head_exists"] = (checkout / ".git/FETCH_HEAD").is_file()
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        result = subprocess.run(
            [str(checkout / "scripts/check")],
            cwd=checkout,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=1800,
        )
        exit_code = result.returncode
    state.update(
        status="PASS" if exit_code == 0 else "FAIL", exit_code=exit_code, children_joined=True
    )
except (OSError, subprocess.SubprocessError) as error:
    state.update(status="ERROR", error_type=type(error).__name__)
finally:
    state["elapsed_seconds"] = round(time.monotonic() - started, 3)
    state["working_source_preserved"] = all(
        hashlib.sha256((repo / path).read_bytes()).hexdigest() == expected
        for path, expected in state["source_scope"].items()
    )
    shutil.rmtree(root)
    shutil.rmtree(scratch)
    state["temporary_roots_removed"] = not root.exists() and not scratch.exists()
    state_path.write_text(json.dumps(state, indent=2) + "\n")
print(json.dumps(state))
raise SystemExit(exit_code)
