# RI-004 D47 — fixed checklist product activation

Status: VERIFIED — fixed-template product activation only. Final tests, actual UI, exact source rollback and scoped source/evidence/document audits completed after the history-label correction. RI-004 overall remains PARTIAL. No formal deployment or live8026 restart.

## A. Current State

D44 preparation/review and D46 strict worker are preserved. D47 joins them into one explicit owner flow: prepare → inspect exact four files and actual verification → approve/install disabled → separate enable → existing catalog/tool proposal/approval/context/dispatcher → revoke. The UI adds controls under 電腦協助; sample fill does not send a chat. Only markdown-checklist-v1 is supported, with empty permissions, pasted text only and no files/network.

Temporary actual Gateway/SQLite/strict worker and CUA browser completed prepare/install-disabled/enable/fill-without-send/revoke/readback. Product controls are locally ready for the next authorized runtime start; the currently running user's service has not been restarted. Placeholder renderer in this fixture is not a Live2D acceptance claim.

## B. Codebase Memory Status

No Codebase Memory MCP exposed in this turn; graph queries/reindex NOT_RUN. Direct public source, caller/contract, captured hashes and actual synthetic probes used instead. No private DB/chat/WAV/key/model/GPU inspection, no owner lease bypass or new runtime dependency.

## C. Architecture Findings

Reuse existing skills table, registry, catalog, orchestrator, dispatcher and strict worker; no new scheduler/registry/schema engine. Existing install UPSERT/default APIs remain compatible. Additive catalog entries appear only after exact approved disabled install, preserving capture/deepcopy/name guards; availability stays pure cached metadata, with actual registry/frozen package revalidation at dispatch. No model can install/enable itself or provide raw code/schema/path/PASS.

New-card counterexamples were reproduced before local correction: revoke cleanup failure skipped durable disable; cancelled startup restored late availability; delayed/queued review adopted a newer owner epoch; successful execution returned late despite cancellation/deadline/revoke during cleanup; unsupported strict runtime leaked the wrong error contract; tools-off waited for candidate cancellation before stopping skills; live tools-off UI did not fence new controls. Final actual screenshot also exposed a stale preparation label saying not-installed next to installed/enabled state; two RED UI cases require labeling the upper review as historical without rewriting its original exported facts. Source repair stays in the contracted owner/Gateway/UI files, with no D46/Core/policy change or original design correction required.

## D. Implemented Changes

- Registry insert-if-absent preserves all existing same-version identity/state. Optional expected identity fences enable AND disable; row-only is_installed facade permits safe disabled startup without persistence internals leaking into service. Legacy API behavior preserved.
- One server-held immutable review, monotonic900s TTL and owner epoch; full template package/source/tests/proposal/verification binding. Browser passes only strict review UUID/hash. No dormant descriptor before preparation.
- Managed readonly exact four-file package plus outside-package approval receipt, disabled install and actual strict-runtime validation before explicit enable. Startup restores only exact fixed template/receipt/registry identity and verifies enabled runtime; unknown/tampered rows fail closed.
- Single owner serializes control mutations; SQLite/offloop work stays owned and joined across repeated cancellation. Epoch fences compensate a late enable with disable. Active plus bounded queued executions (max8, single execution slot) are tracked before admission; revoke/tools-off stop admission before awaiting, join all jobs, durably disable even on primary cleanup failure and preserve the typed error. Shutdown joins work while retaining a prior explicit durable enabled choice for exact restart; tools-off persists disabled and requires explicit enable after tools-on.
- Existing authorized ExecutionContext required; argument-only executor refuses. Cancellation/deadline/epoch fenced after async cleanup, not just before output. Local typed input/nested output/count bounds, no broad schema engine.
- Same-origin/session, candidate-only narrow Gateway controls; legacy and missing owner unavailable. UI separates approval/install, enable, revoke, manual status read and sample fill; no automatic retry or late response revival.

## E. Tests and Verification

Contracts D47 preceded production edits. Owner28 RED before source; foundation35 FAIL/1 PASS then seven row-facade RED; product79 RED; independent19 includes actual8 initial failures/10 controls and later queued1 failure; retain raw before/after artifacts. Initial owner drafting errors, a read-only runner fixture edit, a reserved test parameter and wrong schema script filename are retained as corrected implementation/fixture/invocation errors, not hidden as passes.

Final card after the visible history-label correction: **189 PASS /3 existing warnings /17.12s** (`card-after-history.log`: owner28, foundation43, lifecycle7, independent19, HTTP65, actual-page Node27). Earlier187 PASS16.19s is historical before those two UI cases. Product92 PASS includes the final65 HTTP and27 UI cases. Independent19 PASS4.67s; actualOS queue/PID and real SQLite pre-COMMIT cases explicitly separate from injected cleanup/timing seams. Actual fixed-template through normal pending→explicit approval→COMPLETED Chinese/fences/counts test, no fake model call. Prior D44 main composition32 PASS after preserving exact minimal review response shape.

