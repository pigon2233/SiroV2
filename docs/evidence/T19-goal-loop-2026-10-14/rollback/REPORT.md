# D57 — independent source-only rollback and additive-data preservation

Date: 2026-10-15 Asia/Taipei. Public baseline: `5c67c6f78f36833e526626b2d3481654bd823165`. Final result: **PASS**, limited to an owned source copy and synthetic SQLite fixture. No runtime deployment, operational rollback, signed-release approval or live-data rollback was performed.

## Exact source rehearsal

`rollback-probe.py` extracts the public baseline's source, original tests, runtime and build files into one owned temporary directory. It copies only the eight frozen candidate production paths into that archive and produces a real Git binary patch for those paths. Five existing paths change: Rust `linux.rs`, Core `cognition.py`, persistence `goals.py`, Gateway and its page. Three paths are additive: Core `goal_tasks.py`, agent `goal_tasks.py` and migration014.

The probe performs actual `git apply --reverse --check`, `git apply --reverse`, `git apply --check` and `git apply`. All return EXIT0. The reversed tree equals the public baseline byte for byte; the reapplied tree equals the candidate tree byte for byte. The three new source files are absent during reversal. The only eight differences between candidate and reversed tree are the intended paths. `rollback-result.json` retains the complete before/baseline/reversed/reapplied SHA256 maps and the exact patch path set. Raw `production-eight-paths.patch` SHA256: `0d8a19ea089bc67960dc674ea817147e21be87cec44ed3a0b30bc9f7b6b3b5c4`.

There are **303 unrelated archived public files** preserved during reversal, including **135 original Python test/helper files** and **13 original migration files**. The probe also hashes **315 existing/new source, test and build files in the shared workspace** before and after, including all four new integration tests; every hash matches. It never reverses the working source, changes an original test or creates a commit.

## Actual synthetic task and caller withdrawal

The first child imports only the candidate source under the owned archive, initializes an empty synthetic database to schema14 and adds one legacy Goal with its original fields and NULL task metadata. It then starts the real `ReadTaskOwner`, proposes an exact synthetic file path, verifies zero reads before approval, explicitly approves that revision and waits for the actual completed goal. The controlled adapter reads a real small fixture file through file IO; it is not a Rust driver, provider or general OS cancellation demonstration.

The actual source observation records SHA256 `136af48b26f5a325fa877ee78a78b6b84340a02d2cb19824887426a0997ea4c8`, an aware read time, explicit approval time and three sourced lines. One read consumes one step and produces one completed typed observation and one planning history row. Reading those TODO/FIXME lines performs no listed TODO.

Before any source reversal, the child explicitly sets `SIRO_GOAL_TASKS_ENABLED=0`, awaits `ReadTaskOwner.close()`, verifies the owned task/context/active slot cleared and joins its asyncio work. That child then exits and is joined. The reversed and reapplied children retain feature-off and never start a new caller. `database-initialize.json` retains the withdrawal facts.

## Schema14 and latest-data preservation

Each source phase reopens the **same** owned synthetic database. The unchanged `SQLiteStore.initialize()` and original repository run against the reversed source. The original repository reads the legacy Goal's fields unchanged and can read the completed goal's ordinary fields while ignoring its additive metadata. The read does not mutate or delete the metadata. On reapply, the candidate repository reconstructs a typed `GoalTask` with the exact completed observation.

| Source phase | Loaded migration count | Actual DB migration count | Typed task attribute |
| --- | ---: | ---: | --- |
| Candidate before reversal | 14 | 14 | Present |
| Exact baseline source | 13 | 14 | Absent in old Goal; JSON remains stored |
| Reapplied candidate | 14 | 14 | Restored with exact metadata |

The original `apply_migrations` checks its loaded migrations and leaves the future applied version14 row intact. That narrow source compatibility is verified here; it does not establish permission to launch an old signed schema13 release against actual schema14.

All three complete SQL dumps are byte-identical: `schema14-before.sql`, `schema14-reversed.sql` and `schema14-reapplied.sql`. Each retains all14 migration rows, names, checksums and applied times; the `task_json` column, legacy fields/NULL metadata, completed task JSON, budgets, revisions, observation and planning history all remain unchanged. Each database integrity check returns `ok`.

SQL dump SHA256: `f95f39b56692897523e9b999304d818a2a7cc774a7a12c2e11268d3ca574a8c6`.

Stored task JSON SHA256: `04e0d6b506b4c65513d635585672a932637d97243872759b0f19d755fa37505b`.

No downmigration, DROP-column operation, database backup restoration, database replacement or old-data replay occurs. The SQL dumps are evidence snapshots and are never restored.

The distinct signed-release gate is already exercised by `test_schema13_upgrade_preserves_legacy_goal_and_refuses_old_release_approval` in the [final API evidence](../api/REPORT.md), bound to the same candidate source hashes. Its independently framed signed v2 receipt with max_schema13 resolves before migration and is refused against actual14 by both a13-support manager and a14-support manager; the post-migration SQL dump and active pointer remain unchanged. This rollback probe performs no signing, receipt rewriting, key handling or release selection and makes no additional release authorization claim.

## Raw execution, cleanup and harness correction

Final `rollback-probe.log` records seven subprocess steps, each EXIT0: database initialize, reverse check/apply, reversed database read, reapply check/apply and reapplied database read. All owned subprocesses are joined. The full temporary public source/database/workspace root `/tmp/g57r-vju6ziis` is removed after verification. No private runtime tree is scanned or read. No live8026, private database/configuration/chat/audio/key/model, GPU, provider or device is accessed.

The first run is retained verbatim under `first-harness-failure/` and is **FAIL**, not product PASS. Its source reverse and old-repository read succeeded, and its SQL dump equality assertion succeeded. The harness then compared SQLite migration-row tuples with JSON-decoded lists and failed its receipt comparison. Only the new evidence helper normalized those rows to lists; unused-import/lint corrections affected only the new evidence scripts. The failed run's owned children and temporary root were cleaned and protected workspace hashes matched. No production or old-test correction was needed.

Ruff lint and format checks pass for the two final evidence scripts. Complete regression, final product acceptance and remote exact-commit verification retain their own separate receipts.

## Operator boundary and reproduction

Before an operational change, withdraw the caller with `SIRO_GOAL_TASKS_ENABLED=0` and drain/join its owned work. Preserve schema14, additive task metadata/history and latest data. Never silently approve or widen an old schema13-only receipt. Reversing the Rust leaf restores its known unbounded read implementation; this rehearsal does not authorize exposing that path as an autonomous fallback. Existing read authorization and release handoff gates remain mandatory.

From the public repository, run `.venv/bin/python -B docs/evidence/T19-goal-loop-2026-10-14/rollback/rollback-probe.py`. The probe creates only its own temporary public-source/synthetic-data roots and writes its scoped evidence receipts/logs/patch here. Raw logs and the Git patch are preserved as generated, including whitespace; they are not reformatted into source-diff claims.
