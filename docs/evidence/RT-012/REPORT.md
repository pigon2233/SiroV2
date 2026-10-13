# RT-012 persistent browser session — 2026-10-05

Status: **DONE**. Completion date:2026-10-05. All three task acceptance criteria and related automated regression checks passed.

## Selected Task / Why selected

RT-012 is the first PLANNED executable task after RT-001–011 DONE. Its RT-005/007 dependencies and FIX gates are satisfied. selection.json records all15 tasks. RT-011 summary and RT-013/015 remain DEFER. RT-014's historical BLOCKED wording references already-DONE RT-010: discrepancy recorded, not expanded into another task.

F09 correctly identifies main browser_tool's per-call driver context manager and the lack of fill/click callers. The underlying ScopedBrowserDriver already implements semantic targets, stale DOM version checks, scoped routing and action readback; it is not rewritten. Task acceptance is cross-step state retention, post-action readback and stale-target rejection.

## Files changed

Production: src/siro/services/tools/browser_session.py (new wrapper), src/siro/services/presentation/gateway.py (composition/lifecycle), src/siro/services/tools/orchestrator.py (candidate schemas and enum validation).
Tests: tests/integration/test_browser_sessions.py (new), tests/integration/test_tool_catalog.py (additive tool inventory assertions; previous route/pair/kill-switch assertions retained).
Documentation: DECISIONS D29, CONTRACTS, STATUS, RUNTIME_EVOLUTION_ROADMAP and this evidence directory. completion.patch and digests.json cover exactly five implementation/test files against this turn's snapshots, preserving all previous dirty work. No new dependency, source move, rename or migration.

## Runtime path / Implementation summary

Candidate main -> descriptor/catalog -> normal proposal/authorization/journal -> contextual executor with trusted ExecutionContext.session_id -> BrowserSessions -> existing ScopedBrowserDriver -> tool observation/model consumer. Session identity is not a model argument. The main integration fixture traverses actual main, IntegratedCompanion/Core, catalog/orchestrator, SQLite journal and real headless Chromium against a local synthetic HTTP form; only the model/body transport are synthetic.

Same-origin navigation and completed runs reuse the driver/sessionStorage. Explicit new-origin navigation closes the old scoped driver and creates a replacement instead of widening scope. Candidate-only browser.read/fill/click/close use existing authorization/kill switches; navigate+read name and URL input remain unchanged. Fill/click require exact role/name/version and return fresh readback. Epoch-prefixed screen versions reject different sessions and recreated drivers even if the DOM hash matches. Existing driver DOM verification prevents stale actions within one epoch.

Default8 sessions,300s idle TTL,30s action timeout (or earlier context deadline), per-session serialization and bounded4s cleanup. A lifecycle reaper evicts idle resources; cancel tokens, repeated task cancellation, explicit close, endpoint cancellation and shutdown clean owned resources. Cleanup failure raises ExecutionCleanupError, retains ownership and refuses new work. A shared control WS lacks canonical conversation identity: disconnect cleanup is by idle TTL rather than guessing which conversation to kill. No credentials/profile are persisted; restart loses ephemeral browser state without action replay.

## Tests run / Regression results

- Before-source actual main fixture: FAIL (exit1), no successful browser observations; prior catalog lacks required browser actions. before.log uses temporary source copies, isolated data and local synthetic content, never the private DB.
- Initial new five cases:5 PASS (task-initial.log).
- Initial adjacent suite:31 PASS/2 FAIL (task.log): old exact catalog inventory assertions did not include the newly authorized actions. Updated only inventory assertions, retained route/observation checks.
- Final task/adjacent:33 PASS,3 dependency warnings (task-final.log), including real Chromium form/state/isolation/stale/TTL/close, actual main across runs/shutdown, existing real navigation cancel, and catalog/legacy checks.
- Ruff/mypy/format: final logs; mypy183 files. Initial type/fixture diagnostics preserved in mypy-initial.log.
- Full regression:419 PASS,5 opt-in SKIP,3 dependency warnings,127.82s,exit0 (full.log). Five real-provider/speech tests are opt-in; skip is not pass.
- Scoped reverse patch dry check and whitespace checks passed. Feature-off and legacy stateless behavior exercised in isolated main fixtures, two calls/two closed drivers; no private deployment change.

## Acceptance criteria

| Criterion | Evidence | Result |
| --- | --- | --- |
| Cross-step state preserved | Real Chromium fill -> next page -> save; different run contexts and actual main two completed runs | PASS |
| Post-action readback | Main model receives tool content containing Saved Runtime; explicit read returns retained result | PASS |
| Expired target rejected | Real DOM change, cross-session version and recreated-driver version rejected before action; TTL loses state explicitly | PASS |

Compatibility: legacy/default injection static schema/path unchanged; candidate startup SIRO_BROWSER_SESSION_ENABLED=0 omits additional tools and restores stateless navigation. Existing full auto-authorization, proposal argument hash, journal unknown-outcome/replay protections, HTTP/WS URLs and state/config formats remain unchanged. The opaque candidate screen version adds an epoch; old stateless screen versions stay unchanged on rollback.

## Remaining issues / Scope discipline / Architecture deviations

No driver-core change or desktop/sudo, login credential persistence, identity/affect/audio/model asset changes. Wrapper lives in services/tools instead of modifying adapter internals; optional Gateway shutdown callback and catalog schemas are necessary additive wiring recorded in D29. Browser state is ephemeral,8-session bound per Gateway, not a cross-process broker. On any action error the affected session is closed and requires navigation again; already performed effects cannot be undone or assumed absent. Origin switches intentionally discard prior cookie/state. Current driver semantic click/scope behavior is inherited, not a general desktop-control guarantee.

Related browser L2 tests use actual headless Chromium/local pages; no public-site login, real LLM planning, owner visual GUI walkthrough or long-duration/power-loss release test is claimed. These release-level validations are separate from this task's acceptance, not unfinished RT-012 production features. Running port8000/private DB were untouched.

## Rollback method

At a drained next startup set SIRO_BROWSER_SESSION_ENABLED=0 (candidate retains stateless navigate) or select legacy. Shutdown cleans active/idle owned drivers first. No state/schema rollback or journal deletion. To revert source only this task, validate digests and `git apply --reverse --check docs/evidence/RT-012/completion.patch`, then apply that scoped reverse patch; do not reset the broad dirty tree. Isolated feature rollback behavior and source dry check are verified; private deployment rollback was not performed.

Only RT-012 selected; stop after its completion, no RT-014/next task implemented.
