# D51 / FIX-015 — backup cancellation and Git integration

## A. Current State

FIX-015 DONE / VERIFIED for backup cancellation/staging cleanup. D50/FIX-014 remain scopedVERIFIED. RI-005 is PARTIAL: actual approved signed-version launcher/readiness/handoff and old/nonmanaged writer adoption are not proven. RT-011/013/015 scopedDONE histories are preserved; FIX-002/005/006 retain product-quality gates. This is a source repair, not deployment or final product acceptance.

GitHub Desktop authentication now works for local Git through its existing OS credential store and a repository-local helper. No token was logged, copied into tracked files or stored as plaintext. Existing Desktop LFS binary is used; pre-push hook retained. Public checkpoint7892ecc was actually pushed and remote verified. Local unpublished history remains on local-backup/pre-public-push-2026-10-13; private audio/models/cache and uncertain historical artifacts stay local. The public checkpoint parent is the previously public remote, with no private ancestors transferred. D51 source publication is recorded separately if pushed;7892 does not contain D51.

## B. Codebase Memory Status

No callable Codebase Memory MCP tool is exposed in this session; graph connection/query/reindex/validation NOT_RUN. Existing repo integration is not equated with a successfully connected MCP or SIRO personality memory. Raw source, actual tests and exact hashes supplied the evidence.

## C. Architecture Findings

Confirmed root path: operations TemporaryDirectory→await SQLiteStore.backup_to→unowned to_thread→late _backup_sync mkdir/copy. Cancellation unwound writer/context before real IO; sqlite3 connection transaction context also did not close actual connections. The lower backup responsibility leaked into the enclosing ZIP lifetime.

SQL-only repair protected data/staging but repeated default Runner SIGINT abandoned coroutine teardown. Backup-only temporary handler initially cancelled its task without waking the blocked selector; true8 timing failures plus two original D50 init-stage test failures exposed this. Installed Python3.14 Runner._on_sigint explicitly performs cancel plus call_soon_threadsafe wakeup. The local handler now follows that same behavior. No original architecture error or need for new ARCHITECTURE_CORRECTION was found; existing single owner remains valid.

## D. Implemented Changes

- src/siro/persistence/sqlite.py: only backup methods plus copy_context import; retained default-executor Future/captured context, local cancel Event, actual copy/publication fences, writer lock retained until IO/explicit connection close/cleanup, typed primary errors preserved with type-only secondary notes.
- src/siro/cli.py: only _backup wrapper plus threading imports; one backup main-thread temporary SIGINT→ownedtask.cancel＋loop wakeup, repeated cancellation waits cleanup, finally restores exact previous handler. Signal cancellation/late successful body flag become original KeyboardInterrupt; plain CancelledError/primary typed errors remain.
- two new focused test files (19 SQLite +6 CLI); contracts/decisions updated before each production correction.

D49 restore and all other SQLite body; D50 owner/Gateway/main/original tests; operations, Core/policy/providers/voice/UI/launcher/dependencies remain unchanged. Private _backup_sync(destination,cancelled=None) preserves direct one-argument callers. Public API and raw/ZIP formats unchanged.

## E. Tests and Verification

| Evidence | Actual result | Scope |
|---|---|---|
| cli-before.log |4FAIL/1PASS | Original CLI, first5 controlled tests before implementation |
| lifecycle-before.log |14FAIL/2PASS | Original SQLite, initial16-case RED snapshot |
| lifecycle-cancellation-fences-before.log |16FAIL/2PASS | Original SQLite, expanded18-case RED snapshot |
| signal-after-progress.json |8data/staging PASS;4tripleSIGINT pending-task stderr | Intermediate SQL-only repair, not final teardown PASS |
| signal-cli-wakeup-before.json |8 timing failures | First CLI handler without selector wakeup |
| focused-before-wakeup.log |2FAIL/237PASS | Original D50 backup/ZIP init-stage callers exposed real integration bug |
| full-before-wakeup.log |2FAIL/1575PASS/5unselected/3warnings | Historical incomplete source; not final baseline |
| cli-lifecycle-final.log |25PASS | Final19SQLite+6CLI cases |
| focused-final.log |240PASS/2existingwarnings/17.60s | Final new+original restore/operations/release/signing/owner/launcher tests |
| full-final.log |1578PASS/5real_provider unselected/3existingwarnings/198.40s | Complete final offline suite |
| signal-final.json/.log |8PASS/130/zero stderr | TrueOS single/three SIGINT: raw/ZIP beforecopy, raw afteractualpublication, actualSQLite in-flight64/124pages |
| format/lint/types/schema/diff-final.log |PASS (Ruff311/mypy245) | Actual final code/style/type/wire-schema/diff checks |
| rollback-final.json |PASS/269 of271baselineunchanged/exact4sourceonly | Disposable reverse/reapply, no live data modification |

