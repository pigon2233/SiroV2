# RT-003-FIX-01 repair / 2026-10-04 (Asia/Taipei)

## Selected FIX
RT-003-FIX-01 — DONE. Chosen first of the remaining equally HIGH cards; dependency implementation RT-002/007/008 exists. This card completed and verified before starting the next FIX. No downstream RT development.

## Source Task
RT-003, Architecture Review AR-01, RT-008 exact ownership/recovery callers. Original task/evidence, RT-008 independent report, relevant contracts/decisions, authoritative eight documents, probe/results and affected production paths checked. ARCHITECTURE_CORRECTION absent.

## Severity
HIGH / REQUIRED_FIX.

## Original Problem
Same session's valid subsequent run with provider ID call-0 was rejected in RAM; restart hit SQLite UNIQUE(session_id,call_id). Session/call matching also allowed old proposal callbacks/recovery to be confused with current run.

## Verified Root Cause
CONFIRMED. Provider-local ID was reused as session-lifetime storage/dispatch identity. Fixing only RAM is insufficient. Existing exact journal proposal_id relation supports a local repair without changing schema or model pairing.

## Reproduction
Two formal counterexamples failed before fix: consecutive/restarted reused provider IDs; old callback while a new manual batch reuses the ID (before.log). Synthetic provider/handler, real controller/Core/SQLite. Additional same-run duplicates, A/B isolation, transaction injection, true subprocess crashes, legacy/mapped rows and HTTP fixtures enforce desired behavior; no private DB.

## Files Changed
Production: services/presentation/integrated.py, services/tools/orchestrator.py, services/agent/runs.py.
Tests: test_agent_batches.py, test_tool_orchestrator.py, test_run_journal.py.
Docs: DECISIONS D22, CONTRACTS, STATUS, FIX_REGISTER/ROADMAP, this evidence (snapshots/digests/patch/logs/crash/independent rollback script).
Gateway/provider/execution/audio/migrations/dependencies untouched.

## What Was Changed
Candidate private tool_proposals.call_id is the existing proposal UUID; run_journal_calls keeps provider ID. Proposal INSERT and exact run/call proposal binding commit together. Repository reads/transitions return original provider ID through exact binding. Dispatch guards require exact owner; historical unbound insert-before-bind gaps use matching payload/session/call only, ambiguity fails closed. Callback must belong to current run's exact proposal list. Reconcile fences exact proposals; old unbound rows retain conservative unknown/no replay. Dedup keyed by run and cleared at terminal. bind_call cannot overwrite a different established binding.

## Why This Is the Minimal Fix
Uses existing UUID, tables, atomic transaction and binding; no new migration/ID framework/repository redesign. Three expected production caller files only. Does not tackle terminal-map retention debt beyond this dedup state. implementation.patch isolates this FIX from prior FIX-001 and existing dirty changes.

## Compatibility
Original public ToolProposal IDs/HTTP events/model result pairing/approval URL/argument hash/full authorization preserved. Legacy raw rows/callers remain readable. Historical pending candidate proposals remain fenced in current legacy mode. Successful provider payload and prior observations unchanged. New mapped rows require retaining this identity reader/guard on rollback; raw old reader sees internal UUID, so a completely old binary is not assumed compatible for execution. Migration 001–013 and all other source/test files verified unchanged using before-digests/scope.json.

## Tests Run
| Command / test | Result |
|---|---|
| initial two counterexamples | 2 FAIL before fix |
| batch/journal/tool-orchestrator source suites | 65 PASS (task-final.log) |
| all listed ownership/batch/main/adapter/schema/execution regressions | 125 PASS (related.log) |
| full Python pytest | 326 PASS / 5 opt-in skips / 3 warnings, 58.37s |
| ruff / mypy | PASS / 174 files PASS |
| separate identity verification, real effect file | Three runs including restart, exactly 3 effects PASS |
| isolated caller rollback with retained reader/guard | Readback/original ID, old approval fenced, new text run, zero replay PASS |
| scope digests / exact reverse applicability / whitespace | PASS |

Initial post-fix failure was a test sorting raw private storage IDs instead of canonical batch indexes; changed fixture query only, original order/deny acceptance unchanged. Initial HTTP fixture expected call_id in a response that has always been status-only; corrected to assert exact status response and real public tool events/readback. Failures retained in initial-after.log/task.log. No DIAGNOSIS_MISMATCH of original product defect. No swallowed exception, skipped FIX test, xfail, or effect-only mock claim: tests assert real repository fields, payloads, counts, owner/state and reopened pairing. Synthetic provider/UI/handler fixtures are labelled; process crash and effect file are real OS/filesystem integration.

## Regression Baseline
PASS: source RT-003 batch barrier/mixed success/failure/manual deny/callback dedup/step limit/200 cancel ordering cases; RT-002/native adapter pairing/prompt compatibility; RT-008 four crash points/old insert-bind gap/reopen/no-replay/unknown/budget/upgrade/old-loader; gateway terminal fence/main/catalog; relevant execution, identity/memory/body/audio automated baseline through full suite.
NOT VERIFIED: five opt-in real model/Groq speech tests; real GUI/GPU/soak/power loss/deployed rollback. No expansion of product release claims.

## FIX Acceptance Criteria
- PASS: three valid independent runs (including restart) each once, original call-0, no IntegrityError.
- PASS: same-run/batch duplicate zero additional effect; A/B unaffected.
- PASS: callbacks from old exact proposal cannot mutate new readback/UI; current manual approve/deny works.
- PASS: insertion/binding failure rolls back both; subprocess crash before/after atomic commit zero replay; original historical gap test remains.
- PASS: mixed rows have correct owner; old unknown retained and new non-dispatched not falsely unknown; recovered approvals fenced in fresh/legacy runtime.
- PASS: HTTP response/event and provider pairing compatibility; migrations/checksums unchanged.
- PASS: required regression/no new critical regression/compatibility/no unresolved in-scope blocker.

## Source RT Status
RT-003 DONE / VERIFIED within original batch acceptance plus repaired identity scope. RT-008 stays DONE within local readback; original tests re-run. Previous PARTIAL and review evidence preserved as history.

## Downstream Blockers
RT-010 FIX gate cleared; RT-011 budget FIX gates cleared (summary still DEFER/dependent on RT-010); RT-014 still awaits RT-010. RT-012/015 still blocked by RT-005-FIX-01 and other original prerequisites/DEFER. No downstream implementation begun.

## Remaining Issues
RT-005-FIX-01 remains unresolved at this card's completion. Global RAM retention/single-owner coupling and release external gates remain. No in-scope blocker.

## Architecture Deviations
NONE. Existing proposal binding and transaction used; no correction/scope escalation.

## Rollback
Stop candidate new dispatch and drain/fence jobs, retain unknown/journal. New mapped rows require retaining orchestrator identity reader/ownership guard and exact recovery reader. Temporary rehearsal copies current package, restores pre-FIX integrated caller only, switches to legacy with tool dispatch disabled; pending mapped original ID/readback still readable, attempted old approval rejected, new text succeeds, effect file unchanged. Full old binary is unsafe for mapped call identity/replay. Do not delete rows/downgrade DB/reset dirty tree. Exact implementation.patch reverse check only proves applicability, not safe removal of compatibility code. Actual deployed rollback NOT VERIFIED; restore unresolved FIX gates if reverting.
