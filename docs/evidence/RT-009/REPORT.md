# RT-009 completion report

Date: 2026-10-05 Asia/Taipei. Status: DONE for scoped measured criteria; not candidate promotion or a release.

## Selected Task
RT-009 — provider bounded retry/fallback.

## Why this task was selected
Read the entire RT task status/dependency list, five requested runtime-evolution documents, applicable AGENTS/STATUS/SOL_RUNBOOK, review/register and FIX-001 evidence. RT-001–008 DONE; RT-009 first executable PLANNED, dependencies RT-007/008 DONE, FIX-001 gate DONE. The other FIXes also DONE, RT-013/015 remain DEFER and other dependency gates unchanged. selection.json preserves selection snapshot. Only this task implemented; no RT-010 or deferred work.

## Original intent and actual path
F07: existing FailoverModel was not wired to main, loop could visit every backend, any exception triggered fallback, and emission counted only nonempty text. Main selected Ollama first, configured cloud second, otherwise offline; it had no cost-budget configuration. Existing FIX-001 correctly rejects failed/cancelled generation tool batches and must remain.

Production path now: candidate main chooses the same single provider with the same env priority/privacy → FailoverModel → existing adapter/HTTP transport → ConversationEngine → Core/Integrated accepted-generation gate → existing tool orchestrator/journal/observation. Legacy main bypasses wrapper. No routing abstraction or extra backend composition. Gateway captures SIRO_MODEL_RETRY_ENABLED=0|1 at startup (default candidate on); later env changes cannot change a running policy. 0 disables only this wrapper on next startup, preserving other candidate FIXes/journal.

## Files changed
Production (three):
- src/siro/adapters/models/failover.py
- src/siro/adapters/models/openai_compatible.py
- src/siro/services/presentation/gateway.py
Tests (two):
- tests/contract/test_failover_policy.py
- tests/integration/test_provider_retry.py
Docs: DECISIONS D24, CONTRACTS, STATUS, RUNTIME_EVOLUTION_ROADMAP and docs/evidence/RT-009.
Precise incremental implementation.patch and before/source digests distinguish this card from the pre-existing dirty tree. No migration, database/state format, provider port/ModelRequest field, dependency, identity/memory/affect/body/voice asset, Rust/device/executor/journal change. No private DB, key or running user service read/mutation; all tests use synthetic inputs and isolated data.

## Implementation summary
Two total invocations per generation, including initial plus either same-provider retry or second supplied backend. Never a separate retry tier per backend; third backend is not visited. Retryable: ConnectionError/TimeoutError/httpx.TransportError and HTTP429/502/503/504, only before emission. Nonempty text, any tool_request (even malformed empty intent) and finished fence every later attempt. Protocol/validation/permission and other statuses propagate without retry. Backoff defaults 0.25s, constructor bounded to 0–5s, token cancellation interrupts wait; task cancellation propagates. Original prompt/native messages/privacy/output budget stay identical, only retry's private generation ID changes. Global ConversationEngine deadline is unchanged and still spans generation/attempts.

Cloud policy: actual OpenAICompatibleAdapter recognized plus explicit cloud indices for injected/custom providers. Every cloud invocation requires cloud_allowed; primary authorized cloud request is existing behavior. Any extra cloud request requires explicit additional-cloud-request budget (0 or 1); default 0. Main does not have configured monetary budget, so extra cloud attempts are denied, even when cloud key/model exist next to selected Ollama. There is no new cloud fallback route. Direct callers can explicitly budget one additional cloud request; this is a request-count ceiling, not a USD/daily spending guarantee. Cost-priced/daily budget integration is not silently invented.

OpenAI SSE buffers tool fragments before yielding ToolCall. A transport/parser failure after a buffered fragment is marked using a private standard exception note, making retry unsafe while preserving the original exception class/legacy error code. This necessary adapter scope addition was documented in D24 before final implementation. No changes to chunk/message port or successful stream serialization. FIX-001 dispatch gate and all prior FIX implementations left untouched.

## Tests run
| Gate | Result | Evidence / actual layer |
| --- | --- | --- |
| New policy + actual main assembly tests | 32 passed, 3 dependency warnings, exit 0 | task-verified.log; 24 policy cases + 8 main cases |
| Existing model adapter contracts + initial policy set | 30 passed, exit 0 | task-initial.log; before real HTTP cases were added |
| Relevant integration/contract regression | 153 passed, 3 warnings, exit 0 | related-verified.log; model/Integrated/native batch/journal/Gateway/cancel/main/catalog; before final exception-class-preserving adjustment, covered again in final full suite |
| Final full suite | 376 passed, 5 skipped, 3 warnings, 81.02s, exit 0 | full-suite.log; final startup-freeze test included |
| Ruff / mypy / format | PASS / 176 files PASS / five changed Python files formatted | ruff-final.log, mypy-final.log, format.log |
| Scope rollback dry check | PASS, exit 0 | git apply --check --reverse docs/evidence/RT-009/implementation.patch; rollback-check.log; no reverse applied |

