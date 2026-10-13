"""Real synthetic wrong-binding probes, without changing main source or SQLite dependencies."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
TEST = ROOT / "tests/integration/test_unknown_effect_approval.py"
ORCHESTRATOR = ROOT / "src/siro/services/tools/orchestrator.py"


async def real_guard_probe() -> dict[str, object]:
    specification = importlib.util.spec_from_file_location("synthetic_approval_fixture", TEST)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="siro-quoted-key-guard-") as temporary:
        fixture = await module.fixture_at(Path(temporary))
        original: dict[str, object] = {"argv": ["synthetic-operation"], 'quote"key': 2**80}
        run_id, old = await module.prior_call(fixture, arguments=original)
        assert old is not None
        wrong = await module.fresh_proposal(
            fixture,
            arguments={"argv": ["synthetic-operation"], 'quote"key': 2**80 + 1},
        )
        assert wrong.arguments_hash != old.arguments_hash
        await fixture.store.run_transaction(
            lambda connection: connection.execute(
                "UPDATE run_journal_calls SET proposal_id=? WHERE run_id=?",
                (wrong.proposal_id, run_id),
            )
        )
        row = await fixture.store.run_transaction(
            lambda connection: connection.execute(
                "SELECT (SELECT c.arguments_json -> fullkey FROM json_tree(c.arguments_json) "
                "WHERE type='integer') AS call_lexeme, "
                "(SELECT p.arguments_json -> fullkey FROM json_tree(p.arguments_json) "
                "WHERE type='integer') AS proposal_lexeme, "
                "(SELECT atom FROM json_tree(c.arguments_json) WHERE type='integer') "
                "AS call_atom, (SELECT atom FROM json_tree(p.arguments_json) "
                "WHERE type='integer') AS proposal_atom "
                "FROM run_journal_calls c JOIN tool_proposals p ON p.proposal_id=c.proposal_id "
                "WHERE c.run_id=?",
                (run_id,),
            ).fetchone()
        )
        assert row is not None
        assert row["call_atom"] == row["proposal_atom"]
        # Exact extraction is permitted; imprecise/wrong extraction never is.
        assert row["call_lexeme"] in (None, str(2**80))
        assert row["proposal_lexeme"] in (None, str(2**80 + 1))
        await module.assert_automatic_hold(
            fixture, await module.fresh_proposal(fixture, arguments=original)
        )
        result = {
            "python": sys.version.split()[0],
            "sqlite": sqlite3.sqlite_version,
            "numeric_atoms_collide": True,
            "call_lexeme": "NULL" if row["call_lexeme"] is None else "EXACT_EXPECTED_INTEGER_TEXT",
            "proposal_lexeme": "NULL"
            if row["proposal_lexeme"] is None
            else "EXACT_EXPECTED_INTEGER_TEXT",
            "wrong_bound_payload_has_different_hash": True,
            "actual_prior_outcome_unknown_raised": True,
            "fresh_proposal_remains_pending": True,
            "full_sqlite_dump_unchanged": True,
            "effects": len(fixture.effects),
            "no_mocked_sql_or_operator": True,
        }
    result["temporary_database_root_removed"] = not Path(temporary).exists()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true")
    arguments = parser.parse_args()
    if arguments.child:
        print(json.dumps(asyncio.run(real_guard_probe())))
        return
    state = json.loads((EVIDENCE / "scan-sqlite-public-state.json").read_text())
    temporary = Path(state["temporary_root"])
    assert temporary.parent == Path("/tmp")
    assert temporary.name.startswith("siro-fix016-sqlite-public-")
    library = temporary / "libsqlite3-probe.so"
    assert library.is_file()
    before = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (TEST, ORCHESTRATOR)
    }
    results = []
    for modern in (False, True):
        environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONPATH": str(ROOT / "src")}
        if modern:
            environment["LD_PRELOAD"] = str(library)
        run = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        assert not run.stderr
        results.append(json.loads(run.stdout))
    after = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (TEST, ORCHESTRATOR)
    }
    assert before == after
    assert results[0]["sqlite"] == "3.46.1" and results[1]["sqlite"] == "3.50.4"
    result = {
        "status": "PASS",
        "classification": "TEST_GAP / version-specific intermediate fixture assertion",
        "production_guard_regression_proven": False,
        "production_and_original_test_bytes_unchanged": True,
        "captured_public_source_sha256": before,
        "official_modern_sqlite_source": "scan-sqlite-public-state.json",
        "new_project_dependency_or_lock_change": False,
        "real_synthetic_temporary_database_probes": results,
    }
    (EVIDENCE / "scan-sqlite-portability-result.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
