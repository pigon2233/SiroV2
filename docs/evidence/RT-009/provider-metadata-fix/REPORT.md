# RT-009 provider metadata repair — 2026-10-05

Selected task: RT-009 only. The latest DONE task failed independent compatibility verification; RT-010 was not started.

## Intent and root cause

Retry wrapper main composition replaced the selected adapter object. Integrated.respond still correctly uses model.name at run creation, SQLiteAgentRunRepository.start commits it to run_journal.backend, and readback returns the same value. FailoverModel.name was a fixed policy label, so wrapping indirectly erased selected-provider provenance. Independent test reproduced expected synthetic-cloud vs actual failover.

## Repair / scope

Only production change: src/siro/adapters/models/failover.py captures primary selected provider name at construction. Existing main, Integrated caller, repository and consumer require no changes. Name does not mutate after retry/fallback; selected-primary metadata is not an attempt execution trace. The two-attempt cap, emission fence, cloud request policy, cancellation and provider priority are unchanged. No API/protocol/config/state/schema change or architecture deviation. D25 records this decision.

Tests changed: tests/integration/test_provider_retry.py asserts authenticated API readback, raw SQLite row, and fresh SQLiteStore/repository readback after main lifecycle shutdown. Local/cloud and retry enabled/disabled are covered, including errors and successful tool effect. Additional cloud feature-off case and contract name-after-fallback test prevent wrapper/attempt identity confusion. Providers are synthetic; main/Core/SQLite/ASGI and successful Python subprocess are real.

## Reproduction and evidence

- Original independent verification test rerun before repair: FAIL, backend failover.
- before.log: expanded standard suite before production repair: 6 failed / 3 passed. All six enabled candidate cases fail provider metadata assertion; legacy/feature-off pass.
- task.log: repaired contract/main suite plus unchanged independent test: 35 passed, 3 dependency warnings, no skips/xfail.
- ruff.log: PASS. mypy.log: PASS, 176 source files.
- full.log: **378 passed, 5 opt-in skipped, 3 dependency warnings, 99.85s**, exit0. Includes relevant unit/contract/integration, journal recovery, cancellation, terminal fence, tools, legacy/config and body/audio synthetic baseline tests. Skips are real model/speech opt-ins, not PASS.
- repair.patch compares this repair only against before snapshots, not repository HEAD; digests.json records source/test before/after. git apply --reverse --check passed without modifying files.

## Acceptance / regression

Original criteria (at most two attempts, no fallback after emission, no unconfigured cloud egress) PASS in task suite. Selected-provider durable metadata and reopened readback PASS for tested local/cloud enabled/disabled paths. Relevant unit/contract/integration and regression baseline PASS under the stated synthetic/local test limits. Final repair status: DONE; original independent failure report remains historical evidence.

## Limits / remaining issues

Historical rows already written as failover remain unchanged: no reliable provider evidence exists to infer them safely. No private DB migration, user service restart, real provider call, GUI, GPU, power-loss, soak or deployed rollback validation. These remain NOT VERIFIED. Optional protocol-error classification expansion is outside this repair.

## Rollback

Prefer SIRO_MODEL_RETRY_ENABLED=0 at a subsequent drained startup to bypass retry wrapper without reintroducing this metadata bug. repair.patch reverse application is a scoped code rollback, verified only by dry check; it reintroduces the bug when wrapping is enabled. Preserve journal data; no schema rollback or replay. User port8000 service not restarted.
