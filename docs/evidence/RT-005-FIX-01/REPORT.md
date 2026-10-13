# RT-005-FIX-01 repair / 2026-10-04 (Asia/Taipei)

## Selected FIX
RT-005-FIX-01 — DONE, after RT-003-FIX-01 separately reached DONE. This is the last unresolved registered FIX; no downstream RT implementation.

## Source Task
RT-005 optional contextual executor, RT-007 descriptors, Architecture Review AR-02; RT-008 journal/cancellation callers. Existing owned argv acceptance retained. Authoritative documents, relevant implementation/verification/audit evidence, AGENTS/contracts/experience/security/acceptance and actual caller paths checked. No ARCHITECTURE_CORRECTION exists.

## Severity
HIGH / REQUIRED_FIX.

## Original Problem
Only contextual tasks were registered in _active. Candidate arguments-only handlers could continue after cancellation terminal; known browser/application callers were in this branch. Journal unknown/fenced UI alone did not stop the handler.

## Verified Root Cause
CONFIRMED. Registration/cancellation waiting belonged only to the contextual branch. Further in-scope reproduction confirmed acquired browser/Playwright leaked when __aenter__ was cancelled; production application caller lost an owned launcher during spawn/pre-ack cancellation. These are confirmed local lifecycle gaps, not proof of all GUI cleanup failure, not a DIAGNOSIS_MISMATCH or backend PGID bug.

## Reproduction
Before fixes: two auto/manual cooperative arguments-only cases plus acquired-browser enter cancellation all FAIL (before.log). Captured actual main application caller with real synthetic owned subprocess: spawn and pre-ack cases FAIL, ack case PASS (launcher-before.log). Tests clean their fixture-owned processes only; no private directory/GUI application/user process control. Desired assertions retained and turn PASS after repair.

## Files Changed
Production: services/tools/orchestrator.py, services/presentation/gateway.py (application caller only), adapters/browser.py (only after fixture-confirmed startup/close gap).
Tests: test_execution_lifecycle.py, test_gateway_main.py.
Docs: D23/CONTRACTS/STATUS/FIX_REGISTER/ROADMAP and this evidence (snapshots, digests, patch, logs, verification/rollback).
No changes to integrated terminal mapping needed; existing ExecutionCleanupError -> FAILED path used. execution.py, migrations 001–013, models/config/dependencies/voice/core/identity untouched.

## What Was Changed
All candidate invocations share owned task registration; arguments-only tasks receive one cancellation, contextual executors keep token cleanup. Done callbacks retain ownership until actual task completion; outer caller cancellation also requests run cleanup. Cleanup waits at most 4.75s; refused/delayed cleanup maps to ExecutionCleanupError, and journal keeps dispatched unknown. Suppressed cancellation cannot convert into successful tool completion. Late UI/dispatch fences remain.
Browser start/launch acquisition is protected so returned resources can be closed even when cancelled; failed __aenter__ cleans acquired resources, and Playwright stops even if browser.close fails. Candidate application spawn protects the owned handle and group until original acknowledgment; uses existing protected PGID cleanup, including probe handle on cancellation. Legacy application behavior and acknowledged user-managed lifetime remain.

## Why This Is the Minimal Fix
Common invocation/task boundary plus necessary existing browser/application cleanup only; no new supervisor, signature, browser session, schema or argv backend change. Reuses existing protected owned-group cleanup. No process-name cleanup or unrelated retention work. Exact patch based on dirty-tree snapshots preserves FIX-001 and RT-003-FIX-01.

## Compatibility
Arguments-only executor(arguments), contextual constructor, full authorization/hash/catalog availability, provider tool IDs/payload, HTTP/WS/state/schema and default legacy preserved. Existing contextual argv output/TERM-KILL/reap/detach behavior retained and re-run. Ack app remains user-managed; no cancellation of unrelated session/process. Original Firefox/GTK response shapes preserved. Existing browser navigation/readback/scope/stale-target contracts pass using actual local Chrome. Unknown means external effects are not proven stopped; cancellation is never an exactly-once/whole-OS claim.

## Tests Run
| Test / command | Result |
|---|---|
| cooperative auto/manual + browser enter before fix | 3 FAIL (before.log) |
| main GTK spawn/pre-ack before fix | 2 FAIL / ack PASS |
| intermediate lifecycle/main/batch/terminal-fence gate | 75 PASS (task-initial.log) |
| final source lifecycle + main caller suites | 33 PASS (task-final.log) |
| affected lifecycle/bounded/batch/catalog/tools/gateway/main/fence/journal/browser set | 147 PASS (related.log) |
| full Python suite | 344 PASS, 5 opt-in skips, 3 warnings, 68.58s |
| ruff / mypy | PASS / 174 files PASS |
| separate real-file cancellation verification | cleanup before terminal, no effect/new dispatch; 0.027s PASS |
| temporary pre-FIX source legacy text-only rollback | retained journal/unknown, zero replay PASS |
| source/test digests, exact patch reverse check, whitespace | PASS |

