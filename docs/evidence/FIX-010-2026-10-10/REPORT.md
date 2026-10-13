# FIX-010 — Fresh call IDs cannot automatically repeat unknown effects

2026-10-10. **DONE / VERIFIED** for this bounded repair. Classification REQUIRED_FIX; severity HIGH; source FIX-006 synthetic dialogue evaluation and independent actual call-path review. Confirmed implementation/integration/test gap, not a proven private incident or a specific historical RT regression.

## Problem and smallest repair

The old proposal replay fence remains valid, but a new model call receives a new proposal UUID. Full mode previously auto-approved and executed the same session/capability/arguments even when the earlier fenced dispatch had an unknown result. The [original real controller counterexample](counterexample-before.json) executed the synthetic counter once where zero was required; no OS action was executed.

Exactly three production files changed: existing SQLite proposal approval transaction, IntegratedCompanion automatic resolution and existing proposal-card rendering. No new ledger, abstraction, owner, scheduler, DB migration, model/provider/budget change or grant expansion. Core, Memory, prior browser/voice/session/skills/patch/release repairs and private data remain unchanged.

D42 makes automatic resolution explicit while preserving manual resolve's default. In the original BEGIN IMMEDIATE PENDING→APPROVED transaction, candidate v1 fenced dispatched same-session/capability calls with explicit outcome_unknown, NULL or invalid receipt hold matching content. Missing/orphan/cross-session/capability/payload binding conservatively holds that capability. There is no TTL/history cutoff or privacy-route reset. Fixed PriorOutcomeUnknown leaves pending and historical records unchanged.

Binding verification stays inside SQLite: bounded UTF-8 object JSON, recursively decoded-key JSON-array paths, symmetric structural comparison, source numeric lexemes, duplicate-key and missing numeric-lexeme rejection. This avoids exposing raw history/arguments/receipts to Python/model context. Only the current trusted descriptor.effect=read exempts the extra hold; original availability/schema/grants/executor authorization remain.

The controller decides automatic approval before emitting one proposal. Full mode now displays a fixed unknown-result/duplicate-effect warning and the existing explicit manual button. A new manual approval can execute that new proposal once; it never certifies, deletes or resolves the old unknown effect.

## Verification

- Final 44 backend cases plus actual frontend renderer case against the exact three dirty pre-card sources: **45 FAIL /2 warnings /3.19s**, with isolated import/hash proof in [complete-tests-before-final.json](complete-tests-before-final.json).
- Final new and adjacent batches/journal/catalog cases: **122 PASS /3 existing warnings /20.71s**, [tests-after-final.log](tests-after-final.log). Cases cover identity/route/session boundaries, unknown receipt variants, wrong binding, JSON Unicode/order/numeric/duplicate edges, immutable ledger/CAS, manual/denial, read exemption, cancellation and mixed held/normal batch behavior.
- Full offline suite: **991 PASS /5 real_provider deselected /3 existing warnings /118.71s**, [full-suite-final.log](full-suite-final.log). Opt-in providers are separate; this repair adds no provider calls.
- Format/lint/type/schema/diff checks PASS: 226 formatted files, 216 mypy files; [checks.json](checks.json). Initial new-test tuple inference error corrected with an explicit annotation only; no assertion weakened. [Explicit allowlist secret scan](secrets.json): zero findings, no private scan.
- Real Chrome 154.0.8037.92 + actual HTTP/WebSocket/controller/current UI: **21/21 PASS**, [ui-verification.json](ui-verification.json). Single held card, pending/zero automatic counter effects, reconnect without model retry/POST/effects, 401 and tools-disabled 403, explicit manual button once, completed terminal once, duplicate POST404 without another effect, exact old unknown ledger unchanged. Source hashes match start/end; browser/server/temporary DB removed.
- Browser screenshots [held](unknown-effect-held.png), [approved](unknown-effect-approved.png) visually checked. An intermediate harness assertion wrongly expected NULL after finish_journal's existing recovery receipt; preserved separately and corrected to exact before/after ledger comparison in [runner notes](ui-runner-notes.md). Production source remained identical.
- Independent [final scoped source review](source-review.md) found no remaining confirmed blocker within this card. Post-review candidate defects were reproduced before correction: wrong payload binding, Unicode fullkey spelling, large integer atom collision, duplicate keys and quote-key numeric extraction. All failure logs retained; synthetic corruption pragmas never touch production DB constraints.
- [229 pre-card source hashes](preservation.json): only the three listed production files changed; two tests added, no existing test edited. Exact five-file isolated [reverse/reapply rehearsal](rollback.json) PASS; [repair.patch](repair.patch). Prior D41 and all existing dirty changes preserved.

## Explicit remaining limits

Exact content identity is not semantic deduplication of equivalent actions with different parameters/capabilities. The current single-owner/controller finish-before-new-run boundary and service-written arguments_hash remain assumptions; arbitrary multi-controller post-approval races or DB hash tampering are not certified. Different numeric spellings or quote-bearing numeric keys may conservatively require manual confirmation.

Valid JSON receipts without an exact unknown marker retain existing interpretation; this card does not diagnose every external timeout. Manual approval does not resolve the previous unknown, so later confirmation can recur. Unknown-ledger scan/retention and an explicit result-resolution workflow are TECH_DEBT with no demonstrated resource failure; do not add automatic expiration or another state manager.

The gateway active-turn snapshot can show completed while the agent waits for approval, and full page reload does not restore pending cards. These existing lifecycle/recovery gaps are not claimed repaired by same-page WebSocket reconnect. No real provider, OS effect, audio, Live2D, private conversation, live8026 restart or deployment acceptance was performed.

FIX-006 remains PARTIAL: actual model semantics/voice correction/style/privacy distinctions are independent of this hard approval guard. FIX-002 useful public search, FIX-005 latency/listening and RI-003–005 isolation/review/release gates remain. No original-design invalidation or ARCHITECTURE_CORRECTION is warranted.

## Rollback

Switch affected runtime to existing safe/manual mode and drain owned turns before reversing only this patch against matching after hashes. Retain all journals/proposals/private data and prior D41; never restore an old DB or replay unknown effects. The vulnerable old full-mode auto path cannot be used for unknown actions during rollback. Temporary source reversal/reapplication is verified; no live rollback or restart was performed.
