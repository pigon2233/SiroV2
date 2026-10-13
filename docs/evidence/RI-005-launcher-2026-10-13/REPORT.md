# RI-005 D52 — signed source launch and actual readiness

## A. Current State

D52 source selection/actual loaded identity/same-schema readiness slice VERIFIED. RI-005 remains PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION. The existing product launcher now has an explicit operator signed-source route; existing default launch remains. Two real versions and code rollback preserve latest data. First-adoption, immutable package verify/import gap and approved maintenance/runtime handoff are still unproven; no formal service update took place. RT-011/013/015 and FIX-012–015 scopedDONE histories remain. FIX-002/005/006 search/voice/comprehension product gates remain.

## B. Codebase Memory Status

No callable Codebase Memory MCP tool is exposed in this session; connection/query/reindex verification NOT_RUN. Repo integration is not a verified MCP index or SIRO personality memory. Source, actual tests and captured hashes supplied evidence.

## C. Architecture Findings

Before D52, scripts/launch_companion.py execv imported the installed working package; releases/active.json had no launcher consumer, and /health/ready only reported Core health. That was MISSING_INTEGRATION / INCOMPLETE_TASK / TEST_GAP, not a new original design error. Added one public read-only target selector to existing ReleaseManager; Core has no Gateway/provider/OSdriver dependency. Explicit immutable identity enters the existing Gateway composition/ready projection. D48 schema SQL fact was locally extracted and independent AST parameter-bound equivalence confirmed, not replaced by a new schema service.

New actual first-adoption counterexample shows new D50 flock and successful SQLite BEGIN IMMEDIATE can coexist with a living old WAL writer that later commits. PID file, TERM delivery and readiness cannot establish old-writer absence. This keeps the known gate; no automatic kill/scan, PIDTTL authority or new owner registry was introduced.

## D. Implemented Changes

- src/siro/core/releases.py: resolve_launch_target validates bounded exact active record, complete signed receipt/version, actual regular source tree/digest, required package/Core/Gateway files and actual readonly known-prefix schema. Immutable VerifiedRelease captures identity and checks runtime origins/current schema. Existing rollback schema fact is reused without changing its SQL/behavior.
- scripts/launch_companion.py: explicit SIRO_RELEASE_ROOT plus existing SIRO_RELEASE_SIGNING_KEY selects this route. Fresh -I/-B interpreter loads selectedsrc; existing cwd/data/assets remain, data path captured absolute. Prepared assets only, no cargo/renderer/tokenizer provisioning. Exec environment copy removes signing key; no failure fallback to installed source.
- src/siro/services/presentation/gateway.py: optional trusted VerifiedRelease composition argument; under existing D50 owner checks actual SIRO/Core/Gateway __file__ and actual DB schema before model/DB startup. Candidate migration count different or intervening schema change refuses. Ready version/digest appears only after all startup callbacks; absent before startup/failure/drain. Default main call and ready shape remain.
- Four new test files: selector70, launcher7, ready/DTO/owner15, actualsourceprocess3 =95 cases.

The same-schema route refuses required migration; signed schema bounds alone do not authorize data migration. Manifest/signature format and release stage/rollback CLI are unchanged. DTO/API is only for D52-compatible selected source; old ABI fails closed. Actual import origin is not live-byte cryptographic attestation or protection from hostile sameUID mutation.

## E. Tests and Verification

| Evidence | Actual result | Limits |
|---|---|---|
| selection-before.log |70FAIL/1.09s | Missing new API, not70old security defects |
| caller-before.log |10FAIL/2PASS/0.98s | Original12 caller cases; already-working behavior preserved |
| selection-after-first.log |70PASS/0.51s | Actual temporary SQLite/WAL/source/signature/strict records/schema/aliases/zero-effects |
| process-final.log/.json |3PASS/6.40s;5actualchildren | True1→2→rollback1 HTTP; two negative ABI/tamper child cases |
| adoption-result.json |9checks PASS;3controlledchildren exit0/joined | True oldWAL writer remains after newlock; does not prove private oldwriter stopped |
| boundary-runtime-result.json |9direct controls PASS | Actual synthetic SQLite, origins as controlled inputs; not real child imports |
| focused-final.log |335PASS/3existingwarnings/25.63s |95new plus240 original restore/backup/release/owner/launcher |
| full-final.log |1673PASS/5real_provider unselected/3existingwarnings/199.58s | Final offline source-bound suite |
| format/lint/types/schema/diff-source-docs-final.log |PASS/Ruff315/mypy250 | Includes launcher types; whitespace scope is source/tests/docs, not verbatim raw evidence |
| rollback-final.json |exact7 PASS/270-of-273unchanged | Disposable reverse/reapply, no live data/index rollback |

