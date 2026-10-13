# FIX-010 final independent scoped review

2026-10-10. Reviewer: dialogue_failure_guard_research; final pass read-only. No additional confirmed blocker in this card. Final numeric NULL guard is present. Reviewed the current three production files and new synthetic fixtures; no private records or live service inspected.

The original PENDING→APPROVED transaction checks expected state first, retains CAS, and holds automatic approval with fixed PriorOutcomeUnknown without changing pending or historical ledger. Candidate v1 fenced, dispatched same-session/capability calls with explicit unknown, NULL or invalid receipt participate, independent of old privacy route/age. Missing/orphan/cross-owner/capability/payload binding holds conservatively.

Both payloads are byte-bounded before JSON validation. Recursive decoded-key paths preserve object order/Unicode equivalence and distinguish array positions/types. Duplicate keys and unavailable numeric lexemes are unverified; numeric source lexemes avoid SQLite atom precision collisions. No raw historical payload reaches Python/model context. Trusted descriptor read exemption removes only this additional hold, not original readiness/schema/grant/executor checks. Optional metadata/risk/model strings cannot exempt effects.

Controller explicitly marks automatic resolution and emits the single proposal after that decision. Gateway manual resolution preserves the default, original hash check and existing replay fence. UI uses one fixed blocked code/text warning with explicit manual button. Cancellation and batching are preserved by tests.

## Limits retained

- Existing single-owner/controller finish-before-new-run scope; not arbitrary multi-controller post-approval races.
- Existing service-written arguments_hash is trusted; arbitrary DB hash tampering is not certified.
- Exact content identity, not semantic deduplication of different arguments/capabilities.
- Manual approval of a new action never resolves or deletes the old unknown result; further explicit confirmation may remain necessary.
- Valid JSON receipts without the exact unknown marker retain original interpretation; not every timeout/provider failure is diagnosed by this card.
- WebSocket reconnect card retention is distinct from full page reload restoration, which remains an existing gap.
- Dialogue semantics, speech speed/complete listening, useful public search and autonomous release gates remain separate.

Post-review added real candidate counterexamples before correction: Unicode fullkey spelling, same-owner wrong-payload binding, large integer atom collision, duplicate keys and quote-key numeric extraction. No original-design invalidation or new subsystem was required. Local tests are evidence of these fixed invariants, not overall intelligence or deployment.