Final full offline regression: **1,391 PASS /5 real_provider deselected /3 existing warnings /154.61s** (`full-after-history.log`). Earlier1,389 PASS158.46s is retained as the pre-history-correction result. Five real_provider tests remain intentionally unselected; no claim about real model semantics, latency SLO, voice or hardware.

Final full static checks after the two-file history-label correction: Ruff302 formatted files/lint PASS; mypy237 source files PASS; schema export check PASS (`*-after-history.log`). Final frozen source preservation/reverse-check-reapply PASS (`preservation-final.log`, `preservation.json`): baseline258/254 unchanged, exactly existing4/new7; D46 seven and protected Core/policy/worker unaffected. Only the final two UI files differ from phase1, other nine identical. Phase1 raw evidence/after/source patch retained under `phase1-source-audit/`; its older patch is historical. Final scoped sensitive-data scan: explicit11 source files **0 findings**; D47 evidence **356 raw records**, each exact-file/line detector fingerprint matches its recorded SHA256, **356 digest false positives /0 unresolved**. Explicit ten updated public architecture/status documents: **0 findings /0 unresolved**. Final review cutoff **2026-10-11 02:10:44 UTC** (`source-audit-report.md`, `secrets-*-final.json`). Audit outputs and subsequent root status/count/cutoff annotations are outside the snapshot cutoff; implementation/browser facts and hashes did not change. No blanket entropy exemption and no private data scanning. Final independent11-file binding agrees with preservation; D46 seven and254 remaining baseline files unchanged. Documentation diff check PASS.

Actual final CUA tab4 fixture binds registry/catalog/Gateway/index/owner hashes to final source. Prepare/install-disabled/enable/fill-without-send/revoke/readback passed; upper label identifies preparation history and lower label reflects current state. `browser-acceptance.json`, `browser-final-ax.txt`, final full/viewport JPG screenshots and source binding retained. Only temporary localhost18034 synthetic data used, no private owner state. Final fixture shutdown exit0 and `browser-server-after-history.log` record owned_jobs_after_shutdown0/temporary_workspace_removedTrue; source hashes read back equal and temporary path is absent. Actual OS lifecycle tests separately prove running/queued PIDs and workspaces gone.

Final tab console recorded one unattributed MutationObserver target error at2026-10-11T02:03:56.173Z; no origin URL/stack was returned. Earlier phase also recorded the same message. Public src search found no MutationObserver reference and final document has no external scripts; **origin UNKNOWN — NEEDS INVESTIGATION**, not proof of a product defect or a fix. The actual flow completed with correct states; do not claim zero browser errors. This observation does not justify a speculative production repair. Placeholder renderer is not a Live2D acceptance claim.

## F. Risk Assessment

Fixed builtin template only, not arbitrary model-generated software approval. Linux x86_64/system CPython3.14 supported profile; unsupported fails closed, no host/trusted fallback. Same-UID hostile mutation is outside the certified threat boundary; package no-follow/hash and row CAS resist stale identity but receipt is an owned local record, not a new signing system. Aggregate kernel RAM/cgroup/general dependencies/multiprocess/other OS remain unverified.

An interrupted package/receipt write may leave a disabled managed residue or disabled registry row; never auto-enable/overwrite/repair it. Status may require local investigation before reinstallation. Revoke cleanup failure still attempts durable disable and reports typed failure; a simultaneous storage failure is not proof of durable revoke and requires readback before any restart. Cached availability is descriptive; exact registry/bytes authority remains at execution.

Review expires/replaces and is not persisted across restart. Registered revoked capability remains unavailable and is not regenerated; owner can explicitly re-enable the same still-valid approved package. UI session/full-mode behavior and dialogue intelligence are not redesigned.

## G. Recommended Next Tasks

Continue RI-005's separate launcher/single-writer/latest-data-preserving rollback acceptance, with production activation still blocked until its checks pass. RI-006 operator resilience can use the new lifecycle baselines. FIX-002 useful search, FIX-005 first-audio/human listening and FIX-006 real comprehension remain separate product gates; do not treat this skill slice as their completion. Existing RT-011/013/015 DONE slices remain preserved and are not refactored again.

## H. Deferred Work

Arbitrary templates/code/dependencies, model self-approval, semantic duplicate discovery, persisted review history, release/autonomous deployment and broader OS/resource profiles remain outside this card. No numbered RT history/rankings changed. CI formatting was handled locally without user intervention.

## Rollback

Exact11-file source-only patch `repair.patch` SHA256 **04fcaac71e93f3166ed997b8b53bc1038cf69ed37498e921f55a7ccce6f0026f** is bound to final history-label source and189/1391 results. Final disposable reverse/check/reapply passed; first-phase patch/rehearsal remains historical. Disposable reverse/check/reapply verifies pre-card dirty bytes and all final bytes, with no live source apply or database rollback. For a running deployment, first tools-off/revoke and verify owned work/disabled readback; stop its known owner before restoring captured source. Retain current data, packages/receipts and any later memory, do not whole-DB restore. Source rollback removes this new caller while preserving all pre-card work; never relaunch an old caller against an unverified enabled package.