A related-suite invocation first used nonexistent tests/test_conversation.py and exited4 with no tests (related.log); corrected actual integration selection and final full suite includes tests/integration/test_conversation.py. Historical lint/iteration logs retained and not called passes.

Policy cases cover two-attempt cap including three failing supplied backends, same backend, immutable request/new ID, retriable errors, permanent errors, text/tool/finished emission, local_only/cloud_allowed/request budget, token/task/pre-cancel and buffered SSE fragments. Main cases use actual main construction, Core/controller/SQLite/ASGI and a real Python file-write subprocess for successful tool closure; model adapters are synthetic. Includes successful retry→tool→paired observation→final, two failures, legacy single request, feature off, startup env flip, partial text/tool failure, continuation intent failure with retained previous observation, and primary cloud429 without extra budget.

Real HTTP fixture: local asyncio server + actual Ollama/OpenAI adapter and HttpxStreamingTransport. Ollama429 retries once then parses successful response; OpenAI tool fragment + premature HTTP EOF raises original RemoteProtocolError without fallback. This verifies real network/HTTP code against synthetic responses, not a real model provider. No GUI/GPU/paid provider calls implied.

## Regression results
PASS: selected-provider/env priority, legacy and feature-off behavior, raw/native prompt/message compatibility, previous FIX-001 failed-generation gate (initial/continuation), tool pairing and budget behavior, cancellation, session/ownership, full existing schema/tool/body/audio fixtures. Full suite retains 100 race/fence and prior FIX tests.
NOT VERIFIED: five opt-in external model/speech provider tests; actual selected provider tool loop, GUI/GPU this card, 24h soak, deployment rollback. No claim that G1–G3 release/promotion gates are now satisfied. No current port8000 deployment/restart.

## Acceptance criteria
| Criterion | Verdict | Evidence |
| --- | --- | --- |
| At most two attempts including initial | PASS | Same-backend and three-backend tests; actual main failing local makes two; success-tool continuation is separate generation and journal round |
| Zero fallback/retry after emission | PASS | Text/tool/finished and buffered fragment tests, actual HTTP premature EOF; actual initial/continuation main failed intent makes zero new effects and no replacement round |
| No unconfigured cloud egress | PASS | local_only + explicit budget gate tests; main with both local/cloud config never constructs cloud fallback; selected primary cloud429 sends exactly its original one authorized request, no extra |

## Remaining issues / known limitations
Cloud request budget is not price/token/daily accounting; production therefore allows zero additional cloud requests until a real budget integration is defined. Main uses retry on its selected local backend, not an automatically added alternative provider. Explicit cloud metadata remains caller responsibility for custom providers; real OpenAI adapter is automatically identified. Backoff is fixed and does not honor Retry-After/jitter; bounded attempts still apply. Retry after no local emission cannot prove provider did no internal inference/billing; this policy protects visible generation/tool intents and avoids unbudgeted extra cloud calls. SDK HTTP timeouts still obey existing overall ConversationEngine deadline. Unknown external effects remain journal/readback responsibility, never retried here.
AR-04 retention, AR-05 single-owner technical debt, session hydration/context budget/deferred Rust/scheduler remain separate. JSON SiroSettings and Gateway env are still separate. No new real-world provider/GUI/rollback measurements.

## Architecture deviations
No redesign. Required additional file beyond roadmap's two expected modules is OpenAI adapter, to fence tool intent buffered below the port while preserving error type. D24 records this discrepancy; not expanding into provider port redesign. Retry/fallback combined into one existing model wrapper/policy. No cost-priced routing/default cloud promotion.

## Rollback method
Drain the active generation, set SIRO_MODEL_RETRY_ENABLED=0 and restart the same compatible candidate binary for new runs; existing single provider remains with prior fixes/journal/ownership. Existing legacy profile also bypasses wrapper but changes other runtime features, so per-wrapper off is narrower. Both profiles and feature-off are exercised via main. For source reversal use only scoped patch after checking digests; retain prior FIXes, migration/readers and unknown fencing, never reset the dirty tree. Reverse applicability checked; actual deployed mid-work rollback NOT VERIFIED.
