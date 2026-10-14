from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from siro.core.releases import ReleaseManager
from siro.persistence.sqlite import load_migrations

KEY = b"synthetic-d52-fixture-key"


def launcher_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Path, Path]:
    source = Path(__file__).resolve().parents[2] / "scripts/launch_companion.py"
    spec = importlib.util.spec_from_file_location("signed_companion_launcher", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "__file__", str(project / "scripts/launch_companion.py"))
    for key in tuple(os.environ):
        if key.startswith("SIRO_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic-local")
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    binary = project / "target/debug/siro-runtime"
    binary.parent.mkdir(parents=True)
    binary.touch()
    renderer = project / "renderer"
    renderer.mkdir()
    (renderer / "index.html").write_text("synthetic renderer, not a real character")
    monkeypatch.setenv("SIRO_LIVE2D_DIST", "renderer")
    data = project / "existing-data"
    data.mkdir()
    with closing(sqlite3.connect(data / "siro.db")) as db, db:
        db.execute("CREATE TABLE schema_migrations(version INTEGER)")
        db.executemany(
            "INSERT INTO schema_migrations VALUES(?)", [(m.version,) for m in load_migrations()]
        )
        db.execute("CREATE TABLE fixture(value TEXT)")
        db.execute("INSERT INTO fixture VALUES ('latest-completed')")
    monkeypatch.setenv("SIRO_DATA_DIR", "existing-data")
    root = tmp_path / "manager"
    bundle = root / "releases/2.0.0"
    for relative in (
        "src/siro/__init__.py",
        "src/siro/core/releases.py",
        "src/siro/services/presentation/gateway.py",
    ):
        p = bundle / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# synthetic prepared source fixture\n")
    manifest = {
        "version": "2.0.0",
        "source_sha256": ReleaseManager._digest_v2(bundle),
        "min_schema": len(load_migrations()),
        "max_schema": len(load_migrations()),
        "signing_format": "siro-release-manifest-v2",
    }
    signature = hmac.new(
        KEY,
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(),
        hashlib.sha256,
    ).hexdigest()
    receipt = root / "manifests/2.0.0.json"
    receipt.parent.mkdir()
    receipt.write_text(json.dumps({**manifest, "signature": signature}))
    (root / "active.json").write_text(json.dumps({"version": "2.0.0"}))
    monkeypatch.setenv("SIRO_RELEASE_ROOT", str(root))
    monkeypatch.setenv("SIRO_RELEASE_SIGNING_KEY", KEY.decode())
    return module, root, data


def test_signed_launcher_executes_only_selected_source_without_key_or_provisioning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, root, data = launcher_fixture(tmp_path, monkeypatch)
    executions: list[tuple[Any, ...]] = []
    monkeypatch.setattr(module.os, "execve", lambda *a: executions.append(a))
    monkeypatch.setattr(
        module.os, "execv", lambda *a: pytest.fail("signed mode must not fall back")
    )
    monkeypatch.setattr(
        module.subprocess, "run", lambda *a, **kw: pytest.fail("signed mode must not provision")
    )
    before = (data / "siro.db").read_bytes()
    module.main()
    assert len(executions) == 1
    _, argv, environment = executions[0]
    assert "-I" in argv and "-B" in argv
    assert str(root / "releases/2.0.0") in argv
    assert "SIRO_RELEASE_SIGNING_KEY" not in environment
    assert os.environ["SIRO_RELEASE_SIGNING_KEY"] == KEY.decode()
    assert environment["SIRO_DATA_DIR"] == str(data)
    assert Path.cwd() == tmp_path / "project"
    assert (data / "siro.db").read_bytes() == before


@pytest.mark.parametrize(
    "defect",
    [
        "missing_key",
        "bad_signature",
        "bad_pointer",
        "missing_database",
        "missing_runtime",
        "missing_renderer",
    ],
)
def test_selected_launcher_failure_never_falls_back_or_provisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    module, root, data = launcher_fixture(tmp_path, monkeypatch)
    if defect == "missing_key":
        monkeypatch.delenv("SIRO_RELEASE_SIGNING_KEY")
    elif defect == "bad_signature":
        p = root / "manifests/2.0.0.json"
        value = json.loads(p.read_text())
        value["signature"] = "0" * 64
        p.write_text(json.dumps(value))
    elif defect == "bad_pointer":
        (root / "active.json").write_text('{"version":"../../foreign"}')
    elif defect == "missing_database":
        (data / "siro.db").unlink()
    elif defect == "missing_runtime":
        (tmp_path / "project/target/debug/siro-runtime").unlink()
    else:
        (tmp_path / "project/renderer/index.html").unlink()
    calls: list[Any] = []
    monkeypatch.setattr(module.os, "execve", lambda *a: calls.append(a))
    monkeypatch.setattr(module.os, "execv", lambda *a: calls.append(a))
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: calls.append(a))
    pointer = (root / "active.json").read_bytes()
    with pytest.raises(SystemExit):
        module.main()
    assert calls == [] and (root / "active.json").read_bytes() == pointer
    assert not (root / "backups").exists()
