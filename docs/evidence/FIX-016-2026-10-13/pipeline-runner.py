"""Execute published CI source in an owned, sanitized temporary archive."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("initial", "final", "cleanup"))
    parser.add_argument("--replacement", action="append", default=[])
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[3]
    evidence = Path(__file__).resolve().parent
    state_path = evidence / "pipeline-state.json"
    commit = "d1f5d07c6c9ab8e8f17b091fcf9ea387685803d5"
    if args.phase == "initial":
        root = Path(tempfile.mkdtemp(prefix="siro-fix016-pipeline-"))
        archive = root / "published.tar"
        with archive.open("wb") as output:
            subprocess.run(
                ["git", "archive", "--format=tar", commit],
                cwd=repository,
                stdout=output,
                check=True,
            )
        checkout = root / "checkout"
        checkout.mkdir()
        with tarfile.open(archive) as public_archive:
            public_archive.extractall(checkout, filter="data")
        archive.unlink()
        scratch = root / "tmp"
        scratch.mkdir()
        toolchain = checkout / "rust-toolchain.toml"
        original = toolchain.read_text()
        assert 'components = ' not in original
        toolchain.write_text(original + 'components = ["rustfmt", "clippy"]\n')
        state = {
            "published_commit": commit,
            "root": str(root),
            "checkout": str(checkout),
            "initial_temporary_only_change": "rust-toolchain.toml explicit rustfmt/clippy",
            "production_repository_modified": False,
            "runs": [],
        }
    else:
        state = json.loads(state_path.read_text())
        root = Path(state["root"])
        checkout = Path(state["checkout"])
        scratch = Path(state.get("scratch", str(root / "tmp")))
    if args.phase == "cleanup":
        import shutil

        shutil.rmtree(root)
        if scratch != root / "tmp":
            shutil.rmtree(scratch)
        state["temporary_root_removed"] = not root.exists()
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        print(json.dumps({"temporary_root_removed": not root.exists()}))
        return
    replacements = []
    for relative in args.replacement:
        source = repository / relative
        target = checkout / relative
        assert source.is_file()
        assert relative in {"scripts/check", "rust-toolchain.toml", "scripts/check_secrets.py", "tests/integration/test_ci_secret_gate.py", "runtime/siro-runtime/src/linux.rs", ".github/workflows/check.yml", "tests/integration/test_unknown_effect_approval.py", "src/siro/services/audio/tts.py", "tests/integration/test_tts_import_boundary.py"}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        replacements.append({"path": relative, "sha256": digest(target)})
    (root / "config").mkdir(exist_ok=True)
    environment = {
        "PATH": "/home/jasonliao/.local/bin:/home/jasonliao/.cargo/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": "/home/jasonliao",
        "LANG": "C.UTF-8",
        "TMPDIR": str(scratch),
        "XDG_CONFIG_HOME": str(root / "config"),
    }
    log_path = evidence / f"pipeline-{args.phase}.log"
    started = time.monotonic()
    with log_path.open("w") as output:
        outcome = subprocess.run(
            [str(checkout / "scripts/check")],
            cwd=checkout,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=1800,
        )
    run = {
        "phase": args.phase,
        "command": "scripts/check",
        "exit_code": outcome.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "log": log_path.name,
        "environment_keys": sorted(environment),
        "replacements": replacements,
        "children_joined": True,
        "uv_lock_sha256": digest(checkout / "uv.lock"),
        "cargo_lock_sha256": digest(checkout / "Cargo.lock"),
        "python_version_sha256": digest(checkout / ".python-version"),
        "check_script_sha256": digest(checkout / "scripts/check"),
    }
    state["runs"].append(run)
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(run))


if __name__ == "__main__":
    main()
