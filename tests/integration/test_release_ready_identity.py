from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import siro.core.releases as releases
import siro.services.presentation.gateway as gateway
from siro.adapters.data_ownership import exclusive_data_owner
from siro.persistence.sqlite import load_migrations
from siro.services.presentation.gateway import GatewayState, create_app


def identity(tmp_path: Path) -> Any:
    cls = getattr(releases, "VerifiedRelease", None)
    assert cls is not None, "signed readiness needs explicit verified launch identity"
    return cls("2.0.0", "0" * 64, tmp_path, 1)


def test_default_ready_wire_shape_remains_unchanged() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/health/ready").json() == {"state": "healthy"}


def test_release_ready_identity_exists_only_after_completed_startup(tmp_path: Path) -> None:
    app = create_app(verified_release=identity(tmp_path))
    with TestClient(app) as client:
        assert client.get("/health/ready").json() == {
            "state": "healthy",
            "release": {"version": "2.0.0", "source_sha256": "0" * 64},
        }
    with TestClient(app, raise_server_exceptions=True) as client:
        # Re-entering lifespan is a new startup, not an old ready snapshot.
        assert client.get("/health/ready").json()["release"]["version"] == "2.0.0"


def test_release_ready_without_lifespan_cannot_claim_healthy(tmp_path: Path) -> None:
    app = create_app(verified_release=identity(tmp_path))
    client = TestClient(app)
    try:
        assert client.get("/health/ready").json() == {"state": "starting"}
    finally:
        client.close()


def test_failed_release_startup_does_not_publish_ready_identity(tmp_path: Path) -> None:
    async def startup() -> None:
        raise RuntimeError("synthetic startup failure")

    app = create_app(verified_release=identity(tmp_path), on_startup=startup)
    with pytest.raises(RuntimeError, match="synthetic startup failure"), TestClient(app):
        pass
    client = TestClient(app)
    try:
        assert client.get("/health/ready").json() == {"state": "draining"}
    finally:
        client.close()


def test_release_drain_removes_identity_and_reports_real_health(tmp_path: Path) -> None:
    state = GatewayState()
    app = create_app(verified_release=identity(tmp_path), state=state)
    with TestClient(app) as client:
        assert "release" in client.get("/health/ready").json()
    client = TestClient(app)
    try:
        assert client.get("/health/ready").json() == {"state": "draining"}
    finally:
        client.close()


def runtime_fixture(tmp_path: Path) -> tuple[Any, Path, dict[str, Path]]:
    directory = tmp_path / "selected"
    origins = {
        "package_file": directory / "src/siro/__init__.py",
        "gateway_file": directory / "src/siro/services/presentation/gateway.py",
        "release_file": directory / "src/siro/core/releases.py",
    }
    for p in origins.values():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# synthetic loaded-origin fixture\n")
    database = tmp_path / "data.db"
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("CREATE TABLE schema_migrations(version INTEGER)")
        db.execute("INSERT INTO schema_migrations VALUES(1)")
        db.execute("CREATE TABLE retained(value TEXT)")
        db.execute("INSERT INTO retained VALUES('latest-completed')")
    return releases.VerifiedRelease("2.0.0", "0" * 64, directory, 1), database, origins


def test_runtime_identity_accepts_exact_origins_without_database_writes(tmp_path: Path) -> None:
    selected, database, origins = runtime_fixture(tmp_path)
    before = database.read_bytes()
    selected.validate_runtime(database, **origins, current_schema=1)
    assert database.read_bytes() == before


@pytest.mark.parametrize("origin", ["package_file", "gateway_file", "release_file"])
def test_runtime_identity_refuses_mixed_loaded_sources(tmp_path: Path, origin: str) -> None:
    selected, database, origins = runtime_fixture(tmp_path)
    origins[origin] = tmp_path / "foreign-source.py"
    before = database.read_bytes()
    with pytest.raises(releases.ReleaseLaunchError) as error:
        selected.validate_runtime(database, **origins, current_schema=1)
    assert error.value.status == "wrong_loaded_source"
    assert database.read_bytes() == before


@pytest.mark.parametrize("target_schema", [0, 2])
def test_source_selection_never_performs_implicit_schema_migration(
    tmp_path: Path, target_schema: int
) -> None:
    selected, database, origins = runtime_fixture(tmp_path)
    before = database.read_bytes()
    with pytest.raises(releases.ReleaseLaunchError) as error:
        selected.validate_runtime(database, **origins, current_schema=target_schema)
    assert error.value.status == "schema_migration_required"
    assert database.read_bytes() == before


@pytest.mark.parametrize("defect", ["missing", "empty", "advanced"])
def test_data_schema_changed_after_selection_refuses_before_startup(
    tmp_path: Path, defect: str
) -> None:
    selected, database, origins = runtime_fixture(tmp_path)
    if defect == "missing":
        database.unlink()
        before = None
    else:
        with closing(sqlite3.connect(database)) as db, db:
            if defect == "empty":
                db.execute("DELETE FROM schema_migrations")
            else:
                db.execute("INSERT INTO schema_migrations VALUES(2)")
        before = database.read_bytes()
    with pytest.raises(releases.ReleaseLaunchError) as error:
        selected.validate_runtime(database, **origins, current_schema=1)
    assert error.value.status == "data_schema_changed"
    assert (database.read_bytes() if database.exists() else None) == before


def test_selected_gateway_rechecks_schema_under_real_owner_before_composition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pwd

    monkeypatch.setattr(pwd, "getpwuid", lambda uid: SimpleNamespace(pw_dir=str(tmp_path)))
    data = tmp_path / "data"
    data.mkdir()
    database = data / "siro.db"
    schema = len(load_migrations())
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("CREATE TABLE schema_migrations(version INTEGER)")
        db.executemany(
            "INSERT INTO schema_migrations VALUES(?)", [(n,) for n in range(1, schema + 2)]
        )
    selected = releases.VerifiedRelease(
        "2.0.0", "0" * 64, Path(__file__).resolve().parents[2], schema
    )
    calls: list[Any] = []
    monkeypatch.setenv("SIRO_DATA_DIR", str(data))
    monkeypatch.setattr(gateway, "_run_gateway", lambda *a, **kw: calls.append(a))
    before = database.read_bytes()
    with pytest.raises(SystemExit, match="data_schema_changed"):
        gateway.main(verified_release=selected)
    assert calls == [] and database.read_bytes() == before
    with exclusive_data_owner(database):
        pass
