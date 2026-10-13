# RT-008 — durable journal and read-only recovery

Date: 2026-10-03 (Asia/Taipei). Result: DONE for the task's measured acceptance; not a product release or automatic resume claim.

## Selected Task / Why this task was selected
Read all RT task status/dependencies and the five runtime-evolution documents. RT-001–007 were DONE; RT-008 was first PLANNED and RT-003/005/007 dependencies were satisfied. Selection preserved in selection.json. No RT-009 implementation.

## Reconstructed intent / current implementation / callers and callees
F04 identifies persisted AgentRun/AgentStep without reconstructable native messages or restart behavior. Before this card, Integrated held tool batch/results/message history and model-round counter in RAM; append step budget counted ledger events, not model requests. Automatic and HTTP-approved tools both enter ToolOrchestrator.execute, so dispatch journaling must cover that common boundary.

Candidate Gateway main → lifespan controller.startup → _ensure_core → migrations + repo.reconcile before traffic. Lazy initialization shares this path for injected controllers. start atomically inserts agent_runs + versioned run_journal; journal epoch equals run ExecutionContext epoch (run_id), records startup candidate profile, selected model backend name, privacy and independent budgets. Executor binding remains the existing startup profile binding from RT-004; this card does not implement multi-backend recovery or Rust.

CompanionCore optional on_messages_ready callback commits assembled canonical context before a provider request; old callers remain valid and Core still has no concrete persistence/UI/execution dependency. Model response's accepted assistant batch is checkpointed with ordered unique call rows before proposal/approval. reserve_round happens before every candidate generation. Journal event hook in common execute commits dispatch intent before handler and commits observations before proposal completion/UI delivery. Manual denial and each batch callback commit independently, so partial batches survive. Existing batch completion still controls the next model round.

Restart reconciliation never invokes executor/provider. It fences persisted pending/approved/running proposals (including proposal insert→bind gap), marks old interrupted AgentRun FAILED with existing error fields, retains already committed results, and fills missing pairs with outcome_unknown or not_dispatched. Even RUNNING-without-intent is conservative unknown. Local readback does not prove remote/OS effects and cannot silently rebind or resume recovered runs. A persistent journal-owner guard prevents old candidate approvals from executing without live matching context/hook, including current legacy runtime.

Authenticated GET /v1/agent-runs/{session_id} returns goal, profile/version/backend/privacy/epoch, counts/limit, canonical paired messages and call ledger. Browser boot reads its existing browser session and displays an interrupted/unknown notice. Old rows without journal remain legacy_unrestorable; old assembled prompts are not parsed into native messages. New run/session restoration is RT-010, not implemented here.

## Files changed
Production: src/siro/services/agent/runs.py; new src/siro/persistence/migrations/013_run_journal.sql; src/siro/services/presentation/integrated.py; src/siro/services/tools/orchestrator.py; src/siro/core/companion.py; src/siro/services/presentation/gateway.py; src/siro/services/presentation/static/index.html.
Tests: new tests/integration/test_run_journal.py and tests/fixtures/run_journal_crash.py; tests/integration/test_operational_cli.py isolates env/data for its existing launcher test.
Docs: DECISIONS D20, CONTRACTS, STATUS, RUNTIME_EVOLUTION_ROADMAP and this evidence directory.
Before/source digests and implementation.patch isolate this card from the pre-existing dirty tree. No commit/push, mass moves/renames, dependency additions, old migrations/enums, Rust protocol, config format, identity/affect/memory algorithm, Live2D or voice asset changes.

## Tests run / Regression results
| Gate | Result | Evidence / layer |
| --- | --- | --- |
| Final full suite | 285 passed, 5 skipped, 3 dependency warnings; 54.22s, exit 0 | full-suite-verified.log; unit/contract/integration, not all real providers |
| Final dedicated cases + failed launcher regression | 13 passed; exit 0 | task-final.log; 12 RT-008 cases plus existing launcher case |
| Related suites before final small adjustments | 92 passed; exit 0 | related.log; run/batch/tools/Gateway/native context/cancel/session/schema |
| Ruff / mypy / format | PASS / 174 files PASS / 8 files formatted | ruff.log, mypy.log, format.log |
| Actual installed Gateway startup recovery over HTTP | PASS; unknown and budgets/pairs visible, effect file unchanged, recovery UI served, shutdown complete log | main_smoke.py + main-smoke-final.log; temporary data/offline backend, no provider call |
| Reverse patch check | PASS, exit 0 | git apply --check --reverse docs/evidence/RT-008/implementation.patch; rollback-check.log; no reverse actually applied |

