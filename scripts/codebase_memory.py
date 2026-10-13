#!/usr/bin/env python3
"""Local development graph only: filtered source, no network, no runtime integration."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
VERSION = "0.11.0"
SOURCE_ROOTS = frozenset({"src", "runtime", "tests", "scripts", "schemas", "firmware"})
ROOT_FILES = frozenset({"pyproject.toml", "Cargo.toml", "rust-toolchain.toml", "README.md"})
SUFFIXES = frozenset({".py", ".rs", ".html", ".js", ".ts", ".json", ".toml", ".h", ".cpp"})
BLOCKED_PARTS = frozenset(
    {
        ".git",
        ".siro-data",
        "__pycache__",
        "node_modules",
        "target",
        "build",
        "dist",
        ".venv",
        "venv",
        "site-packages",
        "vendor",
        "vendored",
        "deps",
        "generated",
    }
)
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024


def source_paths(repository: Path) -> list[Path]:
    """Use Git's inventory, including current untracked source, never a home-directory scan."""
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repository,
    )
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin", "-z"],
        input=output,
        cwd=repository,
        capture_output=True,
        check=False,
    )
    if ignored.returncode not in {0, 1}:
        raise RuntimeError("Could not validate Git ignore rules")
    excluded = set(ignored.stdout.decode().split("\0"))
    result = []
    for raw in sorted(set(output.decode().split("\0")) - {""}):
        relative = Path(raw)
        if raw in excluded:
            continue
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe Git path")
        if any(part in BLOCKED_PARTS for part in relative.parts):
            continue
        if any(part.startswith(".env") or part == "secrets.h" for part in relative.parts):
            continue
        if any(
            marker in part.lower()
            for part in relative.parts
            for marker in (
                "credential",
                "private-key",
                "private_key",
                "auth-token",
                "auth_token",
                "access-token",
                "access_token",
            )
        ):
            continue
        accepted = (
            relative.parts[0] in SOURCE_ROOTS
            and (relative.suffix in SUFFIXES or relative.parent == Path("scripts"))
        ) or raw in ROOT_FILES
        accepted |= relative.parts[0] == "config" and ".example." in relative.name
        if not accepted:
            continue
        path = repository / relative
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            continue
        if path.is_file():
            result.append(relative)
    return result


def prepare(repository: Path, destination: Path) -> dict[str, object]:
    """Build a disposable projection; record exact source hashes rather than copying Git history."""
    if destination.exists():
        raise FileExistsError("projection exists; use the index command to refresh it")
    files: dict[str, str] = {}
    total = 0
    for relative in source_paths(repository):
        path = repository / relative
        size = path.stat().st_size
        if size > MAX_FILE_BYTES or total + size > MAX_TOTAL_BYTES or len(files) >= 5000:
            raise ValueError("source projection exceeds development budget")
        data = path.read_bytes()
        if len(data) > MAX_FILE_BYTES or total + len(data) > MAX_TOTAL_BYTES:
            raise ValueError("source changed beyond development budget")
        total += len(data)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[str(relative)] = hashlib.sha256(data).hexdigest()
    return {"repository": str(repository), "files": files, "total_bytes": total}


def require_current_index(repository: Path, home: Path) -> None:
    if not (home / "index-ready.json").is_file():
        raise RuntimeError("No verified index; run scripts/codebase_memory.py index")
    manifest = json.loads((home / "source-manifest.json").read_text())
    current = {
        str(path): hashlib.sha256((repository / path).read_bytes()).hexdigest()
        for path in source_paths(repository)
    }
    if current != manifest["files"]:
        raise RuntimeError("Source changed; run scripts/codebase_memory.py index before querying")


def sandbox_command(tool_home: Path, arguments: list[str]) -> list[str]:
    """Fail closed if Linux bubblewrap is unavailable; never fall back to host access."""
    bubblewrap = shutil.which("bwrap")
    if not bubblewrap:
        raise RuntimeError("Linux bubblewrap is required; see the integration report")
    return [
        bubblewrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--ro-bind",
        "/usr",
        "/usr",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/home/cbm",
        "--ro-bind",
        str(tool_home / "release"),
        "/opt/cbm",
        "--ro-bind",
        str(tool_home / "source/SiroV2"),
        "/workspace/projects/SiroV2",
        "--bind",
        str(tool_home / "cache"),
        "/cache",
        "--chdir",
        "/workspace/projects/SiroV2",
        "--setenv",
        "HOME",
        "/home/cbm",
        "--setenv",
        "CBM_CACHE_DIR",
        "/cache",
        "--setenv",
        "CBM_ALLOWED_ROOT",
        "/workspace/projects/SiroV2",
        "--setenv",
        "CBM_WORKERS",
        "2",
        "--setenv",
        "CBM_MEM_BUDGET_MB",
        "512",
        "/opt/cbm/codebase-memory-mcp",
        *arguments,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["index", "serve", "config", "version"])
    options = parser.parse_args()
    home = REPOSITORY / ".siro-data/developer-tools/codebase-memory" / VERSION
    lock_path = REPOSITORY / "config/development/codebase-memory.lock.toml"
    lock = tomllib.loads(lock_path.read_text())
    for name, expected in lock["release_files"].items():
        if hashlib.sha256((home / "release" / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("pinned release mismatch: " + name)
    home.mkdir(parents=True, exist_ok=True)
    (home / "cache").mkdir(exist_ok=True, mode=0o700)
    with (home / "session.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if options.action == "index":
            projection = home / "source/SiroV2"
            pending = home / "source/pending"
            if pending.exists():
                shutil.rmtree(pending)
            manifest = prepare(REPOSITORY, pending)
            (home / "index-ready.json").unlink(missing_ok=True)
            if projection.exists():
                shutil.rmtree(projection)
            pending.rename(projection)
            (home / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        elif options.action == "serve":
            require_current_index(REPOSITORY, home)
        environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}

        def run(args: list[str], *, diagnostic: bool = False) -> int:
            return subprocess.call(
                sandbox_command(home, args),
                env=environment,
                stdout=sys.stderr if diagnostic else None,
            )

        if options.action in {"index", "serve"}:
            for key in ("watcher_enabled", "auto_watch", "auto_index", "ui_enabled"):
                if run(["config", "set", key, "false"], diagnostic=True):
                    return 1
        if options.action == "index":
            result = run(
                [
                    "cli",
                    "--quiet",
                    "index_repository",
                    "--repo-path",
                    "/workspace/projects/SiroV2",
                    "--name",
                    "SiroV2",
                ]
            )
            if result == 0:
                (home / "index-ready.json").write_text('{"status":"indexed"}\n')
            return result
        if options.action == "serve":
            return run(["--tool-profile=analysis"])
        if options.action == "config":
            return run(["config", "list"])
        return run(["--version"])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
