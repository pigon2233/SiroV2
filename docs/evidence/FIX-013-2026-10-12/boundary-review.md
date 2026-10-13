# FIX-013 independent SQLite boundary research

This work unit initially changed only `boundary-probe.py`, `boundary-probe.json` and this review. The final source audit additionally archived its own actual current-source reproducer/RED result as `current-probe.py` and `current-probe.json`, and repaired-source result as `current-probe-final.json`, with explicit parent authorization. No production/test file, private database, service, model or GPU was modified or launched. The saved results contain this work unit's actual synthetic runs, not another agent's results.

The production implementation was changing concurrently. The final reproducible run therefore explicitly loads the card's **original source snapshot**, SHA256 `714a396d4b6d3d1a1aee68bafa4de7184b46804ff399d2e10a49ebcedc2af8fe`. Its defects are historical before-repair evidence, **not claims about the repaired current implementation**.

Reproduce from the repository root:

```bash
./.venv/bin/python docs/evidence/FIX-013-2026-10-12/boundary-probe.py \
  --store-source docs/evidence/FIX-013-2026-10-12/before/src/siro/persistence/sqlite.py \
  --output /tmp/siro-fix013-boundary-result.json
```

The recorded run exited 0 on Python **3.14.4**, SQLite **3.46.1**. It records **11 probe outcomes**, not eleven passing production tests. All database fixture directories were removed; the script retains only its explicitly requested result file. Temporary paths and markers are synthetic.

## Confirmed original defects

1. Original `restore_from`/`_restore_sync` copied the source over live before validating applied migration checksums. A valid SQLite snapshot with a synthetic bad checksum raised `MigrationError`, while the latest marker was already replaced by `old-snapshot`.
2. Cancelling the original `await asyncio.to_thread(...)` released the store's `_writer_lock` while its restore thread continued. A queued transaction completed before that thread joined, then the late restore overwrote its `after-cancel-write`. The second cancellation was already ineffective because the parent task had returned.

These are measured order/ownership failures. This review does not revive the previously corrected release rollback semantics.

## SQLite backup interruption boundary

With an actual 1,091-page source and `pages=16`, the first callback observed status 0, remaining 1,075. Raising there retained the original latest marker **and identical main/WAL bytes**, both with DELETE and WAL destinations. Raising at status **101 (`SQLITE_DONE`), remaining 0**, still raised the callback exception but the old snapshot was already committed to live. All four outcomes are recorded in `boundary-probe.json`.

This follows SQLite's documented transaction boundary: an unfinished backup is rolled back by `backup_finish`; `SQLITE_DONE` has already completed the destination operation. CPython invokes the progress callback after `backup_step`, including DONE, and calls `backup_finish` when that callback raises. [SQLite backup API](https://www.sqlite.org/c3ref/backup_finish.html), [CPython 3.14 implementation](https://github.com/python/cpython/blob/3.14/Modules/_sqlite/connection.c#L2059-L2094).

**Contract consequence:** a cancellation callback must not throw on DONE and then imply the live database was preserved. Pre-copy or incomplete-copy cancellation can retain live data; cancellation that crosses the commit boundary can have a completed effect. There is no post-DONE rollback guarantee. Do not add `os.replace` of live/WAL or restore an old backup to manufacture that guarantee.

