"""Actual isolated HTTP/source identity; synthetic fixture interposition is signed."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from siro.core.releases import ReleaseManager, ReleaseManifest
from siro.persistence.sqlite import SQLiteStore, load_migrations

ROOT = Path(__file__).resolve().parents[2]
KEY = b"synthetic-d52-source-process-key"  # pragma: allowlist secret
HEALTH = (sys.executable, "-I", "-B", "-c", "pass")


def source_hashes() -> dict[str, str]:
    return {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in (
            "scripts/launch_companion.py",
            "src/siro/core/releases.py",
            "src/siro/services/presentation/gateway.py",
            "tests/integration/test_release_source_process.py",
        )
    }


def environment(root: Path, port: int) -> dict[str, str]:
    result = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SIRO_")
        and key not in {"GROQ_API_KEY", "PYTHONPATH", "PYTHONHOME"}
        and key.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}
    }
    result.update(
        SIRO_RELEASE_ROOT=str(root / "manager"),
        SIRO_RELEASE_SIGNING_KEY=KEY.decode(),  # pragma: allowlist secret
        SIRO_DATA_DIR=str(root / "data"),
        SIRO_GATEWAY_PORT=str(port),
        SIRO_OLLAMA_MODEL="synthetic-not-called",
        SIRO_CONTEXT_TOKEN_BUDGET_ENABLED="0",
        SIRO_WORKSPACE_ENABLED="0",
        SIRO_MEMORY_ORGANIZATION_ENABLED="0",
        SIRO_MEMORY_INGRESS_ENABLED="0",
        SIRO_CONTEXT_SUMMARY_ENABLED="0",
        SIRO_BROWSER_SESSION_ENABLED="0",
        SIRO_MODEL_RETRY_ENABLED="0",
        SIRO_RUNTIME_BINARY=str(root / "prepared-runtime"),
        SIRO_LIVE2D_DIST=str(root / "prepared-renderer"),
        SIRO_TEST_ACCOUNT=str(root / "synthetic-account"),
        SIRO_TEST_OBSERVATION=str(root / "observed-source.json"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    return result


def prepared_project(root: Path) -> Path:
    project = root / "project"
    (project / "scripts").mkdir(parents=True)
    launcher = project / "scripts/launch_companion.py"
    shutil.copyfile(ROOT / "scripts/launch_companion.py", launcher)
    # Assets are explicit public fixtures; neither runtime nor renderer is executed.
    (root / "prepared-runtime").write_text("synthetic asset; must not execute\n")
    renderer = root / "prepared-renderer"
    renderer.mkdir()
    (renderer / "index.html").write_text("synthetic public prepared renderer")
    assert not (project / ".env.local").exists()
    return launcher


def source_bundle(root: Path, version: str, *, unsupported_abi: bool = False) -> Path:
    bundle = root / f"bundle-{version}"
    shutil.copytree(
        ROOT / "src", bundle / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    gateway = bundle / "src/siro/services/presentation/gateway.py"
    # All fixture modifications are part of the complete actual signed digest.
    # No mocked main/IO/HTTP result: only account locator and observable origins.
    gateway.write_text(
        gateway.read_text()
        + "\n# Signed synthetic integration instrumentation, absent from production.\n"
        + "import json as _fixture_json\n"
        + "import pwd as _fixture_pwd\n"
        + "from types import SimpleNamespace as _FixtureAccount\n"
        + "_fixture_pwd.getpwuid = lambda uid: _FixtureAccount(\n"
        + "    pw_dir=os.environ['SIRO_TEST_ACCOUNT'])\n"
        + "_fixture_main = main\n"
        + "def main(*, verified_release=None):\n"
        + "    import siro\n"
        + "    import siro.core.releases as _fixture_releases\n"
        + "    Path(os.environ['SIRO_TEST_OBSERVATION']).write_text(_fixture_json.dumps({\n"
        + "        'package_file': siro.__file__, 'gateway_file': __file__,\n"
        + "        'release_file': _fixture_releases.__file__,\n"
        + "        'signing_key_present': 'SIRO_RELEASE_SIGNING_KEY' in os.environ,\n"
        + f"        'fixture_version': {version!r},\n"
        + "    }))\n"
        + "    _fixture_main(verified_release=verified_release)\n"
    )
    if unsupported_abi:
        release = bundle / "src/siro/core/releases.py"
        release.write_text(
            release.read_text()
            + "\n# Deliberately unsupported selected DTO ABI; no host fallback allowed.\n"
            + "class VerifiedRelease:\n"
            + "    def __init__(self):\n"
            + "        pass\n"
        )
    assert not list(bundle.rglob("*.pyc")) and not list(bundle.rglob("__pycache__"))
    return bundle


def signed(bundle: Path, version: str) -> ReleaseManifest:
    values: dict[str, Any] = {
        "version": version,
        "source_sha256": ReleaseManager._digest(bundle),
        "min_schema": len(load_migrations()),
        "max_schema": len(load_migrations()),
        "signing_format": "siro-release-manifest-v1",
    }
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    values["signature"] = hmac.new(KEY, payload, hashlib.sha256).hexdigest()
    return ReleaseManifest.model_validate(values)


def seed(database: Path, phase: str) -> None:
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT OR IGNORE INTO identities VALUES ('process-fixture','{}',1,'synthetic')"
        )
        connection.execute(
            "INSERT INTO conversations VALUES (?,'process-fixture','synthetic','closed')", (phase,)
        )
        connection.execute(
            "INSERT INTO turns VALUES (?,?,?,'completed',1,'synthetic')", (phase,) * 3
        )
        connection.execute(
            "INSERT INTO messages(turn_id,role,text,sequence) VALUES (?,'user',?,0)",
            (phase, f"synthetic conversation {phase}"),
        )
        connection.execute(
            "INSERT INTO memories(memory_id,identity_id,kind,text,status,confidence,revision) "
            "VALUES (?,'process-fixture','episodic',?,'committed',1,1)",
            (phase, f"synthetic memory {phase}"),
        )
        connection.execute(
            "INSERT INTO actions(action_id,idempotency_key,state,skill_id,args_hash) "
            "VALUES (?,?,'completed','synthetic-read-only','synthetic')",
            (phase,) * 2,
        )
        connection.execute("CREATE TABLE IF NOT EXISTS source_process_fixture(marker TEXT)")
        connection.execute("INSERT INTO source_process_fixture VALUES (?)", (phase,))


def retained(database: Path) -> dict[str, list[str]]:
    queries = {
        "conversation": "SELECT text FROM messages WHERE turn_id IN "
        "(SELECT turn_id FROM turns WHERE session_id IN "
        "(SELECT session_id FROM conversations WHERE identity_id='process-fixture')) ORDER BY text",
        "memory": "SELECT text FROM memories WHERE identity_id='process-fixture' ORDER BY text",
        "completed_ledger": "SELECT action_id FROM actions WHERE state='completed' "
        "ORDER BY action_id",
        "fixture": "SELECT marker FROM source_process_fixture ORDER BY marker",
    }
    with closing(sqlite3.connect(database)) as connection:
        return {
            key: [str(row[0]) for row in connection.execute(query)]
            for key, query in queries.items()
        }


def port_at() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = int(listener.getsockname()[1])
    assert port != 8026
    return port


def actual_gateway(root: Path, launcher: Path, manifest: ReleaseManifest) -> dict[str, Any]:
    source_before = source_hashes()
    selected = root / "manager/releases" / manifest.version / "src/siro"
    digest_before = ReleaseManager._digest(selected.parents[1])
    assert digest_before == manifest.source_sha256
    port = port_at()
    log_path = root / f"gateway-{manifest.version}-{time.monotonic_ns()}.log"
    observation = root / "observed-source.json"
    observation.unlink(missing_ok=True)
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-B", str(launcher)],
            env=environment(root, port),
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 20
            while True:
                assert process.poll() is None, log_path.read_text()
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/health/ready", timeout=0.3
                    ) as response:
                        ready = json.load(response)
                    if ready.get("state") == "healthy":
                        break
                except (urllib.error.URLError, TimeoutError):
                    pass
                assert time.monotonic() < deadline, log_path.read_text()
                time.sleep(0.02)
            assert ready == {
                "state": "healthy",
                "release": {"version": manifest.version, "source_sha256": manifest.source_sha256},
            }
            loaded = json.loads(observation.read_text())
            assert loaded == {
                "package_file": str(selected / "__init__.py"),
                "gateway_file": str(selected / "services/presentation/gateway.py"),
                "release_file": str(selected / "core/releases.py"),
                "signing_key_present": False,
                "fixture_version": manifest.version,
            }
            process.terminate()
            returncode = process.wait(timeout=10)
            text = log_path.read_text()
            assert returncode in (0, -signal.SIGTERM), text
            assert "Application shutdown complete." in text, text
            assert "Task was destroyed" not in text and "Traceback" not in text, text
            assert not list(selected.parent.rglob("*.pyc"))
            assert not list(selected.parent.rglob("__pycache__"))
            digest_after = ReleaseManager._digest(selected.parents[1])
            assert digest_after == manifest.source_sha256
            assert source_hashes() == source_before
            return {
                "version": manifest.version,
                "source_sha256": manifest.source_sha256,
                "origins_selected": True,
                "loaded_files": {
                    name: str(Path(loaded[name]).relative_to(root))
                    for name in ("package_file", "gateway_file", "release_file")
                },
                "signing_key_absent": True,
                "ready": ready,
                "exit_code": returncode,
                "joined": True,
                "shutdown_complete": True,
                "package_unchanged": True,
                "digest_before": digest_before,
                "digest_after": digest_after,
                "host_source_hashes": source_before,
            }
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Only a child created here can be killed; a forced cleanup
                    # never satisfies the normal graceful-shutdown assertion.
                    process.kill()
                    process.wait(timeout=3)


def test_actual_signed_source_versions_and_code_rollback_preserve_latest_data(
    tmp_path: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="signed-source-owned-", dir=tmp_path) as temporary:
        root = Path(temporary)
        launcher = prepared_project(root)
        database = root / "data/siro.db"
        asyncio.run(SQLiteStore(database).initialize())
        seed(database, "before-first")
        manager = ReleaseManager(
            root / "manager", KEY, current_schema=len(load_migrations()), database=database
        )
        observed: list[dict[str, Any]] = []
        manifests: dict[str, ReleaseManifest] = {}
        for version, phase in (("1.0.0", "after-first"), ("2.0.0", "after-second")):
            bundle = source_bundle(root, version)
            manifest = signed(bundle, version)
            manifests[version] = manifest
            assert manager.stage_and_activate(bundle, manifest, HEALTH).status == "activated"
            observed.append(actual_gateway(root, launcher, manifest))
            # New late writes occur only AFTER the actual child has joined.
            seed(database, phase)
        expected = retained(database)
        assert manager.rollback().status == "rolled_back"
        assert retained(database) == expected
        observed.append(actual_gateway(root, launcher, manifests["1.0.0"]))
        assert retained(database) == expected
        assert all(len(values) == 3 for values in expected.values())
    assert not root.exists()
    print(
        json.dumps(
            {
                "case": "signed-two-version-code-rollback",
                "status": "PASS",
                "processes": observed,
                "retained_counts": {key: len(value) for key, value in expected.items()},
                "schema_migrations": len(load_migrations()),
                "temporary_root_removed": True,
            }
        )
    )


@pytest.mark.parametrize("invalid", ["unsupported-abi", "tampered-package"])
def test_actual_invalid_signed_source_never_falls_back_or_mutates_database(
    tmp_path: Path, invalid: str
) -> None:
    with tempfile.TemporaryDirectory(prefix="signed-refusal-owned-", dir=tmp_path) as temporary:
        root = Path(temporary)
        launcher = prepared_project(root)
        database = root / "data/siro.db"
        asyncio.run(SQLiteStore(database).initialize())
        seed(database, "before-refusal")
        bundle = source_bundle(root, "1.0.0", unsupported_abi=invalid == "unsupported-abi")
        manifest = signed(bundle, "1.0.0")
        manager = ReleaseManager(
            root / "manager", KEY, current_schema=len(load_migrations()), database=database
        )
        assert manager.stage_and_activate(bundle, manifest, HEALTH).status == "activated"
        if invalid == "tampered-package":
            (root / "manager/releases/1.0.0/src/siro/__init__.py").write_text(
                "raise AssertionError('tampered selected source must never import')\n"
            )
        before = database.read_bytes()
        expected = retained(database)
        source_before = source_hashes()
        selected = root / "manager/releases/1.0.0"
        package_before = ReleaseManager._digest(selected)
        port = port_at()
        completed = subprocess.run(
            [sys.executable, "-B", str(launcher)],
            env=environment(root, port),
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert completed.returncode != 0
        if invalid == "unsupported-abi":
            assert "TypeError" in completed.stderr and "VerifiedRelease" in completed.stderr
        else:
            assert "invalid_release_target" in completed.stderr
            assert "tampered selected source" not in completed.stderr
        assert not (root / "observed-source.json").exists()
        assert database.read_bytes() == before and retained(database) == expected
        assert source_hashes() == source_before
        assert ReleaseManager._digest(selected) == package_before
        assert not list(selected.rglob("*.pyc")) and not list(selected.rglob("__pycache__"))
        with pytest.raises(urllib.error.URLError):
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=0.3)
    assert not root.exists()
    print(
        json.dumps(
            {
                "case": invalid,
                "status": "PASS",
                "exit_code": completed.returncode,
                "joined": True,
                "database_bytes_unchanged": True,
                "no_host_fallback": True,
                "temporary_root_removed": True,
                "package_unchanged": True,
                "host_source_hashes": source_before,
            }
        )
    )