All8 truechild probes verify exacthandler restoration, no Runner.close while backupIOpending, every repeat consumed by owned coroutine, IO/children joined, source/config/priorarchive/fixedtemp retention as applicable, staging absence after join,3data keys held to join and next-owner write retained. Raw publication after cancellation remains committed honestly. Every controlled child joined and synthetic root removed; no forced kill in final probes. Timing pauses and cleanup/copy error injections are controlled; actualSQLite, filesystem, kernellocks and processsignals are real.

Full warnings are the existing pypinyin codecs.open deprecations plus preexisting Starlette httpx TestClient deprecation, not pending backup warnings. real_provider and actual human voice/comprehension/product/runtime8026/private-data/deployment/powerloss are NOT_RUN. scripts/check as a single aggregate command is NOT_RUN: final offline/format/lint/mypy/schema and scoped secret gates are separately executed; Rust/dependency sync/native model setup are unchanged and not rerun by this card. Do not claim aggregate CI success from scoped checks.

Independent reviews: lifecycle-review.md/lifecycle-cli-review.md/lifecycle-doc-review.md, signal-review.md, rollback-final-report.md. First controlled review missed selector wakeup; that limitation and new trueRED/final source bindings are retained. Exact four SHA values are in source-freeze.json; actual5production probe hashes match start/finish.

## F. Risk Assessment

Backup/module owner/Gateway remain YELLOW; synthetic tests/evidence GREEN; running DB/migration/permissions/release RED. Blocking OSIO can remain pending; no new bounded cancellation SLO is invented. Connection/unlink refusal remains visible and does not claim cleanup succeeded. A final published raw snapshot can exist with130; read back before retry, no automatic retry/rollback. ZIP multfile atomicity, powerloss, hostile sameUID races and old/nonmanaged writers are not proven. Backup retention/capacity remain TECH_DEBT/DEFER, not immediate abstraction expansion.

Exact4 source-only rollback restores captured prior SQL/CLI bytes and removes then reapplies two newtests in a disposable tree, retaining all user data. Source rollback does not authorize use of unsafe previous cancellation behavior.271 baseline paths have only the two intended existing modifications;269 remain byte-identical. Git-hygiene publication of previously omitted synthetic tests is separate from this repair scope: test_model_adapters.py, test_provider_completion.py and test_companion_launcher.py were conservatively omitted from7892. The unchanged local public fixtures have zero scoped secret findings and are included in the next repair checkpoint; this does not enlarge the exact4 repair rollback.

No live8026/privateDB/chat/WAV/key/config/models/GPU or formal deploy actions occurred.

## G. Recommended Next Tasks

Three existing scopes, not a ranking or renumbering: RI-005 first-adoption stopped-old/nonmanaged writer evidence; RI-005 approved exact signed launcher/version/readiness/handoff; RI-006 source-backed failure→read-only proposal. KEEP RI-005/SPLIT remaining gates; KEEP RI-006; RT-011/013/015 DONE unchanged. No evidence demands cancelling a numbered task, redesign or new owner/backup manager.

## H. Deferred Work

REJECT duplicate backup/owner/executor/global-state abstractions. DEFER arbitrary self-modification/automatic publication and dependency/multiprocess/cross-platform certification until concrete caller/value and separate safety evidence exist. Keep real voice-speed/human perception/useful-search/comprehension gates open. Neither a public Git push nor offline PASS substitutes for those product results.

Sensitive-input audit cutoff: 2026-10-13T05:26:58.849676+00:00; source4/docs13/Git-hygiene3 findings0; 899 evidence entropy findings individually tied to exact captured/reconstructed public digests, unresolved0. See secrets-summary.json and locally retained individual scanner review. Scanner outputs and this count-only annotation are outside the input cutoff. No private inputs were scanned.
