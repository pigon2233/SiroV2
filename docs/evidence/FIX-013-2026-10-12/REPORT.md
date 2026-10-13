# FIX-013 / D49 — Validate explicit restore before replacing data

Status: VERIFIED — bounded explicit-restore component; final full offline regression, independent scoped reviews, source-only rollback and explicit sensitive-audit snapshot completed. This is explicit data restore, not runtime deployment or code rollback.

## A. Current state

Original restore could overwrite latest conversation/memory/completed ledger and then report migration failure. D49 now snapshots into an owned candidate, validates known migration prefix/checksums, applies existing migrations there and checks integrity before opening the live target. Successful explicit restore still intentionally selects the backup data. D48 code-only rollback remains unchanged and preserves latest data.

RI-005 overall remains PARTIAL: actual launcher consuming approved release/version, stopped writer owner, startup/readiness/rollback acceptance and approval integration are separate gates. No live8026 restart or deployment performed.

## B. Codebase Memory and review

No callable Codebase Memory MCP exposed: graph query/reindex NOT_RUN. Direct source/callpaths/contracts, captured public hashes, synthetic actual SQLite and independent reviews used. Three agents reviewed contract, lifecycle tests and real SQLite backup boundaries; their saved findings distinguish historical source, intermediate implementation and final source. No private DB/chat/WAV/keys/model/GPU read or invoked.

## C. Architecture findings

REQUIRED_FIX/HIGH, IMPLEMENTATION_BUG/BAD_INTERFACE/TEST_GAP. Confirmed root causes: compatibility/migration checked after live copy; shared apply_migrations ignores unknown applied future versions; bare to_thread cancellation lets writer lock go while restore still runs. Repairs remain local to SQLiteStore, no new restore/schema engine, policy, dependency, Core/provider/UI coupling or global state. This is implementation repair, so no new ARCHITECTURE_CORRECTION is needed.

Independent review exposed one intermediate MINOR_FIX/LOW/TEST_GAP: Python3.14 shield plus late cancel plus MigrationError additionally logged a shielded-future error although caller observed it. Existing real lifecycle case gained exception-handler assertions: 1 FAIL/1 PASS before, 2 PASS after. Only the owned waiting primitive changed to asyncio.wait((job,)); error still propagates through job.result(). Intermediate source snapshot and actual probe retained.

## D. Implemented changes

Only production file src/siro/persistence/sqlite.py; two new focused test files. Source opened SQLite mode=ro/query_only (not immutable, so committed source WAL participates). Candidate in private temporary directory; bounded known exact integer migration prefix, existing name/checksum checks and existing apply_migrations, final integrity. Explicitly close restore-owned source/candidate/target connections. Promotion uses SQLite backup into target with its WAL semantics; no live file replacement, source migration or automatic replay/restore on error.

Original per-store writer lock covers thread completion and cleanup, including repeated cancellations. Thread-safe cancel flag checks preparation and promotion fences, and progress can abort an unfinished backup. At SQLITE_DONE SQLite has committed; late cancellation joins and reports cancellation, retaining committed data rather than claiming rollback. An existing primary migration/SQLite/IO error wins over later cancellation; cleanup denial adds only sanitized type note to primary, otherwise raises cleanup error. OS-denied cleanup is not described as removed.

## E. Tests and verification

D49 contract/decision and RED fixtures preceded main repair. Original validation screen: 20 FAIL/9 PASS. Initial independent lifecycle: 2 FAIL. All final41 new cases against exact captured original production: **30 FAIL/11 PASS /5.61s** (exact-before-final-freeze.log). Eleven positives are controls; failures include new ownership/cleanup contract gaps and are not thirty distinct vulnerabilities. Both source-to-candidate and candidate-to-live copy use real SQLite with controlled progress timing; DELETE/WAL partial-copy rollback and already-committed DONE distinction separately measured.

Final frozen adjacent matrix: **145 PASS /4.95s** (focused-final-freeze.log): new32 validation/new9 lifecycle plus existing SQLite, operations raw/ZIP CLI, release signing, latest-data code rollback and companion launcher tests. Actual temporary DB/WAL/old schema0,1,3,10,12,13/source readonly write denial/source preservation/explicit connection closes/current writer usability; negative checksum/name/future/gap/type metadata, committed-step migration SQL failure, target IO failure, corrupt/missing source, no target directory creation, completed ledger retained on rejection. Raw and ZIP CLI failure preserve existing target/config. Cleanup denial/thread timing/progress interruption are controlled injections around actual DB work, not claims of real disk hardware faults.

