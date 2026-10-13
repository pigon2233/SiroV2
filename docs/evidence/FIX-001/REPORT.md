# FIX-001 completion / 2026-10-04 (Asia/Taipei)

## Selected FIX
FIX-001 — failed/cancelled generation dispatch gate. DONE. Only this FIX handled.
All three unresolved cards were HIGH/REQUIRED_FIX with satisfied implementation dependencies; no CRITICAL or higher-severity card existed. Selected the directly unsafe failed-generation dispatch boundary with clear local scope. No FIX dependency is skipped; source RT-003's unrelated identity issue remains PARTIAL.

## Source Task
Architecture Review AR-03; existing RT-002/003/008 callers. HEAD already had dispatch ordering bug; not an RT-008 regression or unimplemented RT-009 issue. Read source roadmap, implementation reports and RT-008 independent verification, review probe/results, all eight authoritative documents and applicable AGENTS/runbook/STATUS/contracts/decisions. ARCHITECTURE_CORRECTION.md does not exist.

## Severity
HIGH / REQUIRED_FIX.

## Original Problem
Provider emitted tool intent then failed; controller dispatched it and accepted a subsequent successful round, overwriting the failure with completed. Partial cancelled generations could follow the same route.

## Verified Root Cause
CONFIRMED. ConversationEngine correctly preserves partial calls and FAILED/CANCELLED in TurnResult. Initial and continuation controller branches checked calls before state. CompanionCore also appended rejected calls as accepted canonical history; leaving this unchanged would permit journal registration of an invalid batch after adding the state gate. No configuration/test/stale-document cause of the original behavior. No DIAGNOSIS_MISMATCH.

## Reproduction
Formal production-path tests use synthetic streaming provider and effect handler, real Core/controller/orchestrator/SQLite in pytest temporary directories. Before production changes: 24 failed (before.log), first failing assertion proves extra effects. Profiles legacy/candidate × initial/continuation × connection/timeout/cancel × partial text on/off. Added eight real asyncio generation-deadline cases after the initial reproducer; final matrix 32 passed. No real provider network claim.

