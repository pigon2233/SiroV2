# AR-06 / AR-07 repair and DEFER gate review

Date: 2026-10-06. Local defects repaired; deferred features remain DEFER. No deployment, private DB migration, provider request or live-service restart. Existing unrelated dirty changes preserved.

## Intent and implementation

AR-06: official pinned Harmony reference template supports one call per assistant message. Rejecting every multi-call message broke legitimate Core continuation after effects executed. Production GPTOSSBudget now makes a private counting view of each uniquely identified completed call/result pair, retaining assistant content once. It adds the full serialized batch token count as local conservative reserve. Provider payload and Core/journal/executor order stay unchanged. Incomplete pairing rejects; over-budget stops before next request and never replays effects. Single-call boundaries unchanged. This is local configured policy, not proof of Groq framing's universal upper bound. Increased reserve can conservatively reject some otherwise admissible large batches.

AR-07: scripts/check now runs the existing public pinned-revision/hash-checked setup after uv sync and before pytest. CI already invokes scripts/check. Runtime does not download assets or disable tests. Empty /tmp cache download and actual GPTOSSBudget asset validation passed. Remote CI and an entire fresh checkout/check run were not executed.

## Changed files

Production: src/siro/services/agent/native_context.py; scripts/check. Tests: tests/integration/test_native_context_budget.py (four cases). Docs: DECISIONS D31, CONTRACTS, STATUS, runtime-evolution roadmap and DEFERRED_TASK_PLAN. Evidence: this directory. No provider wire/API/config/state format/schema change; no Core rewrite.

## Evidence and results

- before-after.log: same valid two-call request before ContextBudgetUnavailable, after count=233. Before snapshot and exact scoped repair.patch preserved.
- task-verified.log: pytest tests/integration/test_native_context_budget.py, 19 passed. Actual main/Gateway/Core/SQLite, real isolated Python subprocess effects: normal continuation sends two provider requests and each tool once; oversized observation stops after first provider request with both effects executed exactly once. Model transport is synthetic, not real cloud. Wire two-call payload unchanged; both arguments/results counted; exact boundary and cancellation/error/rollback fixtures preserved.
- full-suite.log: pytest -q, 430 passed, 5 opt-in real-provider skipped, 3 dependency deprecation warnings, 182.19s. No failures observed. Skips are NOT VERIFIED.
- deferred-baseline.log: runtime client/boundary, consolidation and proactivity, 9 passed.
- ruff-final.log: ruff check src tests scripts PASS. mypy-final.log: 184 source files PASS. changed-format.log: changed Python files PASS. schema-check.log and bash -n scripts/check PASS.
- clean-assets.log: public download into initially empty isolated directory, pinned hashes/production loader PASS. clean-native.log: 19 passed, 3 warnings (35.05s); copied native suite with counter ASSETS pointed at that fresh download; actual-main fixtures still use existing project assets, so this is not a whole-checkout CI claim.
- repository-format.log / repository-lint.log: whole-tree format/lint FAIL (26 files, 129 findings), including historical evidence scripts/local downloaded model README. product-format.log also exposes two pre-existing unrelated test formatting issues (test_gateway.py, test_audio_pipeline.py). These were not fixed or hidden by exclusions. Entire scripts/check/remote CI gate is not marked PASS.
- Initial test fixture failures: invalid stream constructor kwarg and iterable typing were corrected in new test code; initial logs preserved. Concurrent initial runs overlapped one task-final.log; task-verified.log is the separately executed authoritative final result.

## DEFER decision

RT-013: no matching production scoped filesystem.read/list caller in model catalog/dispatch; generic computer.execute argv is not semantic parity. No proven benefit: DEFER.
RT-015: deferred_probe.py measured completed retained=100, active=0, close retained=0. This demonstrates cleanup by close but not bounded ongoing retention. Pump single-owner, foreground priority and seven-day/restart gates unproven: DEFER.
RT-011 summary: six synthetic dialogue pairs reference input=6736 fit default profile; this is not proof of need, nor universal workload sufficiency. Source-version/revocation and quality benefit gate incomplete: DEFER.

No new deferred feature implemented. Local AR-06 defect and AR-07 missing provisioning are repaired; broader rollout/clean CI validation and individual deferred gates are distinct.

## Rollback

repair.patch covers only the three source/test files with before snapshots and source-digests.json. Reverse patch dry-run in isolated copy passed (rollback-dry-run.log). To revert this repair after draining owned runs, reverse only this patch against matching source digests; preserve unrelated changes and durable journals. No migration or replay. Reversion restores the known multi-call rejection and missing test provisioning. Existing startup native-budget disable switch remains available but weakens the native guard; byte guard is separate. No deployment rollback was performed.

## Unverified

Real cloud framing/provider, owner GUI, long soak, deployed rollback and remote CI. No claim that local reference allowance guarantees every server serialization. Independent post-repair verification still recommended.
