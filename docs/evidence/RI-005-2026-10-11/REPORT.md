# RI-005 D48 / FIX-012 — Code-only rollback keeps latest data

Status: VERIFIED — code-only rollback component; scoped source/document/evidence audit completed. RI-005 overall PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION and new FIX-013 explicit-restore gate. No product deployment, launch or live8026 access.

## A. Current State

D47 fixed approved skill remains unchanged. D48 corrects local ReleaseManager rollback: select verified last-known-good code pointer while retaining latest conversation/memory/completed ledger, including real temporary WAL data. This does not change the actually running version. Existing launcher still starts the checkout and does not consume active.json; single stopped-owner/start/readiness acceptance remains outstanding.

## B. Codebase Memory Status

No callable Codebase Memory MCP exposed; graph query/reindex NOT_RUN. Direct public source/callers/contracts plus exact hashes/temporary actual probes used. All three requested independent subagent turns hit account usage limits; their initial source observation confirmed rollback→whole-DB restore but no final independent source/OS audit completed. Root performed direct final source/negative verification; do not claim independent final approval. No private DB/chat/WAV/key/model/GPU or lease bypass.

## C. Architecture Findings

Original T32 combined code rollback and old snapshot restore; old test explicitly required later writes to vanish. Classification REQUIRED_FIX/HIGH, ORIGINAL_DESIGN_ERROR/BAD_INTERFACE/TEST_GAP. Architecture correction is recorded in ../../runtime-evolution/ARCHITECTURE_CORRECTION.md, no whole-system redesign. Existing complete D39 signatures remain; reuse local ReleaseManager and standalone CLI, no update/restore framework, scheduler, schema engine, policy or runtime dependency.

A separate actual restore probe found SQLiteStore.restore_from validates migration/checksum only after backup.backup(live). Actual checksum mismatch raised MigrationError after old synthetic snapshot became live. Defined FIX-013 REQUIRED_FIX/HIGH/IMPLEMENTATION_BUG; SQLiteStore not edited here. This blocks explicit-restore/migration/full deployment acceptance, not D48 code-only metadata correction.

## D. Implemented Changes

Only one production file core/releases.py: rollback no longer reads an old backup path or invokes restore/migration/health/replay; obsolete private _restore_database removed. Newly staged immutable versions capture complete signed manifest sidecar outside bundle before active pointer; sequential reuse refuses before release effects. Actual staging bytes reverified after trusted healthcheck. Rollback validates strict version/path/record/source alias/full signature/digest, reads actual schema_migrations in mode=ro/query_only with bounded strict prefix and explicitly closes connection. Unknown/incompatible metadata fails closed without data/pointer change. No legacy sidecar re-sign/fallback.

One existing T32 fixture corrected to retain after-release data and include synthetic schema metadata; one new test file. Constructor/public methods/CLI args/result JSON/signing format unchanged. Intentional compatibility correction withdraws destructive rollback semantics; existing deliberate siro restore remains separate and unchanged.

## E. Tests and Verification

Contracts/decision D48 and FIX definition/architecture correction preceded production edits. First focused before-source result 41 FAIL/3 PASS2.05s; raw history retained. Two retention cases actually lost latest rows/ledger; stage mutation originally activated changed bytes. Final51 new cases plus revised original2 against exact captured production (before_probe.py) **51 FAIL/2 PASS2.70s**: 50 new failures/one positive control plus corrected old assertion failure/old interruption positive control. Not every negative was a distinct prior vulnerability; receipt absence is an expected new contract gap. Staging-identity single RED retained separately.

Final exact-freeze focused **94 PASS /3.75s** (`focused-final-freeze.log`): new51 + original signing/release36 + unchanged launcher3/operations4. Actual temporary SQLite/WAL/current writer/new writes, actual CLI with migrated synthetic DB/closed checkpointed writer, independent canonical signing bytes; alias/tamper/schema rejection. Controlled pointer-write and receipt-save failures explicitly injected. No mock process startup, real model, Live2D or human-voice claim. Known SQLite context manager does not close a connection; fixture helpers explicitly close, active WAL test keeps only its intended writer open. One test wrapper typing annotation corrected after first full pass; first full1,442 PASS154.95s is historical. Final identical-version full offline **1,442 PASS /5 real_provider deselected /3 existing warnings /157.59s** (`full-final.log`).

Final whole-repo Ruff304 formatted files/lint PASS; mypy238 PASS after local test annotation correction (initial one error retained), schema export/diff PASS. Exact3 source-only preservation/reverse/reapply PASS: baseline265/263 unchanged; only releases.py and old fixture changed, one new test, D47 eleven hashes unchanged. Final explicit3source and13updatedpublicdocument scans **0 findings**. D48 evidence **273 raw Hex records**, each exact-file/line detector fingerprint matched a known captured baseline/final source/patch SHA256 in a named recorded field; **273 false positives /0 unresolved**, no blanket exemption. Cutoff **2026-10-11 15:53:57 UTC** (`secrets-review-final.json`, `source-audit-report.md`); audit outputs and subsequent root status/count annotations excluded from snapshot, implementation frozen. No independent subagent final PASS claimed.

## F. Risk Assessment

Bounded component pointer only. Signed schema range and actual prefix do not establish target loader/checksum/startup behavior; read-only snapshot is not a stopped-writer/schema reservation. Same-UID hostile races, concurrent maintenance owners, power-loss fsync/durability, actual launcher/version/health/approval integration unverified. Operational release/DB/policy remain RED, release component YELLOW. Sequential version collision rejection is not a concurrent release lock.

Legacy targets missing captured complete sidecar refuse safely; no automatic trust migration. Interrupted new stage can leave an inactive version/receipt residue; do not silently overwrite or retry it. Pre-stage backup is retained as independent advisory evidence and has no automatic restore authority; retention cleanup TECH_DEBT, no new service. Existing explicit restore is unsafe on migration failure until FIX-013; never test it with private/live data. Five real_provider tests excluded; prior product search/voice/understanding gates unchanged.

## G. Recommended Next Tasks

FIX-013 local explicit-restore prevalidation; remaining RI-005 stopped-writer/actual launcher/version/readiness with latest-data checks; RI-006 readonly failure proposal. These identify dependencies, not rankings or new RT renumbering. RI-004 arbitrary generation/dependencies remains outside approved fixed skill; completed RT-011/013/015 not reopened. No automated deployment authorized.

## H. Deferred Work

General self-update, model self-approval, runtime deployment, arbitrary version mutation/repair, whole data migration/restore redesign, OS/multiprocess generalization are not added. Preserve latest data and existing architecture; restore invariants locally first. Independent final audit not completed because subagent limit; no claim it passed.

## Rollback

Final exact3 source-only disposable reverse/check/reapply PASS; patch SHA256 **c57347d559738a2cb69eb128f3099735112c0ef584746680b367a5da747ccac5**. Before snapshots preserve existing dirty releases.py and original fixture; exact final bytes reapply inside a disposable directory, live source unchanged, rehearsal directory removed. New test is removed only inside rehearsal; no live source apply/DB rollback. Keep latest actual DB. Restoring old source for development does not authorize calling its obsolete whole-DB rollback. Stop known operational owner/read back and retain latest data before any future runtime code switch.
