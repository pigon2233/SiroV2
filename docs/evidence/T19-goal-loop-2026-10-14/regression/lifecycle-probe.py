"""Run unchanged lifecycle tests with frozen D57 files in an owned public clone."""

import ast
import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

repo = Path(__file__).resolve().parents[4]
evidence = Path(__file__).resolve().parent
root = Path(tempfile.mkdtemp(prefix="g57l-"))
scratch = Path(tempfile.mkdtemp(prefix="g57s-"))
checkout = root / "checkout"
(root / "config").mkdir()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
runner = repo / "docs/evidence/T19-goal-loop-2026-10-14/clean-check-runner.py"
paths = next(
    ast.literal_eval(node.value)
    for node in ast.parse(runner.read_text()).body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "paths" for target in node.targets)
)
guard_paths = paths + [
    "tests/integration/test_execution_lifecycle.py",
    "scripts/check",
    "pyproject.toml",
    "uv.lock",
]
source_hashes = {
    path: hashlib.sha256((repo / path).read_bytes()).hexdigest() for path in guard_paths
}
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
state_path = evidence / "lifecycle-result.json"
state = {
    "status": "RUNNING",
    "public_parent": head,
    "root": str(root),
    "scratch": str(scratch),
    "source_scope": source_hashes,
    "main_private_tree_scanned": False,
    "commands": [],
}
state_path.write_text(json.dumps(state, indent=2) + "\n")
owned = {}


def process_table():
    result = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(") ", 1)[1].split()
            result[int(entry.name)] = (int(fields[1]), int(fields[19]), fields[0])
        except (OSError, ValueError, IndexError):
            continue
    return result


def remember_children():
    table = process_table()
    parents = {os.getpid()}
    while True:
        children = {pid for pid, data in table.items() if data[0] in parents}
        if children <= parents:
            break
        parents.update(children)
    for pid in parents - {os.getpid()}:
        owned[pid] = table[pid][1]


def command(argv, cwd, log, timeout):
    print("START " + " ".join(argv), flush=True)
    begun = time.monotonic()
    process = subprocess.Popen(
        argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
    )
    try:
        while process.poll() is None:
            remember_children()
            if time.monotonic() - begun > timeout:
                raise subprocess.TimeoutExpired(argv, timeout)
            time.sleep(0.1)
    finally:
        remember_children()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
    record = {
        "argv": argv,
        "exit_code": process.returncode,
        "elapsed_seconds": round(time.monotonic() - begun, 3),
    }
    state["commands"].append(record)
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    print("END " + json.dumps(record), flush=True)
    return process.returncode


started = time.monotonic()
exit_code = 1
try:
    with (evidence / "lifecycle-candidate.log").open("x") as log:
        for argv, directory, timeout in (
            (["git", "clone", "--depth", "1", "https://github.com/pigon2233/SiroV2.git", str(checkout)], root, 120),
            (["git", "fetch", "--depth", "1", "origin", head], checkout, 60),
            (["git", "checkout", "--detach", head], checkout, 30),
        ):
            if command(argv, directory, log, timeout):
                raise RuntimeError("public clone setup failed")
        for path in paths:
            target = checkout / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / path, target)
        state["fetch_head_exists"] = (checkout / ".git/FETCH_HEAD").is_file()
        state["original_lifecycle_test_unchanged"] = (
            hashlib.sha256((checkout / guard_paths[12]).read_bytes()).hexdigest()
            == source_hashes[guard_paths[12]]
        )
        if command(["uv", "sync", "--locked", "--all-groups"], checkout, log, 180):
            raise RuntimeError("dependency sync failed")
        exit_code = command(
            ["uv", "run", "pytest", "tests/integration/test_execution_lifecycle.py", "-vv"],
            checkout,
            log,
            180,
        )
    state["candidate_exit_code"] = exit_code
    if exit_code:
        with (evidence / "lifecycle-baseline.log").open("x") as log:
            for path in paths:
                tracked = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", path], cwd=checkout,
                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                ).returncode == 0
                if tracked:
                    subprocess.run(["git", "restore", "--source", head, "--", path], cwd=checkout, env=env, check=True)
                else:
                    (checkout / path).unlink()
            baseline_code = command(
                ["uv", "run", "pytest", "tests/integration/test_execution_lifecycle.py", "-vv"],
                checkout,
                log,
                180,
            )
            state["baseline_exit_code"] = baseline_code
    state["status"] = "PASS" if exit_code == 0 else "FAIL"
except Exception as error:
    state.update(status="ERROR", error_type=type(error).__name__, error=str(error))
finally:
    remember_children()
    table = process_table()
    survivors = [pid for pid, start in owned.items() if pid in table and table[pid][1] == start and table[pid][2] != "Z"]
    state["leftover_live_owned_pids"] = survivors
    for pid in survivors:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 3
    while survivors and time.monotonic() < deadline:
        time.sleep(0.05)
        table = process_table()
        survivors = [pid for pid in survivors if pid in table and table[pid][1] == owned[pid] and table[pid][2] != "Z"]
    state["children_joined"] = not survivors
    state["working_source_preserved"] = all(
        hashlib.sha256((repo / path).read_bytes()).hexdigest() == expected
        for path, expected in source_hashes.items()
    )
    shutil.rmtree(root)
    shutil.rmtree(scratch)
    state["temporary_roots_removed"] = not root.exists() and not scratch.exists()
    state["elapsed_seconds"] = round(time.monotonic() - started, 3)
    state_path.write_text(json.dumps(state, indent=2) + "\n")
print(json.dumps(state), flush=True)
raise SystemExit(exit_code)