Three normal actual children have SIGTERM exit-15 and real Uvicorn Application shutdown complete/readback/joined; do not call these exit0. Each ready version/digest, actual three loaded __file__ origins, selected package before/after digest, no pycache, signing-key-absent boolean and frozen root source/test hashes verified. Three batches actual conversation/memory/completed actions/custom markers survive code rollback. Two negative children exit1, preserve DB bytes/rows and never load host Gateway fallback. All5joined and temporary roots removed; provider/TTS requests/actions were not invoked. Clone-only account namespace and loaded-origin telemetry are explicit controlled interposition in the signed fixture, with actual source import/HTTP/SQLite/IO retained.

Initial process fixture missing json/hashlib imports and rollback evidence field-name mismatch were fixture errors; failure logs retained, only fixtures fixed, final tests/rehearsal rerun. They are not production fixes or substitutes for actual integration. Initial controlled checks do not authorize deployment.

Three warnings are existing pypinyin codecs.open and Starlette httpx TestClient deprecations. Whole scripts/check, Rust rebuild/dependency sync, real providers, human voice/comprehension/renderer, private/current8026 and formal deployment NOT_RUN. Scoped checks do not imply aggregate CI or whole-evidence whitespace PASS. Verbatim old pytest diagnostic logs/patches intentionally retain their raw whitespace.

Independent boundary-final-review.md, process-review.md and rollback-final-report.md bind final sources. selection-doc-review.md rebinds final selector source; adoption-review.md/adoption-result.json measure the earlier baseline owner, which remains unchanged, and do not claim all modified D52 sources were tested by that probe. Exact seven SHA values in source-freeze.json; 273baseline snapshot and exact before3 captured. Root full/focused logs bind the frozen source, not a previous prototype.

## F. Risk Assessment

Architecture YELLOW. Selector/launcher/Gateway YELLOW; synthetic tests/evidence GREEN; running DB/migration/permissions/publication RED. Remaining gates: sameUID mutation after parent verification, CLOEXEC maintenance→exec lease gap, unknown/old/unmanaged writer absence, immutable approved package/runtime handoff. Source origin/readiness or newlock does not clear them. No new permission or model approval path.

Same-schema source only; shared pinned interpreter/dependencies do not certify arbitrary release/deps/ABI/OS. Required migration fails before composition. No data restore/replay/retry fallback. 270existingfiles unchanged; exact7 disposable reverse/reapply restores captured3sources/removes4newtests/reapplies allbytes, retains latest real data. Source rollback does not authorize unsafe previous operational rollback/cancellation paths. D48 AST SQL semantics and D49/D50/D51 fences preserved.

No live8026/private DB/chat/WAV/key/config/models/GPU or formal deployment.

## G. Recommended Next Tasks

Three existing scopes, no ranking/renumbering: RI-005 knownoldwriter gracefuljoin/firstadoption evidence; RI-005 immutable exactapprovedpackage plus maintenance/runtimehandoff; RI-006 sourcedfailure→read-only proposal. KEEP RI-005/SPLIT remaining gates; KEEP RI-006. D52 already solves selected-source/readiness slice; do not refactor it again. No evidence demands cancelling numbered tasks or a new updater.

## H. Deferred Work

REJECT duplicate updater/owner/registry/schema engine/globalstate abstractions. DEFER arbitrary self-modification/autopublication, broader deps/ABI/migration/OS certification to concrete caller/value and independent approval/verification. Product search, voice speed/human perception and comprehension require their own evidence. Git publication is not a service update.

Public-input audit cutoff 2026-10-13T06:16:09.886529+00:00: source7/docs13 findings0; 352 evidence entropy findings individually bound to verified public/actual synthetic digests, unresolved0. Raw scanner/individual audit outputs remain local. This count-only footer and summary are outside the cutoff and separately scanned. No private data/model/audio/local Git helper input was scanned.
