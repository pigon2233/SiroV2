# D50 independent data-owner lifecycle review

Status supplement: **REOPENED / BLOCKED_BY_FIX: FIX-014**. Root's subsequent actual caller probe found that a backup destination can overwrite another live managed database while the earlier single-key owner protects only the source. The scoped repair will hold source and optional actual write-target keys with one shared owned-pool join. This report's cb5 production binding and five-file c7b patch below describe the preserved pre-FIX-014 phase, not approval of the newly identified path. `joint-owner-before.log` records three formal TypeError missing-keyword RED cases; those are API-gap evidence, separate from root's actual overwrite probe. The unchanged 31 default cases are retained, and three joint-resource cases have been added for partial acquisition cleanup, canonical alias deduplication and both descriptors retained on IO-join refusal. Their actual post-repair results and new source binding remain pending.

This reviewer owns only `tests/integration/test_data_owner_lifecycle.py` and these lifecycle evidence files. Root owns the adapter and CLI/Gateway integration. No production source, existing test, SQLiteStore, public status or earlier evidence was edited by this reviewer. All exercised databases, owner namespaces, processes and account data are synthetic fixtures; no private data, live8026, model, GPU, service deployment or automatic stop was used.

## Executed evidence

- `lifecycle-before.log`: initial **3 failed in 0.20s**, because the required adapter module did not exist. This was a formal missing-capability RED, not an actual OS isolation or mutual-exclusion result; no core test was skipped.
- `lifecycle-after.log`: initial implementation **1 failed, 26 passed in 0.79s**. A normal descriptor-close refusal escaped as raw OSError instead of the fixed safe DataOwnerUnavailableError. The primary-error variant already preserved its original failure.
- `close-after.log`: after root's local close-error mapping, **2 passed, 25 deselected in 0.04s**.
- `namespace-cleanup-before.log`: expanded negative gate **2 failed, 2 passed, 27 deselected in 0.13s**. Account lookup KeyError escaped directly; a busy contender's descriptor-cleanup error replaced the primary DataOwnerBusyError. The two owned-pool refusal controls passed.
- `lifecycle-before-fd-fixture.log`: repaired helper with the intermediate lifecycle fixture **31 passed in 0.95s**. The exact intermediate test SHA256 `8817bd716fb68ffbb0707f0bef59e194fa8aed46a7171ebbb65a6e64981aba67` is preserved under `before-fd-fixture/tests/integration/test_data_owner_lifecycle.py`.
- `callers-real-final.log`: root's **15 passed, 2 warnings in 4.13s**. This reviewer read the current caller file and log without rerunning it. Actual temporary Gateway HTTP/competing process/shutdown and backup/demo three-SIGINT cases are distinct from its controlled startup/server callbacks.
- `focused-final.log`: root's intermediate **199 passed, 2 warnings in 15.70s**. This result preceded the test-only polling repair below. Whole-repository format309, lint, mypy243, schema and diff logs also passed at that stage; they are not relabeled as a final full-suite run.
- `full-fd-fixture-failure.log`: **8 failed, 1,521 passed, 5 deselected, 3 warnings in 166.69s**. All eight failures came from this reviewer's subprocess-handshake fixture using select.select above its FD_SETSIZE limit. The raw-fork control pipe had the same limit. This is a confirmed test-harness defect, not a demonstrated production regression. The exact intermediate source and raw failure log remain preserved.
- Root authorized changing only the two fixture waits to select.poll with the original two-second timeouts. Test count, assertions and product source remain unchanged. No selector-specific unit test was added.
- Current `lifecycle-final.log`: **31 passed in 0.79s** with controlled dummy descriptors reaching fd1100, so the existing actual process/SQLite cases exercise the repaired waits above the old limit. Every dummy descriptor was closed in finally. Scoped Ruff check, Ruff format diff and strict mypy passed.

The root master source binding was regenerated after this fixture repair; it agrees with the current five scoped files. Final full-suite revalidation remains pending at this supplement's cutoff and is not claimed complete. The failed full-suite run is explicitly historical rather than hidden. Earlier caller fixture argument mistakes are not counted as implementation defects by this review.

## Actual OS and SQLite coverage

The tests exercise real Linux flock/fd behavior, stable files and explicitly joined processes:

- Fixed canonical key, created directory700/lock600, empty single-link artifact, unchanged inode after release, and same-process reentry rejection without creating the intended data directory.
- A real subprocess owns the lease and writes committed synthetic SQLite WAL data. Competition fails while it lives; normal exit and SIGKILL release ownership without replacing the stable lockfile or changing canonical rows.
- Two actual subprocesses start together and produce exactly one HELD winner and one immediate BUSY loser. Distinct databases can coexist.
- Directory and database symlink aliases share the canonical key. Actual lock symlink/hardlink/directory/FIFO/wide-mode fixtures, unsafe owner directories and nonregular/multiply linked existing databases fail closed.
- A thread-held context excludes another caller until the complete context exits.
- Actual exec with close_fds=False does not prolong ownership. Actual raw fork retains it after the parent context closes; normal child completion and SIGKILL release it, and its controlled parent reaps the child.
- The yielded loop_factory creates the tested owned default pool. A real SQLite transaction remains blocked after its event loop closes. A controller thread proves a competing subprocess is BUSY before releasing the real COMMIT. Normal exit and a primary KeyboardInterrupt both wait for completion before another owner can enter.

