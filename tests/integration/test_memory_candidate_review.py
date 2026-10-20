"""True SQLite and CLI checks for metadata-only T18/T30 review."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest

from siro.core.procedural import ProceduralCandidate, TraceStep
from siro.persistence.procedural import SQLiteProceduralCandidateRepository
from siro.persistence.sqlite import SQLiteStore

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/review_memory_candidates.py"


@pytest.fixture
def helper() -> ModuleType:
    spec = importlib.util.spec_from_file_location("memory_candidate_review", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_review_is_bounded_read_only_and_does_not_export_fixture(
    helper: ModuleType,
    tmp_path: Path,
) -> None:
    path = tmp_path / "合成 DB.sqlite"
    store = SQLiteStore(path)
    await store.initialize()
    repository = SQLiteProceduralCandidateRepository(store)
    for index in range(3):
        await repository.save(
            ProceduralCandidate(
                candidate_id=uuid4(),
                source_trace_ids=(uuid4(), uuid4()),
                workflow_hash=f"synthetic-{index}",
                capabilities=("private.capability",),
                fixture=(
                    TraceStep(
                        capability="private.capability",
                        arguments={"text": "PRIVATE_FIXTURE"},
                        result={"text": "PRIVATE_RESULT"},
                        succeeded=True,
                    ),
                ),
                created_at=datetime(2026, 10, 20, tzinfo=UTC),
            )
        )
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    output = helper.review(path, limit=2)
    assert len(output["procedural_candidates"]) == 2
    assert output["candidates_has_more"] is True
    assert output["authorizes_execution"] is False
    assert output["consolidation_runs"] == []
    text = json.dumps(output)
    for private in ("PRIVATE_FIXTURE", "PRIVATE_RESULT", "private.capability"):
        assert private not in text
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--database", str(path), "--limit", "2"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == output
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_missing_database_is_not_created(helper: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError):
        helper.review(path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--database", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["state"] == "unavailable"
    assert not path.exists()


def test_legacy_database_is_not_migrated(helper: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE old_data(value TEXT)")
    before = path.read_bytes()
    with pytest.raises(sqlite3.OperationalError):
        helper.review(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_review_rejects_unbounded_limits(helper: ModuleType, tmp_path: Path, limit: int) -> None:
    with pytest.raises(ValueError):
        helper.review(tmp_path / "missing.sqlite", limit=limit)


@pytest.mark.asyncio
async def test_review_run_metadata_excludes_keys_and_reports_unknown_state(
    helper: ModuleType,
    tmp_path: Path,
) -> None:
    path = tmp_path / "runs.sqlite"
    store = SQLiteStore(path)
    await store.initialize()
    await store.run_transaction(
        lambda c: c.executemany(
            "INSERT INTO consolidation_runs(run_id,run_key,status,checkpoint,created_at) "
            "VALUES (?,?,?,?,?)",
            [
                (f"run-{index}", f"PRIVATE_RUN_KEY_{index}", "PRIVATE_STATUS", "2", "2026-10-20")
                for index in range(3)
            ],
        )
    )
    result = helper.review(path, limit=2)
    assert result["runs_has_more"] is True
    assert len(result["consolidation_runs"]) == 2
    assert all(
        row["status"] == "unknown" and row["checkpoint"] == 2
        for row in result["consolidation_runs"]
    )
    assert "PRIVATE_" not in json.dumps(result)
