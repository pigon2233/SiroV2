"""Development graph projection must not expose runtime data or host capabilities."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def helper() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/codebase_memory.py"
    spec = importlib.util.spec_from_file_location("siro_developer_graph_test_helper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def write(root: Path, relative: str, text: str = "SYNTHETIC_FIXTURE\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def track(root: Path, relative: str) -> None:
    subprocess.run(["git", "add", "--", relative], cwd=root, check=True)


def test_projection_preserves_current_source_without_git_or_runtime_data(
    helper: ModuleType, repository: Path, tmp_path: Path
) -> None:
    tracked = write(repository, "src/current.py", "VALUE = 'old'\n")
    track(repository, "src/current.py")
    tracked.write_text("VALUE = 'current uncommitted source'\n")
    write(repository, "tests/new_test.py", "def test_new(): pass\n")
    write(repository, "README.md", "Synthetic repository\n")
    write(repository, ".siro-data/private.json")
    write(repository, "docs/evidence/old-source/src/obsolete.py")
    destination = tmp_path / "projection"

    manifest = helper.prepare(repository, destination)

    assert set(manifest["files"]) == {"src/current.py", "tests/new_test.py", "README.md"}
    assert (destination / "src/current.py").read_bytes() == tracked.read_bytes()
    assert manifest["files"]["src/current.py"] == hashlib.sha256(tracked.read_bytes()).hexdigest()
    assert manifest["total_bytes"] == sum(
        (destination / relative).stat().st_size for relative in manifest["files"]
    )
    assert not (destination / ".git").exists()
    assert not (destination / ".siro-data").exists()


@pytest.mark.parametrize(
    "relative",
    [
        ".siro-data/private.json",
        "config/providers.json",
        "src/.env.local",
        "src/nested/.env.secret.json",
        "firmware/secrets.h",
        "src/credentials.json",
        "scripts/access-token.json",
        "src/.venv/lib/secret.py",
        "src/venv/lib/dependency.py",
        "src/vendor/dependency.py",
        "runtime/vendored/dependency.rs",
        "src/generated/client.py",
        "runtime/target/debug/dependency.rs",
        "src/node_modules/dependency.js",
        "tests/__pycache__/generated.py",
    ],
)
def test_projection_excludes_sensitive_and_dependency_paths_even_if_tracked(
    helper: ModuleType, repository: Path, relative: str
) -> None:
    write(repository, relative)
    track(repository, relative)

    assert Path(relative) not in helper.source_paths(repository)


@pytest.mark.parametrize("tracked_first", [False, True])
def test_projection_excludes_gitignored_files(
    helper: ModuleType, repository: Path, tracked_first: bool
) -> None:
    write(repository, "src/private_fixture.json")
    if tracked_first:
        track(repository, "src/private_fixture.json")
    write(repository, ".gitignore", "src/private_fixture.json\n")

    assert Path("src/private_fixture.json") not in helper.source_paths(repository)


def test_projection_never_follows_source_symlinks(
    helper: ModuleType, repository: Path, tmp_path: Path
) -> None:
    outside = write(tmp_path, "outside/private.py")
    (repository / "src").mkdir()
    (repository / "src/leak.py").symlink_to(outside)
    (repository / "src/shortcut").symlink_to(outside.parent, target_is_directory=True)
    track(repository, "src")

    assert helper.source_paths(repository) == []


def test_projection_refuses_overwrite(helper: ModuleType, repository: Path, tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = write(destination, "sentinel.py")

    with pytest.raises(FileExistsError):
        helper.prepare(repository, destination)

    assert sentinel.read_text() == "SYNTHETIC_FIXTURE\n"


def test_projection_enforces_per_file_budget(
    helper: ModuleType, repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(repository, "src/large.py", "1234")
    monkeypatch.setattr(helper, "MAX_FILE_BYTES", 3)

    with pytest.raises(ValueError, match="budget"):
        helper.prepare(repository, tmp_path / "projection")


def test_projection_enforces_aggregate_budget(
    helper: ModuleType, repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(repository, "src/a.py", "123")
    write(repository, "src/b.py", "456")
    monkeypatch.setattr(helper, "MAX_TOTAL_BYTES", 5)

    with pytest.raises(ValueError, match="budget"):
        helper.prepare(repository, tmp_path / "projection")


def test_projection_rechecks_actual_bytes_when_source_grows_during_read(
    helper: ModuleType, repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write(repository, "src/growing.py", "1")
    original_read = Path.read_bytes

    def read_after_growth(path: Path) -> bytes:
        return b"123456" if path == source else original_read(path)

    monkeypatch.setattr(helper, "MAX_FILE_BYTES", 4)
    monkeypatch.setattr(Path, "read_bytes", read_after_growth)

    with pytest.raises(ValueError, match="budget"):
        helper.prepare(repository, tmp_path / "projection")


def test_query_requires_a_verified_index(
    helper: ModuleType, repository: Path, tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError, match="verified index"):
        helper.require_current_index(repository, tmp_path / "tool")


@pytest.mark.parametrize("change", ["edit", "add", "delete"])
def test_query_rejects_a_stale_source_snapshot(
    helper: ModuleType, repository: Path, tmp_path: Path, change: str
) -> None:
    source = write(repository, "src/current.py", "VALUE = 1\n")
    home = tmp_path / "tool"
    manifest = helper.prepare(repository, home / "source/SiroV2")
    write(home, "source-manifest.json", json.dumps(manifest))
    write(home, "index-ready.json", '{"status":"indexed"}\n')
    helper.require_current_index(repository, home)

    if change == "edit":
        source.write_text("VALUE = 2\n")
    elif change == "add":
        write(repository, "src/added.py", "VALUE = 3\n")
    else:
        source.unlink()

    with pytest.raises(RuntimeError, match="Source changed"):
        helper.require_current_index(repository, home)


def test_sandbox_command_has_no_host_home_network_or_writable_source(
    helper: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(helper.shutil, "which", lambda _: "/usr/bin/bwrap")
    command = helper.sandbox_command(tmp_path, ["--tool-profile=analysis"])

    assert "--unshare-all" in command
    assert "--share-net" not in command
    assert "--die-with-parent" in command
    readonly_mounts = [
        tuple(command[index + 1 : index + 3])
        for index, argument in enumerate(command)
        if argument == "--ro-bind"
    ]
    writable_mounts = [
        tuple(command[index + 1 : index + 3])
        for index, argument in enumerate(command)
        if argument == "--bind"
    ]
    assert (str(tmp_path / "release"), "/opt/cbm") in readonly_mounts
    assert (str(tmp_path / "source/SiroV2"), "/workspace/projects/SiroV2") in readonly_mounts
    assert writable_mounts == [(str(tmp_path / "cache"), "/cache")]
    assert command[-1] == "--tool-profile=analysis"
    assert str(Path.home()) not in command


def test_missing_bubblewrap_fails_closed(
    helper: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(helper.shutil, "which", lambda _: None)

    with pytest.raises(RuntimeError, match="bubblewrap"):
        helper.sandbox_command(tmp_path, ["--version"])


def test_main_does_not_forward_host_credentials(
    helper: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = repository / ".siro-data/developer-tools/codebase-memory" / helper.VERSION
    release_files = {
        "codebase-memory-mcp": "synthetic executable fixture",
        "LICENSE": "synthetic license fixture",
        "THIRD_PARTY_NOTICES.md": "synthetic notices fixture",
    }
    hashes = {}
    for name, value in release_files.items():
        path = write(home, "release/" + name, value)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    write(
        repository,
        "config/development/codebase-memory.lock.toml",
        "[release_files]\n"
        + "\n".join(f"{json.dumps(k)} = {json.dumps(v)}" for k, v in hashes.items()),
    )
    captured: list[dict[str, Any]] = []

    def execute(command: list[str], **kwargs: Any) -> int:
        captured.append({"command": command, **kwargs})
        return 0

    monkeypatch.setattr(helper, "REPOSITORY", repository)
    monkeypatch.setattr(helper.shutil, "which", lambda _: "/usr/bin/bwrap")
    monkeypatch.setattr(helper.subprocess, "call", execute)
    monkeypatch.setattr(sys, "argv", ["codebase_memory.py", "version"])
    monkeypatch.setenv("SIRO_SYNTHETIC_CREDENTIAL", "synthetic-marker-not-a-secret")

    assert helper.main() == 0
    assert len(captured) == 1
    assert captured[0]["env"] == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    assert "SIRO_SYNTHETIC_CREDENTIAL" not in captured[0]["env"]