## Files Changed
- src/siro/services/presentation/integrated.py
- src/siro/core/companion.py
- tests/integration/test_agent_batches.py
- docs/DECISIONS.md (D21), CONTRACTS.md, STATUS.md
- docs/runtime-evolution/FIX_REGISTER.md, RUNTIME_EVOLUTION_ROADMAP.md
- docs/evidence/FIX-001/* (snapshots, precise patch, logs, scope, separate verification script/report)

## What Was Changed
Both calls to propose require COMPLETED. Existing final path keeps original error/state/text; legacy CANCELLED persists as CANCELLED rather than FAILED. Core canonical history retains partial text without rejected calls; raw TurnResult still retains calls. Optional final agent_steps.rejected_tool_calls preserves failed intent diagnostically. Successful final payload remains unchanged. No modification to journal repository or schema required; earlier accepted observations persist.

## Why This Is the Minimal Fix
Two dispatch conditions, local accepted-history correction and existing final-payload/state mapping only. Two production files changed. No retry/fallback, execution changes, restructuring, cleanup, dependencies or public port changes. implementation.patch compares against exact dirty-tree snapshots, not HEAD.

## Compatibility
Successful tool loops, provider IDs, prompt callers, automatic/full/manual authorization, approval, normal text/cancel/body/audio fixtures and terminal enums remain. Diagnostic field is optional internal final-step JSON, not an HTTP required field. Existing history/readback/unknown fencing preserved. scope.json confirms 108 other review fingerprints unchanged, including immutable migration 013 checksum; production changes only two expected files. All existing dirty changes retained; no private data/service touched.

## Tests Run
| Test / command | Result |
|---|---|
| pytest test_agent_batches -k failed_generation before fix | 24 FAIL; original defect reproduced |
| same original matrix plus real generation deadline | 32 PASS; task-verified.log |
| related conversation/integrated/batch/journal/terminal-fence/model-contract/tool-orchestrator/main/agent-runs/sqlite suites | 91 PASS; related-verified.log |
| full pytest -q | 317 PASS, 5 SKIPPED, 3 dependency warnings, 55.17s; full-suite-verified.log |
| ruff check src tests | PASS; ruff-final.log |
| mypy | PASS, 174 files; mypy-final.log |
| Separate HTTP initial/continuation × legacy/candidate with real effect file | 4 PASS; verification.log |
| Temporary prior-source legacy/readback/text-only/no-replay rehearsal | PASS; verification.log |
| exact patch reverse applicability / diff whitespace / review fingerprints | PASS; implementation.patch / scope.json |

Test integrity: all FIX cases traverse production generation/state/history/dispatch/persistence. Effects, model request counts, exact state/error, proposal count, one terminal, final diagnostic intent, paired prior observation and reopened readback are asserted; not merely absence of exception. FIX/related sets have no skip/xfail. Five full-suite skips are original opt-in real model/Groq speech tests and are NOT VERIFIED. Initial post-fix logs remain: 12 restart fixture failures (missing privacy), then four deadline fixture failures (legacy startup is lazy); fixed fixture setup without changing production. Historical logs not rewritten. Separate HTTP script initially used wrong callback keyword; verification-initial.log preserved, corrected to actual on_turn contract. These are test setup errors, not mismatches of the confirmed product diagnosis.

## Regression Baseline
| Relevant baseline | Verdict |
|---|---|
| conversation/partial streaming/text/cancellation/unique terminal | PASS |
| normal tools/batches/manual approval/deny/full authorization | PASS |
| provider payload/prompt compatibility/adapter contracts | PASS |
| accepted history/prior observation/journal restart/no blind replay | PASS |
| SQLite schema/upgrade/old-reader and configuration/main fixtures | PASS |
| memory/identity/relationship/body/audio automated fixtures | PASS (full suite) |
| real provider/Groq speech | NOT VERIFIED (5 opt-in skips) |
| real GUI/GPU/hardware/24h soak/deployed rollback | NOT VERIFIED; unchanged external release gates |

## FIX Acceptance Criteria
| Criterion | Verdict / evidence |
|---|---|
| failed intent zero effects/new dispatch; original ConnectionError retained | PASS (both profiles, 32-case matrix + HTTP) |
| cancelled generation stays cancelled | PASS (DB turn, AgentRun and single terminal) |
| initial failure one generation; continuation failure no third round | PASS |
| zero orphan pairing/extra terminal | PASS (canonical excludes rejected intents, no rejected proposals/call rows) |
| committed observations retained | PASS (continuation known result paired, readback unchanged after reopen) |
| partial text/error/failed intent preserved | PASS (canonical text, final diagnostic payload, original error) |
| restart no crash/replay | PASS (forbidden restart provider, real reopen, separate effect-file rehearsal) |
| successful tools/text/cancel/manual regressions in both profiles | PASS (related/full suites) |
| no critical regression/compatibility break/unresolved issue within FIX scope | PASS (required gates/scope checks) |

## Source RT Status
No dedicated failed source RT to restore for independent FIX-001. RT-002 DONE; RT-003 PARTIAL remains due to RT-003-FIX-01; RT-008 DONE limited to local journal/readback. Not promoting broader release readiness.

## Downstream Blockers
RT-009 FIX-001 gate cleared, status PLANNED, not started. RT-011/015 FIX-001 gate cleared but remain BLOCKED_BY_FIX due to other FIX/dependencies; summary/scheduler DEFER retained. Retry/privacy/budget and downstream acceptance assumptions unchanged; must be verified when those tasks run. RT-010/012/013/014 unaffected blockers retained.

## Remaining Issues
RT-003-FIX-01 and RT-005-FIX-01 remain PLANNED. Retention/repository coupling debt and external promotion gates unchanged. No unresolved blocker in FIX-001 scope. No new RT task begun.

## Architecture Deviations
NONE. D21 documents accepted-history and optional diagnostic detail within the card's proposed choice; no correction or scope escalation required.

## Rollback
Stop new affected work, fence tool dispatch, drain/cancel owned jobs, retain journal/unknown. Exact source patch may be reversed only for this FIX; do not reset dirty tree. Reversing restores the unsafe failed-intent behavior, so tools must remain disabled; RT-009 gate must be restored. Temporary rehearsal copied current package and replaced only two caller files with saved pre-fix source, kept schema/readers/guard, verified failed-run readback, new text-only run and unchanged real effect file. Source reverse check PASS is separately only patch applicability. Actual deployed rollback NOT VERIFIED; no DB downgrade/delete/restore. Return register/roadmap to unresolved status if reverting repair.
