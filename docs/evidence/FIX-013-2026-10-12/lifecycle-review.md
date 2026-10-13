# FIX-013 D49 independent lifecycle and source review

Scope: new `tests/integration/test_sqlite_restore_lifecycle.py` only for executable changes initially owned by this reviewer. Root subsequently added the narrow exception-handler assertion in the existing parametrized case, after the independent boundary review reproduced a Python 3.14 shield diagnostic. Production `src/siro/persistence/sqlite.py`, validation/CLI tests, contracts and public status were owned by root. This report and its final supplement were separately authorized after the test/source freeze; this reviewer made no further source/test edits. No live service, private database/chat/key/audio, model, GPU or deployment was accessed.

## Observed results

- Initial two cases ran RED before the production repair; the same two-case gate was saved against root's exact captured old module in `lifecycle-before.log`: **2 failed in 0.14s**. Caller cancellation completed before its real thread, and migration-stage cancellation left the old snapshot live.
- The initial complete nine-case lifecycle file was also exercised against the captured old module, without restoring old code into the working tree: `lifecycle-before-complete.log`, **8 failed, 1 passed in 4.41s**. The existing waiting-lock cancellation behavior passed. Missing owned-candidate cleanup stages produced bounded timing/negative failures; those cases do not claim historical OS cleanup refusal.
- The preliminary repaired source passed `lifecycle-final.log`, **9 passed in 0.44s**. Its source/test hashes were `9b4da8293008a2379b558b9e7331d223211d3edc3df633261854a6f172e5492d` / `37b7fcd4baad83248378726343dd746dbfed96d6af2d64e365cf6c419835a95f`. Scoped Ruff check, Ruff format diff and strict mypy passed at that stage. These are historical results, not final-freeze bindings.
- Final existing cleanup-error parametrization with the added loop exception handler: `wait-before.log`, **1 failed, 1 passed, 7 deselected in 0.28s**. Python 3.14 logged an additional `MigrationError exception in shielded future` after repeated cancellation, although the caller still received the primary error.
- After the local waiting-primitive repair: `wait-after.log`, **2 passed, 7 deselected in 0.32s**. The case count remains nine; the assertion observes the loop handler and restores its previous handler in fixture cleanup.
- Root's exact final two-file test projection against the original SQLite source: `exact-before-final-freeze.log`, **30 failed, 11 passed in 5.61s**. Root's final focused regression: `focused-final-freeze.log`, **145 passed in 4.95s**, including the nine lifecycle cases. These logs were inspected, not presented as a separate full-suite run by this reviewer.
- Frozen lifecycle test SHA256, matching `preservation.json` and current bytes: `515127d4c77b9e856bc1f27bf5f8958db928db17c36bcbf692d706d98ab31866`.
- Reviewed final production SQLite source SHA256, matching `preservation.json` and current bytes: `976595f41b6715a1818ec00d1130398ec3befbb793f8ed08562d96d25ddc33bc`.
- Captured pre-repair SQLite source SHA256: `714a396d4b6d3d1a1aee68bafa4de7184b46804ff399d2e10a49ebcedc2af8fe`.
- `full-before-wait-fix.log` records **1,483 passed, 5 deselected, 3 warnings in 157.24s** on the preliminary source. Final `full-final.log` was still running when this supplement was written; final full-suite completion is **not claimed here**.

## What the nine cases establish

All database work uses real disposable SQLite files. Threading events control timing around existing migration, connection, backup and owned-directory cleanup seams; each blocked thread has a bounded three-second release wait, and fixtures explicitly release/join workers and remove any fixture-owned denied workspace.

1. Repeated cancellation retains the per-store writer lock until the restore thread finishes; an already queued store write cannot overtake it, then executes exactly once after ownership is released.
2. Cancellation during candidate migration keeps latest live data and original backup bytes.
3. Cancellation while waiting for the writer lock never starts the restore thread.
4. Cancellation after a real live SQLite commit waits for controlled cleanup and raises cancellation; committed backup data remains live and is not silently rolled back.
5. Controlled candidate cleanup refusal after successful commit remains an observable OSError, and the refused workspace is not falsely reported as removed. The fixture removes it afterward.
6. A primary MigrationError survives controlled cleanup refusal and receives a sanitized cleanup-failure note.
7. The same primary MigrationError also survives repeated cancellation during cleanup, with latest live data preserved and no additional unobserved exception sent to the event-loop handler.
8. The source connection is genuinely read-only: disabling query_only still cannot write. Every captured source/candidate/target connection is explicitly closed, and backup bytes remain unchanged.
9. Repeated cancellation during a real multi-page source-to-candidate SQLite backup joins the copy and never opens the live target.

Cleanup refusal and timing are controlled injections, not claims of an actual OS deletion failure or performance measurement. Source-copy and live-commit behavior are actual SQLite operations. The root validation file separately covers actual candidate-to-live unfinished-copy cancellation and data/schema/CLI negatives; this reviewer read those cases without taking ownership of them.

## Independent source conclusions

The repair is local to explicit restore. Source read-only capture, migration metadata validation, existing migration application and final integrity validation complete in an owned candidate before the live connection is opened. Promotion retains SQLite backup/WAL semantics. The original `restore_from(source)->None` interface and intentional successful data replacement remain intact; code rollback remains separate.

Restore-local metadata validation requires exact integer versions forming a known contiguous prefix, bounded by the bundled migration count, and permits version zero. Existing apply_migrations still checks applied names/checksums and handles SQL migration failures; no global migration engine or SQL files were changed by this repair. Cancelled pre-promotion work cannot promote; completed SQLite commits are acknowledged as committed even when the caller subsequently receives cancellation. Cancellation-safe joining retains the writer lock through connection and workspace cleanup. A worker's primary typed failure is observed before late cancellation is propagated. Cleanup notes omit raw cleanup exception text.

The final same-scope MINOR_FIX replaces repeated `await asyncio.shield(job)` with `await asyncio.wait((job,))`. The separately held job remains owned, outer cancellation sets the thread's cancellation event and returns to the join loop, and only `job.result()` observes the final worker exception. This avoids the additional Python 3.14 shield-future diagnostic without changing restore API, candidate ordering, database semantics or primary-error precedence. The observed RED/GREEN handler assertion supports this narrow correction; it does not certify all shield uses elsewhere or authorize a wider asynchronous refactor.

No confirmed blocker was found in the reviewed source and these scoped cases. This is not a full-suite, deployment or universal SQLite safety certification. The per-store lock does not establish a cross-process lease or protect another independently constructed store. ZIP database/config cross-file atomicity, external active writers, concurrent source mutation, power-loss durability, launcher/version/readiness and formal deployment remain separate RI-005 gates. Existing source-only rollback evidence must never be interpreted as permission to roll back live data or reintroduce the defective restore path.
