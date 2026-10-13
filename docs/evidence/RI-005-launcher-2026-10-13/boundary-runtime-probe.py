"""Direct DTO/real-temp-schema controls; this is not child launch attestation."""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from siro.core.releases import ReleaseLaunchError, VerifiedRelease

PROJECT = Path(__file__).resolve().parents[3]
SOURCES = (
    "src/siro/core/releases.py",
    "scripts/launch_companion.py",
    "src/siro/services/presentation/gateway.py",
)


def hashes() -> dict[str, str]:
    return {path: hashlib.sha256((PROJECT / path).read_bytes()).hexdigest() for path in SOURCES}


def schema_equivalence() -> bool:
    before = PROJECT / "docs/evidence/RI-005-launcher-2026-10-13/before/src/siro/core/releases.py"
    prior = ast.parse(before.read_text())
    current = ast.parse((PROJECT / SOURCES[0]).read_text())
    old = next(
        node
        for node in ast.walk(prior)
        if isinstance(node, ast.FunctionDef) and node.name == "_rollback_schema"
    )
    new = next(
        node
        for node in ast.walk(current)
        if isinstance(node, ast.FunctionDef) and node.name == "_read_data_schema"
    )

    class BindArguments(ast.NodeTransformer):
        def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                argument = {"_database": "database", "_schema": "maximum"}.get(node.attr)
                if argument is not None:
                    return ast.Name(id=argument, ctx=ast.Load())
            return self.generic_visit(node)

    transformed = BindArguments().visit(old)
    assert isinstance(transformed, ast.FunctionDef)
    return [ast.dump(node) for node in transformed.body] == [ast.dump(node) for node in new.body]


def main() -> None:
    start_hashes = hashes()
    cases: list[dict[str, object]] = []
    equivalence = schema_equivalence()
    assert equivalence, "D48 extracted schema primitive differs from the prior implementation"
    with TemporaryDirectory(prefix="siro-d52-boundary-") as directory:
        fixture = Path(directory)
        source = fixture / "selected/src/siro"
        paths = {
            "package_file": source / "__init__.py",
            "gateway_file": source / "services/presentation/gateway.py",
            "release_file": source / "core/releases.py",
        }
        for path in paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# direct public DTO origin fixture, not imported source\n")
        database = fixture / "siro.db"
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("CREATE TABLE schema_migrations(version INTEGER)")
            connection.executemany("INSERT INTO schema_migrations VALUES(?)", [(1,), (2,), (3,)])
            connection.execute("CREATE TABLE preserved(value TEXT)")
            connection.execute("INSERT INTO preserved VALUES('synthetic latest value')")
        identity = VerifiedRelease("2.0.0", "0" * 64, fixture / "selected", 3)

        def exercise(label: str, expected: str | None, **overrides: object) -> None:
            before_data = database.read_bytes()
            origins = dict(paths)
            current = 3
            if "current_schema" in overrides:
                current = int(str(overrides.pop("current_schema")))
            for field, override in overrides.items():
                assert isinstance(override, Path)
                origins[field] = override
            actual: str | None = None
            try:
                identity.validate_runtime(
                    database,
                    package_file=origins["package_file"],
                    gateway_file=origins["gateway_file"],
                    release_file=origins["release_file"],
                    current_schema=current,
                )
            except ReleaseLaunchError as error:
                actual = error.status
                assert str(fixture) not in str(error)
            assert actual == expected, (label, actual, expected)
            assert database.read_bytes() == before_data, "validation changed DB bytes"
            assert not database.with_name("siro.db-wal").exists()
            cases.append({"case": label, "expected_status": expected, "pass": True})

        exercise("exact_origins_and_real_matching_schema", None)
        for field in paths:
            exercise(f"wrong_{field}", "wrong_loaded_source", **{field: fixture / "host.py"})
        exercise(
            "candidate_requires_additive_migration", "schema_migration_required", current_schema=4
        )
        exercise(
            "candidate_does_not_support_current_count",
            "schema_migration_required",
            current_schema=2,
        )
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("INSERT INTO schema_migrations VALUES(4)")
        exercise("actual_schema_changed_after_selection", "data_schema_changed")
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("DELETE FROM schema_migrations WHERE version=4")
            connection.execute("DELETE FROM schema_migrations WHERE version=2")
        exercise("actual_schema_is_not_a_prefix", "data_schema_changed")
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("DROP TABLE schema_migrations")
        exercise("actual_schema_is_unknown", "data_schema_changed")
        with closing(sqlite3.connect(database)) as connection:
            assert (
                connection.execute("SELECT value FROM preserved").fetchone()[0]
                == "synthetic latest value"
            )
    finish_hashes = hashes()
    assert start_hashes == finish_hashes, "STALE_SOURCE"
    print(
        json.dumps(
            {
                "scope": "direct public DTO + real temp SQLite; no service/model/private data",
                "source_hashes": start_hashes,
                "source_stable": True,
                "prior_D48_schema_body_ast_equivalent": equivalence,
                "passed_cases": len(cases),
                "cases": cases,
                "database_bytes_preserved": True,
                "temporary_root_removed": not fixture.exists(),
                "actual_child_launch": "NOT_RUN",
                "same_uid_package_mutation": "NOT_VERIFIED",
                "maintenance_exec_handoff": "NOT_VERIFIED",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