Final full offline regression: **1483 PASS/5 real_provider deselected/3 existing warnings/156.51s** (full-final.log). First pre-wait-fix full **1483 PASS/5 real_provider deselected/3 existing warnings/157.24s** is historical and cannot certify final source. Final whole Ruff **306 formatted files**, lint PASS, mypy **240 source files** PASS, schema export and diff check PASS. Initial local callback typing mismatch and wrong focused test filename were corrected; original error logs retained, neither counted as a passing gate.

Exact3 source-only disposable reverse/check/reapply PASS: baseline266,265 unchanged, only sqlite.py existing changed +2new tests. D47/D48 source preserved. Final patch SHA256 **cd58e3d2884b7e3fd5e338d2e298199b5efb4f6f8a78132addd86e296d77c60d**; rehearsal removed and live source/data untouched. Final sensitive scans: **3 scoped source/12 public documents:0 findings**. Evidence snapshot **55 input files/277 raw Hex findings**, each exact-file/line detector fingerprint matches a named known captured source/test/patch SHA256: **277 reviewed false positives/0 unresolved**, no blanket exemption or network verification. Cutoff **2026-10-11 17:58:09 UTC** (secrets-review-final.json/source-audit-report.md). Generated audit outputs/helper excluded; this final result/status annotation is after cutoff and not presented as part of that input snapshot. Initial scanner-review helper omitted explicit src/ labels from named-field recognition; initial-error log retained, actual exact captured digests verified before corrected audit PASS.

## F. Risks, debt and freeze zones

Architecture overall YELLOW. Restore component YELLOW (bounded trusted operator/per-store profile); focused tests/evidence GREEN after local gates. Running DB/schema migration, stopped-writer maintenance, permission/publishing remain RED. No lock/candidate result is an interprocess lease or a runtime version switch.

ZIP DB/config cross-file atomicity remains unverified: successful DB restore followed by config-write failure could produce mismatch; this card does not promise atomic multi-file transactions. External owners/active transactions, hostile backup schema/trigger attestation, same-UID filesystem races, blocked OS IO latency and power loss are unverified. Temporary candidate disk usage is bounded by operator's selected backup, with no new general capacity/quota manager: TECH_DEBT/DEFER, not an immediate redesign task. Backup retention debt unchanged. Other SQLiteStore methods' cancellation/connection lifetime not swept into this repair.

At completed commit, cancellation or cleanup failure may coexist with restored data; inspect state before retry, no implicit undo. Successful explicit data restore intentionally replaces recent data, independently of D48 code rollback. No hidden adapter or compatibility escape added; old successful callers and SQL/CLI shape remain.

## G. Roadmap and next three slices

KEEP RI-005, SPLIT stopped-owner and actual-launcher integration. Final verification removes only BLOCKED_BY_FIX: FIX-013 for this explicit-restore defect; keep BLOCKED_BY_RELEASE_INTEGRATION. Next three bounded slices: RI-005 stopped writer/maintenance ownership; RI-005 actual approved-release launcher/version/readiness/latest-data checks; RI-006 readonly failure proposals. This is dependency handling, not ranking or RT renumbering. RT-011/013/015 scopedDONE unchanged. FIX-002 useful search, FIX-005 first-audio/human voice, FIX-006 comprehension product gates remain.

Hermes concepts do not justify another restoration/evolution service; REJECT duplicate abstractions, DEFER arbitrary generation/general self-update until existing integration earns it. No new scoped blocker found by review; separate operational gates stay explicit.

## H. Excluded work and rollback

No new feature, unrestricted code execution, provider/model/voice/avatar/policy/grants/build/migrations/UI/launcher change or production restart. No formal or automatic deployment. Five opt-in real_provider tests NOT_RUN; no human/product acceptance claimed.

Reversible source-only patch is repair.patch, with before/after snapshots and preserve_and_rehearse.py. Rehearsal reverses the patch in a disposable directory, verifies original dirty sqlite.py/new tests absent, reapplies and verifies final three hashes, then removes workspace. Do not apply old unsafe restore to private/live data and do not roll back any actual DB. Next operational switch requires stopped owned writer and actual readback, not this source rehearsal.

## Primary API references

The live transfer uses the existing [SQLite backup API](https://www.sqlite.org/c3ref/backup_finish.html) and [Python3.14 sqlite3 backup](https://docs.python.org/3.14/library/sqlite3.html#sqlite3.Connection.backup). Local probes test partial interruption vs SQLITE_DONE; they do not extend those API semantics to arbitrary hardware failures. [Python asyncio.wait](https://docs.python.org/3.14/library/asyncio-task.html#asyncio.wait) provides owned completion waiting; caller cancellation is handled and joined explicitly, not treated as thread termination.
