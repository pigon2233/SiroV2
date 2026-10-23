"""Read bounded T18/T30 review metadata without migrating or changing the database."""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def review(database: Path, *, limit: int = 20) -> dict[str, object]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    path = database.resolve(strict=True)
    if not path.is_file():
        raise ValueError("database must be a file")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        runs = connection.execute(
            "SELECT run_id, status, CAST(checkpoint AS INTEGER) AS checkpoint "
            "FROM consolidation_runs ORDER BY created_at DESC, run_id LIMIT ?",
            (limit + 1,),
        ).fetchall()
        candidates = connection.execute(
            "SELECT candidate_id, workflow_hash, status, "
            "json_array_length(source_trace_ids_json) AS trace_count, "
            "json_array_length(capabilities_json) AS capability_count "
            "FROM procedural_candidates ORDER BY created_at DESC, candidate_id LIMIT ?",
            (limit + 1,),
        ).fetchall()
    states = {"running", "completed", "cancelled", "failed", "interrupted"}
    return {
        "state": "available",
        "read_only": True,
        "authorizes_execution": False,
        "scope": "metadata only; not automatic learning or acceptance completion",
        "consolidation_runs": [
            {
                "run_id": row["run_id"],
                "status": row["status"] if row["status"] in states else "unknown",
                "checkpoint": row["checkpoint"],
            }
            for row in runs[:limit]
        ],
        "runs_has_more": len(runs) > limit,
        "procedural_candidates": [
            {
                "candidate_id": row["candidate_id"],
                "workflow_hash": row["workflow_hash"],
                "status": "candidate" if row["status"] == "candidate" else "unknown",
                "source_trace_count": row["trace_count"],
                "capability_count": row["capability_count"],
                "registry_checked": False,
                "installation_status": "not_checked",
            }
            for row in candidates[:limit]
        ],
        "candidates_has_more": len(candidates) > limit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="explicit existing local DB")
    parser.add_argument("--limit", type=int, default=20, help="1..100 records per list")
    args = parser.parse_args()
    try:
        result = review(args.database, limit=args.limit)
    except (OSError, ValueError, sqlite3.Error):
        print(
            json.dumps(
                {
                    "state": "unavailable",
                    "read_only": True,
                    "reason": "missing_or_incompatible_database_or_invalid_limit",
                }
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
