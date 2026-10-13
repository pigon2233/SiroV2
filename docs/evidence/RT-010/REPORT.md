# RT-010 session context hydration — 2026-10-05

Status: **DONE**. Completion date:2026-10-05. Selected exactly RT-010, the first incomplete executable RT task. RT-001–009 and all required FIX gates are DONE; RT-010 depends on RT-008. RT-011/012/014 remain outside this implementation. selection.json records all15 task statuses/dependencies at selection.

## Intent / actual path

RT-010 and architecture review AR-01 follow-up request bounded recent session context across restarts, isolation, canonical/raw distinction and reuse of RT-008 journal. Existing WorkingMemory is RAM; SQLiteConversationRepository user rows can contain assembled prompts. Existing journal/reconcile/readback solves run recovery but Integrated creates empty history for new runs, so prior completed dialogue is not supplied to providers. Required callers: gateway.main → Integrated.respond → repository.recent_session_messages → CompanionCore.respond → ConversationEngine → selected provider. Core remains the append owner; on_messages_ready checkpoints before provider invocation. Continuation uses the existing same-run history without hydration.

D26 and CONTRACTS define the small extension before production changes. Necessary Integrated/Gateway runtime wiring exceeds the roadmap's expected file list; recorded discrepancy, not unrelated expansion. No journal reconstruction/reconciliation rewrite, Core provider import, rename/move, new dependency or architecture redesign.

## Implementation / files

- core/companion.py: optional recent_messages; fresh native system + prior user/assistant pairs + current raw user. Skip RAM recent context when canonical recent messages are supplied, preventing duplicated assembled context. Existing callers and legacy default None keep behavior.
- services/agent/runs.py: query only exact session, identical privacy class, version1 candidate terminal COMPLETED journals. Read no more than6 rows for default12 messages. Extract last raw user matching immutable goal (whitespace-preserving input, stripped immutable goal) and final assistant text without tool calls. Complete pairs preserve order; no slicing inside a tool batch. Corrupt version1 dialogue fails explicitly. Legacy/unsupported version/nonterminal/interrupted rows are not treated as canonical completed dialogue.
- presentation/integrated.py: load recent messages once before a normal candidate new run, and before emitting assistant_started. Direct commands keep existing behavior; continuation does not hydrate. Load failure cannot invoke a provider or create a new run.
- presentation/gateway.py: startup-frozen SIRO_SESSION_RESTORE_ENABLED=0|1, candidate default1, feature-off and legacy keep original path.
- tests/integration/test_session_restore.py:9 task cases covering three restarts through actual main/Core/SQLite/ASGI; A/B, feature-off, legacy, bounds/privacy, malformed data, readback-only interrupted states, and actual Python tool subprocess followed by restart with no replay.
- tests/integration/test_integrated_companion.py: existing native provider serialization test parameterized for restore on/off; keeps old no-restore expectation and original same-run tool pair assertions, adds restored raw goal/final response and no historical intent/result assertions.
- docs: D26/CONTRACTS, roadmap/STATUS and this evidence folder.

## Scope and safety

Hydrate recent completed dialogue only. Rebuild current system instructions/memory/affect/runtime context; do not reuse old system prompt or infer raw text from legacy tables. Previous intermediate tool intents/results are not session conversation turns and are not copied to executable context. Their provenance and outcomes remain intact in RT-008 readback. Unknown/interrupted actions are never automatically resumed. Same privacy class prevents newly selected cloud from receiving prior local-only dialogue. One existing runtime owner and journal; current budgets/goal/provider metadata remain intact. No changes to DB migrations, state/config JSON formats, HTTP/WS required fields, long-term memory facts, identity, affect/relationship algorithms, audio/reference/Live2D or Rust.

## Reproduction / verification

- before.log: reconstructed pre-task source in a temporary source copy, PYTHONPATH confirmed by traceback. At second main startup candidate request lacks raw-goal-0/answer-0; expected new test FAIL, exit1. Working tree was not reverted.
- before-launch-error.log: first reproduction launcher erroneously resolved the venv interpreter symlink to system Python; pytest unavailable. This is a harness error, not product evidence; retained and corrected with absolute venv path.
- task.log:9 passed /3 dependency warnings before final nonfunctional lint adjustment and pre-emission load placement; final code included in full gate below.
- full-initial.log:1 failed /386 passed /5 opt-in skipped, 102.10s. The RT-002 fixture expected every new candidate run to have no prior native dialogue, conflicting with this task. Preserve feature-off assertion, add feature-on assertions; no product behavior workaround or relaxed tool-pair checks.
- task-final.log:15 passed /3 dependency warnings after the compatibility fixture update (includes9 new task cases and6 Integrated cases).
- full.log: **388 passed, 5 opt-in skipped, 3 dependency warnings, 89.73s**, exit0. Full gate includes task-specific, relevant unit/contract/integration and regression baseline cases. No new skipped/xfail task tests.
- ruff.log PASS; mypy.log PASS /177 source files. Six changed Python files formatting checked after formatting the modified compatibility test.
- implementation.patch and digests.json scope exactly4 production files plus1 new and1 existing test; compare against task-start snapshots, not HEAD's prior work. Reverse apply dry check PASS, never applied to working tree.

## Acceptance / regression baseline

| Criterion / baseline | Result | Evidence |
|---|---|---|
| new candidate session retains prior goal/recent dialogue across three restarts | PASS | actual main4 startup/shutdown cycles; captured production request roles/raw input/order and journal readback |
| zero cross-session mixing | PASS | B has no A context; returning A excludes B goal; repository exact-session assertion |
| legacy assembled prompt not parsed | PASS | legacy path remains prompt-only; no-journal legacy marked legacy_unrestorable; old system canary excluded |
| upper bound / role preservation | PASS |9 completed runs → newest6 complete user/assistant pairs, exactly12 messages |
| provider/route/privacy metadata | PASS under synthetic tests | same privacy query, local/cloud exclusion; existing provider regression included in full gate |
| no historical tool replay | PASS | actual subprocess file effect once; marker removed, restarted new run does not recreate it; no historical tool_request copied |
| relevant unit/integration/regression baseline | PASS | full.log: conversation, session, provider adapters/retry, tools/batches, cancellation/terminal fences, recovery, legacy/config, body/audio synthetic fixtures |
| real provider / GUI / GPU / power loss / soak / deployed rollback | NOT VERIFIED | not run; no private data or live service restart |

## Known limitations / remaining issues

This is recent completed dialogue (at most12 messages), not complete historical tool transcript, token-budget enforcement, summarization or long-term memory ingress. Failed/cancelled/interrupted run goals/results remain readback-only, not hydrated; direct emotion/status commands retain non-journal behavior. Same-privacy history means changing from local to cloud does not carry local history. Historical failover provider labels remain unchanged per RT-009 fix. Journal retention/disk growth and single-owner assumption pre-exist; RT-011 budget and RT-014 memory are not implemented. UI sidebar history restoration is not part of this provider-context task. No performance improvement rate claimed.

## Rollback

For a drained subsequent startup set SIRO_SESSION_RESTORE_ENABLED=0 (candidate) or use legacy for new runs, preserving all DB data. Feature-off main4 cycles verify previous working path; no schema rollback necessary. implementation.patch reverse --check passes as scoped source rollback; actual deployment/drain rollback not run. Do not replay unresolved effects or restore old backups automatically.
