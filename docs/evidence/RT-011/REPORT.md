# RT-011 context budget slice — 2026-10-05

Status: **PARTIAL**. Implementation date2026-10-05; no full completion date claimed. Summary remains DEFER. Exactly RT-011 selected as first PLANNED task with fulfilled RT-002/010 dependencies and FIX gates; selection.json records all15 tasks.

## Intent / discrepancy / actual runtime

Roadmap requires context measurement and limits preserving immutable goal, authorization/source and pending tool pairs; architecture review explicitly SPLIT hard budget from deferred summary. Twelve messages do not bound a single tool output or active run history. Current runtime has no provider tokenizer/context-window metadata: logical request size is measurable without adding dependencies, while exact provider-token acceptance cannot be verified. Do not change units silently or claim this byte ceiling equals a context-window limit. Therefore task remains PARTIAL despite passing byte-guard tests.

Actual main composition: original selected provider → existing FailoverModel (candidate if enabled) → ContextBudgetModel outer guard → ConversationEngine/Integrated consumers. Guard measures compact UTF-8 JSON of all ModelRequest fields (prompt, native messages/arguments/results, tool descriptions/schema, privacy, output setting and generation ID). Limit default65536 bytes, startup SIRO_CONTEXT_MAX_BYTES;0 bypasses guard, negative/invalid integer fails startup, legacy ignores setting. The outer guard raises ContextBudgetExceeded before any provider invocation, so no retry/fallback can bypass it. name preserves selected provider provenance. Under-limit requests and token object pass unchanged. Existing Core exception boundary produces FAILED/error terminal and existing journal/readback consumer retains context.

## Files / scope

- src/siro/services/agent/context.py: new minimal LanguageModel wrapper, pure request byte measurement, explicit ContextBudgetExceeded.
- src/siro/services/presentation/gateway.py: candidate startup composition and frozen byte cap,8 added lines. This caller exceeds original expected files; necessary runtime wiring recorded D27.
- tests/integration/test_context_budget.py:8 tests combining production wrapper contracts and actual main/Core/SQLite/ASGI plus fake provider/executor.
- docs DECISIONS D27, CONTRACTS, STATUS, RUNTIME_EVOLUTION_ROADMAP and this evidence folder.

No Core refactor, model port/public API/protocol/config JSON/state/schema changes, no renamed/moved files, no new dependency. No affect/identity/relationship/body/audio/long-term memory modification. No summary/compression, no truncation or rewriting of pending pairs, no persistence format change or second journal. Logical representation includes fallback prompt even if adapter uses native messages; measured cap is neither exact serialized HTTP payload nor model token count.

## Tests / evidence

- before.log: same actual-main candidate64-byte cap case in temporary src with pre-task Gateway restored; request still reaches provider and fails expected FAILED terminal assertion. Imports trace to temporary pre-task main; expected exit1. No working-tree rollback.
- task.log:8 passed,3 dependency warnings,exit0. Exact UTF-8 request size; at cap passes,1 below rejects; Unicode/tool schemas/authorization/pending pair and request object identity unchanged; cancellation prevents call; invalid wrapper budget rejects; main feature-on/off/legacy and env freeze; durable selected backend preserved.
- giant tool fixture: initial request accepted, tool executes once and returns400000 characters; continuation rejected before second provider call, error ContextBudgetExceeded; complete goal/system/assistant-call/tool-result pairing and tool count remain in actual SQLite readback. Executor/provider synthetic; no claim of real external effects.
- measurements.json: standalone synthetic logical requests measured by production helper, byte counts only, no provider traffic; demonstrates huge individual result crossing cap.
- ruff.log PASS; mypy.log PASS /179 files; format.log PASS /3 files.
- full.log: **396 passed,5 opt-in skipped,3 dependency warnings,85.84s**,exit0. Includes all unit/contract/integration gates; skips are real provider/speech and not PASS.
- source digest and scoped implementation.patch compare against this task baseline; reverse apply dry check PASS, never applied. No private DB/key/audio accessed or live8000 restart.

## Acceptance criteria

| Criterion | Result | Evidence / limit |
|---|---|---|
| do not send over-limit request | PARTIAL | exact logical UTF-8 cap PASS before any selected provider/retry invocation; provider tokenizer/window enforcement NOT VERIFIED |
| goal / authorization / pending pairs preserved | PASS | pure unchanged input; exact boundary request identity and huge-result journal/readback assertions |
| summary does not write personality facts | PASS within slice | summary absent/deferred; no memory writer/import/change |
| relevant regression baseline | PASS | full.log: conversation, native tool batches, cancel/terminal fence, provider retry/metadata, session/recovery, legacy/config, body/audio synthetic fixtures |
| provider/GUI/GPU/power loss/soak/deployed rollback | NOT VERIFIED | not executed |

## Remaining issues / limitations

Required for full RT-011 budget completion: bind verified provider-specific tokenizer and input+reserved-output/context-window limits to selected model; test true token boundary and actual adapter payload behavior. A byte budget is useful bounded ingress but cannot substitute for that gate. Summary remains DEFER, not an implementation blocker for this authorized slice. Cap measures logical serialized size, not peak RSS, SDK framing, billing/cost or exact wire bytes. Measurement may allocate temporary encoding/asdict copies; not a streaming memory-limit claim. Large existing journals remain intact and disk retention debt is unchanged. Old completed session dialogue may exceed cap; fails explicitly rather than deleting history. Real provider and deployment validation remain external gates.

## Regression / rollback

Candidate feature-off0 and legacy retain existing model path. Existing retry/privacy/name/journal/terminal contracts must pass full gate. To rollback for subsequent drained startup set SIRO_CONTEXT_MAX_BYTES=0; preserve DB/current completed/unknown outcomes, do not replay effects. Scoped patch reverse dry check is source rollback evidence only; deployment drain/rollback not tested. No schema rollback required. Do not start RT-012 in this turn.


## Completion follow-up — 2026-10-05

The above PARTIAL report is retained as historical evidence. The native budget remainder is now completed; authorized budget slice DONE, summary DEFER. See [completion report](token-completion/REPORT.md), final logs and scoped rollback evidence. Its current acceptance and limitations supersede the historical missing-tokenizer statement.