Crash fixture uses real child process os._exit(42) at before/after dispatch and before/after observation commit through actual Core/SQLite/controller/orchestrator. Handler appends and fsyncs a synthetic external file. Restart uses a model/handler that raise if invoked; file is unchanged, pairing and budgets survive, repeat startup is idempotent. Provider is synthetic; this does not test real provider/network or machine power failure. Partial batch/duplicate callback/conflicting observation, queued old approval, step limit after reopen, finish→AgentRun final crash window, session isolation, HTTP auth/manual approval and actual frontend notice function (Node) are covered. Upgrade 0/10/12→13, idempotence/integrity and prior migration loader/old table reader are covered. Existing full suite exercises legacy/candidate text/tools/terminal fence, cancel races and audio/body fixtures.

Five skipped cases are opt-in real model/speech providers; NOT VERIFIED rather than PASS. Real GUI/Live2D/audio/GPU this card, 24h soak, power-loss durability, deployed rollback and external side-effect reconciliation: NOT VERIFIED. The actual UI notice function is tested and page served, but no live browser rendering claim. Existing port 8000 service was not restarted.

## Acceptance criteria
| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Zero blind resend | PASS | Four abrupt process crash cases + actual main startup; forbidden recovery executor/provider; side-effect file unchanged; persisted approval fenced in candidate/current legacy |
| Unknown visible | PASS | Dispatch-without-observation recovers outcome_unknown in AgentRun error and paired observation; authenticated real HTTP readback; actual UI recoveryNotice function returns truthful warning |
| All tool pairs and budgets recoverable | PASS | Partial batch committed result retained and missing result explicit; ordered call IDs pair exactly; canonical system/user/assistant/tool history restored; rounds/tool count/max persisted, budget cannot reset on reopen |

## Issues discovered and resolved / discrepancies
Scope needed small caller additions beyond roadmap's expected files: optional Core message-ready callback for the real pre-provider context checkpoint, orchestrator hook for HTTP approval, Gateway startup/readback and minimal UI notice. D20/CONTRACTS document the added boundaries; no architecture redesign.

A real regression gate failed deterministically (full-suite-final.log: 1 failed/284 passed; operational-rerun.log also failed). Existing operational test used default .siro-data rather than isolated data; its earlier run applied draft 013 there. A later draft SQL change triggered applied-migration checksum protection before logging configuration. Restored the exact initially applied 013, verified checksum/integrity read-only, never edited DB checksum or dropped data. Isolated that test's env/data so future runs cannot mutate private runtime data. launcher-diagnosis.json records the cause. The unintended default DB additive schema change remains; it is not silently undone. No before-change private DB backup was taken by that old test; no private conversation/secret rows were copied to evidence. Final clean gates above passed. Historical logs retained, not rewritten as passes.

## Remaining issues / known limitations
Read-only recovery means local durable context + explicit uncertainty, not autonomous resumption or OS readback implementation. No external action exactly-once guarantee, no process-name scan or adoption of escaped/orphan processes, no new authorization grants. Single Gateway writer assumption; simultaneous independent owners are not coordinated. WAL synchronous policy is unchanged; process-exit tests do not establish power-loss guarantees. Legacy records remain unrestorable. Journal counters are model-round and tool-call counts; no new token/cost/elapsed budget policy. Epoch/profile/backend metadata are fixed at run startup, not a mechanism to live-switch or relocate backends. JSON SiroSettings/Gateway env separation remains RT-007's documented limitation.

## Architecture deviations
Necessary optional callbacks/wrappers only. Recovery deliberately uses existing FAILED/error instead of adding incompatible public state enums. No automatic resume API; unknown requires actual effect readback or owner confirmation. Task completion does not satisfy all G1–G3 release/manual/soak gates.

## Rollback method
Drain active candidate work, retain/fence uncertain actions and journal, then restart current compatible binary with SIRO_RUNTIME_PROFILE=legacy. Keep migration 013/readback/ownership guard, never downgrade/delete journal or let legacy resume candidate mid-run. Old loader/table compatibility was tested on synthetic schema; actual deployed rollback NOT VERIFIED. Scoped implementation.patch reverse applicability is checked for source recovery only, not permission to remove the installed schema or reset unrelated changes. Backup restore is not automatic and would need preserving newer data first.