The Python API provides fixed-size backup steps and a callback for each iteration, including busy/locked retries. Its sleep parameter applies between attempts; it does not itself impose a total deadline. [Python 3.14 backup documentation](https://docs.python.org/3.14/library/sqlite3.html#sqlite3.Connection.backup). Neither these probes nor those API guarantees establish power-loss behavior, arbitrary disk failure behavior, or a cross-process stopped-writer lease.

## Smallest measured repair shape

- Open source with SQLite read-only URI and copy it through the backup API to one owned private temporary candidate. Do not migrate the supplied source or trust only `integrity_check`.
- Validate the candidate's migration ledger as an exact known contiguous prefix, rejecting future/modified entries. Apply all bundled migrations off-live; then validate the full resulting ledger and database integrity. Explicitly close preparation connections before opening the candidate read-only for the final SQLite API copy into live.
- Keep the existing store writer lock until the owned thread and temporary cleanup finish, including repeated parent cancellation. A local cancellation event can stop preparation or incomplete backup; preserve actual migration/IO failures rather than replacing them with a success or a generic cancellation.
- The probe's `asyncio.wait((job,))` join loop retains the worker task without cancelling it when the caller is cancelled. The guarded prototype held the writer lock after both cancellations, blocked the queued transaction until join and then retained `after-cancel-write`. This is a narrow ownership prototype, not a new restore service.

The off-live prototype restored a valid one-migration snapshot after migrating it to all **13** bundled migrations. Its bad-checksum, future-version and actual migration-SQL conflict cases retained live bytes and the latest marker, while preserving supplied source bytes. Errors remained `MigrationError`, `MigrationError` and `OperationalError`, respectively. No prototype uses live-path replacement.

Remaining acceptance belongs to the production repair: real old/current/future schema cases, source/WAL preservation, in-copy cancellation, busy/locked cancellation, repeated parent cancellation with a queued writer, DONE commit-race semantics, candidate cleanup and original SQLite/memory/explicit-restore caller regressions. The store-local lock does not authorize multiple independent stores or processes to write concurrently. Launcher/release/ZIP DB-config atomicity are outside this source review.

## Narrow review of D49 repair before duplicate-log correction

Date: 2026-10-12. The source actually reviewed was `src/siro/persistence/sqlite.py`, SHA256 **`9b4da8293008a2379b558b9e7331d223211d3edc3df633261854a6f172e5492d`**. This section is separate from the historical snapshot/prototype outcomes above. Its data/ownership checks passed, but its duplicate-log observation led to an added acceptance requirement and a minimal owner-wait repair. Its finding is historical; the completed repaired-source re-audit follows below. Production and test files were not edited by this reviewer.

The production diff stays within the existing restore methods and two standard-library imports. Source capture uses mode=ro/query_only and an owned candidate; version-prefix validation, the existing names/checksums/migrations and final integrity check complete before opening the live target. Promotion uses SQLite backup, without replacing the live file or WAL. The existing store lock encloses the off-loop task, its repeated-cancellation join, connection closure and candidate cleanup. Primary migration/SQLite/IO errors remain typed; a cleanup refusal is observable without replacing the primary error. The progress callback skips cancellation at `SQLITE_DONE`, matching the measured commit boundary rather than promising an undo.

The earlier prototype's additional final read-only candidate reopen and full-ledger check were research options, not new D49 requirements. The current implementation keeps the already validated candidate connection for final backup and reuses the existing migration helper. It closes all owned connections before cleanup. No extra service, migration abstraction, dependency or architectural change is justified by this review.

This reviewer's actual focused command was:

```bash
./.venv/bin/pytest -q tests/integration/test_sqlite_restore_validation.py tests/integration/test_sqlite_restore_lifecycle.py
```

Result: **41 passed / 1.42 s**, comprising the 32 validation and nine lifecycle cases present at execution. The new source-copy case pauses an actual incomplete SQLite backup, then cancels and joins without opening live. Other cases cover real WAL/candidate upgrades, invalid metadata, incomplete promotion, commit/cleanup cancellation, cleanup refusal, repeated cancellation, the queued writer and read-only source/connection closure. Controlled fault/timing seams are not evidence of arbitrary OS failure or power-loss safety. This is an actual scoped run, not a full-suite or deployment claim.

### Actual current-source shield observation

A separate synthetic probe called the **actual 9b4da source** `SQLiteStore.restore_from`, with a controlled pause/failure inside its real candidate `apply_migrations` phase. It cancelled the caller twice while a transaction waited on the same store lock, then released the phase to raise `MigrationError`. This was not the earlier guarded prototype. The actual run exited 0 on Python **3.14.4** / SQLite **3.46.1**; its fixture root `/tmp/siro-fix013-current-audit-fnk8vrxj` was removed. Its actual script/result are archived as [`current-probe.py`](current-probe.py) and [`current-probe.json`](current-probe.json). The original eleven before/prototype outcomes remain untouched. Re-run from the repository root with `./.venv/bin/python docs/evidence/FIX-013-2026-10-12/current-probe.py`; this reads the then-current source and writes only `/tmp/siro-fix013-current-boundary-audit.json`, preserving the archived RED result.

The actual captured facts were:

```json
{
  "first_cancel_task_done": false,
  "first_cancel_writer_lock_held": true,
  "first_cancel_queued_writer_done": false,
  "second_cancel_task_done": false,
  "second_cancel_writer_lock_held": true,
  "second_cancel_queued_writer_done": false,
  "caller_error_type": "MigrationError",
  "thread_finished_when_caller_returned": true,
  "live_before_queued_join": "latest",
  "live_after_queued_join": "queued-after-join",
  "source_main_bytes_unchanged": true,
  "loop_exception_contexts": [
    {
      "message": "MigrationError exception in shielded future",
      "exception_type": "MigrationError"
    }
  ],
  "writer_lock_after_join": false
}
```

The one loop exception-handler notification is reproducible: Python 3.14's cancelled shield wrapper installs an exception logger, even though the owner later observes the worker's primary error. It does not demonstrate an unjoined task, lost error, released writer lock or modified live data. The parent added a no-duplicate-error-notification acceptance requirement and classified it **MINOR_FIX / LOW / TEST_GAP**, within FIX-013's existing owner wait loop. The proposed local correction is to wait on the retained task without a cancelled shield exception logger; the same writer lock, cancellation event, join and primary-error behavior must remain. No new abstraction or production/test change was made by this reviewer. The cancellation-with-primary-failure case must continue preserving the primary `MigrationError` instead of replacing it with `CancelledError`.

**Finding at this cutoff:** no reproducible data-retention or cancellation-ownership blocker was found in 9b4da, but the new duplicate-log acceptance is RED and final source audit is pending the parent's smallest wait-loop repair and refreeze. Master preservation and whole-card acceptance remain the parent's responsibility. Cross-process/external writers, arbitrary hostile physical schemas/resources, cancellation latency, power loss, ZIP DB/config consistency, actual launcher/version/readiness and formal deployment remain separate gates; this review does not remove them or revive obsolete release rollback findings.

## Final re-audit after minimal wait correction

**Status: SOURCE_REVIEW_COMPLETED / PENDING_FINAL_MASTER_VERIFICATION.** The final frozen production source read and executed by this reviewer has SHA256 **`976595f41b6715a1818ec00d1130398ec3befbb793f8ed08562d96d25ddc33bc`**. The correction replaces only the shield wait with `asyncio.wait((job,))` and removes the now-unused wait exception branch. The retained task, existing lock, cancellation event, primary `job.result()` and complete thread/connection/cleanup join remain intact. It introduces no service or architectural change.

This reviewer re-ran the archived `current-probe.py` against that final source, preserving the actual pre-correction `current-probe.json`. The actual final result is [`current-probe-final.json`](current-probe-final.json): Python 3.14.4 / SQLite 3.46.1, fixture root `/tmp/siro-fix013-current-audit-jv012qrd` removed, loop exception contexts **empty**. Both caller cancellations still leave the task pending and writer lock held; the queued writer cannot run early. The caller receives the original `MigrationError` after the real thread finishes; live remains `latest` before the queued transaction, source main bytes remain unchanged, and the queued transaction then produces `queued-after-join`. Thus the added duplicate-log acceptance is now GREEN without losing the originally repaired data/ownership invariants.

The same scoped validation+lifecycle command was actually re-run after the correction: **41 passed / 1.62 s**. These final current-source observations supersede neither the saved historical failures nor the separate whole-suite evidence. No remaining reproducible blocker was found in this narrow final source review; the scope limitations and RI-005 release/launcher gates stated above remain in force.