The account-home test controls pwd lookup and environment variables; it does not create or inspect the real account's state directory. The missing-account, open failure, descriptor-close failure and pool-shutdown refusal cases are controlled failure injections. They verify safe error types, sanitized notes, primary-error precedence and retained kernel ownership; they are not claims that the OS actually refused close or that a real thread-pool failure occurred. Pool-refusal fixtures submit no executor tasks, then explicitly close only their exact retained owner descriptor and clear their fixture-created closed event loop. This is distinct from the actual SQLite pool-work cases above.

All child processes are owned and waited/reaped. Blocked fixture threads have three-second release guards and are released/joined in finally; temporary owner namespaces remain inside each test directory. Stable lockfile retention is the intended contract, not leftover PID/TTL authority.

## Source conclusions and final scoped binding

The adapter has one local owner object, records only the yielded factory's default executors, and joins them in a dedicated thread before closing the descriptor. Repeated KeyboardInterrupt while waiting is remembered and cannot release ownership early. Unknown pool completion retains the descriptor. The final explicit acquisition cleanup preserves Busy and other primary errors; notes omit raw secondary exception content. Account lookup and normal close errors now map to the fixed unavailable error. Canonical metadata uses stat with only FileNotFoundError treated as absence, exact private modes, fstat identity and a stable inode check. The canonical key now hashes filesystem-encoded bytes, supporting valid Linux filenames with surrogate-escaped bytes.

CLI holds this owner around handler/asyncio.run and passes its loop_factory only to the three managed asynchronous data commands. Gateway's outer main acquires before provider/composition/SQLite initialization and passes its captured data directory/factory to the existing body. A direct diff against root's captured pre-D50 CLI/Gateway files confirms those bodies changed only for the owner wrappers and loop-factory/captured-directory plumbing. Direct library and injectable create_app callers remain outside this advisory entrypoint boundary.

The final 15-case caller file was read independently: six CLI busy paths retain complete DB/source/config/release snapshots and never call healthcheck; legacy/candidate Gateway busy callbacks remain controlled zero-effects tests; the actual HTTP subprocess starts on a temporary port, refuses a second Gateway and a restore, then shuts down before the key is free. Backup/demo fixtures use actual processes and actual SIGINT at three stages while a controlled old SQLite IO thread is blocked, then verify no success/backup result and a usable next writer after completion. They use synthetic pwd and database state; they do not start a model, prove a new signed executable version, or stop the existing live service.

Current bytes match regenerated `preservation.json` and its final scoped source-only rollback/reapply binding:

- Lifecycle test SHA256: `a746df4a62850f4a9483e9f11d8139be5d4f98d556d5e6d7d07952a0417e9957`.
- Root caller test SHA256: `41ad6041cb3ca240e242d173cd5f3a2d17c71df5537ec14dfc87d0f96dbfa0df`.
- Adapter SHA256: `cb5dfaa11a7b7dbcb274d36ba4ddba4648b16e08100797be10d4d1145f4925ec`.
- CLI SHA256: `727fecbcf1289294a7064f9eba498edd932a3c4c4494aaa316c8b732ff0e61ad`.
- Gateway SHA256: `8be67a5d3aeff067f00c49db1ac1b19ab3e6ba22c6c9c9911fa2b3adf2db3dd1`.
- Preserved D49 SQLite source SHA256: `976595f41b6715a1818ec00d1130398ec3befbb793f8ed08562d96d25ddc33bc`.
- Regenerated exact five-file patch SHA256: `c7b72231f97306504575db1163f47a4c62a1d74cb0d1c055c188a12c0eace0d5`. The master reports 268 baseline files with 266 unchanged and only the expected existing CLI/Gateway changes; disposable reverse/reapply passed, D47/D48/D49 remained preserved. This reviewer inspected that record and current hashes, without presenting root's rollback rehearsal as a separately rerun rehearsal.

No further confirmed helper or scoped caller blocker was found in these reviewed paths after the recorded repairs. Final full-suite completion remains unverified at this cutoff; no blanket product/deployment approval is given. The scope is Linux, the same effective UID, local filesystems and cooperating future entrypoints, not unsupported OS/UID cases unexercised here. An idle lease cannot prove that an old pre-D50 process or raw external SQLite writer stopped. Same-UID hostile filesystem replacement races, all SQLite connection single-writer semantics, network filesystems, ZIP DB/config atomicity, power loss, genuine signed-version launcher/readiness and deployment remain separate gates. No kernel lease result authorizes an update or replays a side effect.

## Root final supplement — 2026-10-12

This lifecycle reviewer's final follow-up hit the account usage limit. Its earlier source audits and3joint RED cases are retained as history, not falsely promoted to final independent approval. Root then extended the exact new fixture to36cases (two/three-key join refusal and last-key partial acquisition); current70new/215focused/1553full tests bind preservation.json. Independent contract reviewer separately reran16selected including actualthreeSIGINT, alltemporarycollisions andjointmechanics againstthe final5paths; that is their review, not this agent's run.

Historical focused-final.log references above identify an earlier199-result cutoff; root's current named focused-final.log is215PASS10.58s. Historical focused-final-freeze.log retains another199 scoped run. Final5source hashes/patch are preservation.json; all historicalcb5/727/a746/c7b conclusions remain limited to their phase. D50 three-key owner/FIX-014 scopedVERIFIED; independent backup-stage ZIP probe foundunchanged backup cancellation recreates staging (FIX-015 REQUIREDFIX/MEDIUM planned), so neither fullregression nor this lifecycle supplement claims completeZIPstaging cleanup.