All FIX/source cases have no skip/xfail and assert effects, cleanup ordering, state/error, ownership, original responses, bound timing, no late UI, other-session progress and readback. No success-only/no-exception acceptance. Synthetic model/Playwright-startup fixtures are labelled; main GTK/Firefox callers use real synthetic subprocesses, not actual GUI launches. Actual production main browser handler plus installed headless Chrome navigates only a blocked localhost fixture and is cancelled; browser disconnected and Playwright closed. Existing full browser-driver suite also uses real Chrome. Initial fixture lint/type errors fixed without changing acceptance; before/after/intermediate logs retained.

## Regression Baseline
PASS: cooperative auto/manual handler cancellation, queued zero-entry, simultaneous completion/cancel existing 200 ordering cases, bounded refusal/noncooperation, shutdown actual lifespan, A/B isolation, manual HTTP cancellation with real argv tree under both contextual and arguments-only wrappers, original owned argv cap/PGID/ack tests, writer/consumer terminal fence, catalog/readiness/hash/authorization, run journal/unknown/no-replay, current identity and generation fixes, normal legacy/candidate paths and full automated core/audio/body/state fixtures.
NOT VERIFIED: five opt-in real provider/Groq speech cases, actual GUI application/escaped daemon cleanup, GPU/voice/24h soak/power loss/deployed rollback. Real localhost headless Chrome evidence does not imply all desktop cleanup is complete.

## FIX Acceptance Criteria
- PASS: original cooperative handler failure -> pass; finally completes before terminal, barrier release creates zero effects.
- PASS: queued cancel zero handler entry; manual approve/HTTP cancel remains compatible and no late result.
- PASS: refused cleanup and deliberately suppressed cancellation produce FAILED/ExecutionCleanupError in <5s and outcome_unknown; retain active task until its eventual cleanup, do not pretend externally stopped.
- PASS: single terminal/no new dispatch/late UI; other session still completes normally.
- PASS: actual shutdown waits handler cleanup; browser startup/close failures clean acquired resources/stop Playwright; real local navigation closes browser connection.
- PASS: actual caller synthetic spawn/pre-ack process stopped/reaped for GTK/Firefox; original acknowledgment shapes and user-managed ack lifetime preserved.
- PASS: original contextual argv/manual approval/ack detach/restart unknown and adjacent regression gates pass.
- PASS: compatibility/protected zones/no critical new regression/no unresolved blocker within measured FIX scope.

## Source RT Status
RT-005 remains DONE for original owned argv; repaired candidate arguments-only lifecycle verified within controlled fixtures and real local browser boundary. Does not extend status to arbitrary GUI/D-Bus/external processes. RT-007/008 retain limited DONE; original acceptance suites re-run.

## Downstream Blockers
RT-012/013/015 RT-005-FIX-01 gate cleared. RT-012 becomes PLANNED; RT-013 stays DEFER until concrete scoped caller/parity evidence, RT-015 stays DEFER/dependent on RT-014 and retention/single-owner expansion gates. RT-014 still awaits RT-010; RT-011 summary still DEFER. All registered FIX gates cleared, no downstream RT begun.

## Remaining Issues
No unresolved registered FIX. Retention/coupling debt, session hydration/retry/new browser features and external release gates remain outside scope. A noncooperative backend may still have effects after requested cancel; explicit failure/unknown and retained task ownership cover uncertainty, not a guarantee to kill it. Application D-Bus/escaped external effects cannot be proven stopped by owned-group cleanup; preserve unknown and do not scan/kill other processes.

## Architecture Deviations
NONE. Conditional browser scope was justified by pre-fix fixture. No escalation/correction required.

## Rollback
Fence new candidate tool work, cancel/drain owned tasks, preserve journal/unknown. Do not hand live tasks to old wrapper. Separate rehearsal copied current package, restored exact pre-FIX orchestrator/gateway/browser source (already containing prior identity repair), then restarted legacy text-only with no tools; cancelled run readback unchanged, new text completes, cleanup marker retained, no effect/replay. Removing this FIX restores unsafe arguments-only cancellation, so that candidate path/promotion remains disabled and its gates must be restored. No DB downgrade/delete/reset/pkill. Reverse patch check proves applicability only; actual deployed rollback NOT VERIFIED.
