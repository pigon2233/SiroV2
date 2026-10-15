# D58 / RT-005-FIX-02 — arguments-only cancellation budget reserve

Date: 2026-10-15 Asia/Taipei. Scoped final result: **PASS**. This evidence adds only `tests/integration/test_cancel_budget_reserve.py` and this evidence directory. The root agent performed the separate one-leaf production correction; this verifier did not edit production, original tests, shared documents or commits. The preceding eight-path D57 rollback evidence remains frozen.

## Confirmed boundary and controlled counterexample

The retained full-run trace fails the original `test_execution_lifecycle.py:799` total cancellation assertion at **5.090748416s**, against the unchanged **<5s** requirement. That failure occurs before recovery-readback or late-owner assertions. The actual full-run distribution of its extra delay between timeout scheduling and terminal persistence remains **UNKNOWN**; migration014 is not assigned that cause.

The original lifecycle source is byte-identical to public baseline `5c67c6f78f36833e526626b2d3481654bd823165`. Integrated, orchestrator, SQLite, journal, conversation, body and cancellation-token sources also matched that baseline during diagnosis. This direct-controller case never instantiates the main goal caller. A separate controlled temporary diagnosis passed the original case on baseline and D57, then demonstrated that a 300ms post-timeout delay fails the original bound on both sources. It identified four awaited operations after the old 4.75s cleanup timeout: proposal read, journal checkpoint, journal finish and final append.

The new arguments-only case uses the actual `IntegratedCompanion` → `ToolOrchestrator` → SQLite native run journal and a synthetic handler that suppresses its first cancellation until the fixture explicitly releases it. A fixture-local monkeypatch adds **0.5s** at the existing `finish_journal` boundary. It preserves the original **elapsed<5** assertion. The handler performs no OS command or external effect.

Pre-fix source gives **1 FAIL / 1 PASS / 2 existing warnings / 11.08s**. The arguments-only total reaches **5.262203922s** and fails only that bound. Before the timing assertion, actual failed-state/ExecutionCleanupError, typed journal/outcome_unknown, retained late-task ownership, late-result fencing, unchanged readback, one terminal event and eventual owner removal all pass. The original 4.75s wait leaves insufficient room for this measured caller bookkeeping. This is a deterministic budget counterexample, not a guessed localization of the full-run delay.

The companion positive case uses the actual contextual executor path. Its cooperative cleanup awaits **4.2s** after the existing context cancellation signal; the same terminal journal fixture adds 0.5s afterward. It must finish cleanup, clear active ownership, produce **CANCELLED** with the original reason, preserve conservative journal readback and emit one terminal within the unchanged <5s bound. It passes on the pre-fix source. Applying a 4.0s wait to contextual work would fail that behavior, so reducing the existing backend window is not an acceptable correction.

## Minimal production behavior and final results

The root changed only `ToolOrchestrator.cancel_run`'s wait selection: when all captured active tasks are arguments-only, wait 4.0s and leave 1.0s for the caller's terminal bookkeeping; otherwise keep 4.75s. Cancellation fencing, task ownership, shielding, callback removal and cleanup-error semantics remain unchanged. The lower process owner's 4.5s cleanup deadline, Integrated and both execution layers remain byte-identical to baseline. The contextual positive case verifies the retained window; no separate mixed-executor runtime demonstration is claimed here.

| Actual run in owned public source copy | Result |
| --- | --- |
| New cases, before correction | 1 FAIL / 1 PASS; 11.08s |
| New cases, final candidate | 2 PASS / 2 existing warnings; 10.29s |
| Entire unchanged lifecycle file, final candidate | 25 PASS / 3 existing warnings; 20.37s |
| Only corrected leaf reversed to baseline | 1 FAIL / 1 PASS; 11.07s; total 5.263391396s |
| Corrected leaf reapplied | 2 PASS / 2 existing warnings; 10.29s |

Final new-test mypy, Ruff lint and Ruff format checks return EXIT0. Evidence runner lint and format also return EXIT0. No original assertion, cancellation deadline, skip or full-suite gate was weakened.

## Exact leaf reverse/reapply and preservation

`cancel-budget-probe.py green` builds an owned archive from public baseline and overlays the frozen D57 source, the corrected orchestrator and the new test. It first runs the new two cases and all 25 unchanged lifecycle cases. It then produces a real one-file Git patch, checks/applies its reverse, verifies the orchestrator equals baseline bytes and that only this one protected source path changed, and reruns the new cases to obtain the actual timing RED. It checks/applies the patch again, verifies the exact final hash and reruns the two cases to PASS.

Baseline orchestrator SHA256: `6f9323fcd7846c6a0257c34afca82a342e4233101f488d9466ed561bb426fecd`.

Final orchestrator SHA256: `2451350a4c6884c00cc1a646cd6f869f98e750d8b7562550eb8933f98830f8f0`.

New test SHA256: `c2622ab1341282f6b3c42c642a4763e2ad1d962966f2a26ae0c5fbd9b83ea251`.

Raw leaf patch SHA256: `d939a1486f86a91e7247799b79405294abd88f28fb77dfb2f8224fe5a4a71f35`.

Original lifecycle test SHA256 remains `5671db4f6dc7b4eacf45393c44b999e273d8df238e641b0a4bd4ef54a66edf61`.

All 16 guarded source/test paths match their before-run bytes in the workspace and final owned copy. Integrated, service execution, adapter process execution, journal, conversation and the old lifecycle test are baseline-identical throughout. Both source phases preserve conservative journal results and late-task ownership; no actual source or database rollback takes place. This leaf proof does not replace the separate D57 schema14/data preservation receipt or approve an operational rollback.

The pre-fix child and all eight final verification subprocesses are joined. Their owned temporary source/database/pytest roots `/tmp/g58budget-m10r28gq` and `/tmp/g58budget-0oe_6_s9` are removed. The fixture releases and joins the late arguments handler; contextual cleanup finishes before terminal. No private tree, live8026, private database/configuration/chat/audio/key/model, GPU, provider, device or deployment is accessed.

## Reproduction and remaining limits

Run `.venv/bin/python -B docs/evidence/T19-goal-loop-2026-10-14/cancel-budget/cancel-budget-probe.py green` from the public repository. This runs the final new/old tests and performs the reverse/RED/reapply/PASS sequence solely in its owned public-source copy. `red-result.json` retains the actual pre-fix run; `green-result.json` records final source guards, commands, exit codes, cleanup and the one-leaf patch identity. Raw pytest/Git logs and patch remain as generated.

The 0.5s journal delay and 4.2s contextual cleanup are explicit controlled fixtures, not measurements of a general filesystem, arbitrary handler cancellation or universal 5s SLA. The original full failure is retained as FAIL; its actual extra-delay location remains UNKNOWN. Complete regression, schema acceptance, secret scanning, product quality and remote exact-commit acceptance retain their separate gates.
