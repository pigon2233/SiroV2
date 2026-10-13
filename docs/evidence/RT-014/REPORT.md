# RT-014 source-backed memory ingress — 2026-10-05

Status: **DONE**. Completion date:2026-10-05.

## Selected Task / Why selected

All15 RT statuses/dependencies are recorded in selection.json. RT-001–012 are DONE; RT-013/015 remain DEFER. RT-014's old BLOCKED label names RT-010, which is DONE. This documentary blocker is stale, not a live dependency; select RT-014 only. F08 correctly identifies memory recall and mutation APIs exist but explicit chat ingress is absent. No RT-015 work.

## Reconstructed intent / Scope

An owner explicitly requests remembering a statement; retain its original source event, identity/person scope and existing revision machinery. Cross-restart lookup, correction and deletion must work without changing immutable persona, relationship calculations or storage policy. Existing memory APIs remain the correction/deletion mechanism, not fuzzy text or LLM-generated mutation decisions.

## Files changed / Runtime path

Five production files: core/memory.py (ingest_owner_request and optional recall filter argument), core/companion.py (candidate route filter passthrough), persistence/memory.py (optional source-privacy SQL filter), presentation/integrated.py (trusted user entry/commit context/error handling), presentation/gateway.py (startup flag).
New tests/integration/test_memory_ingress.py; D30/CONTRACTS/STATUS/roadmap/evidence updated. Six precise source/test paths, hashes and before snapshots are in digests.json/completion.patch. Preserve pre-existing dirty work; no migrations, dependency, mass moves or public protocol/state format changes.

Actual path: authenticated Gateway turn -> IntegratedCompanion creates/records UserTextEvent -> MemoryService.ingest_owner_request -> same MemoryRepository.add transaction/event/source/revision tables -> Core route-scoped recall -> model prompt. Browser/tool continuation never calls the ingress. Core startup establishes siro identity; trusted caller fixes owner scope. Source validation rejects non-presentation events. Full source text/session/time stays in the existing event table; evidence contains only synthetic fixtures.

## Implementation summary

Explicit leading 記住：/請記住：/幫我記住： (ASCII colon accepted) or remember:/please remember: commits an episodic owner statement. Other prose/quotes and empty statements are not silently guessed into facts. Exact statement preserved; UUID5 from source ID/identity supports repeated same-event lookup. Memory confidence describes a sourced user statement, not independent real-world verification; no SemanticFact/persona write.

Only after durable commit, existing verified context reports the memory ID/local-storage limitation to the model. Failure finishes run FAILED with the original error class before provider dispatch; empty command reports failure rather than fake success. Cancellation/terminal checks fence further commit dispatch and late output; a transaction that already committed is not falsely rolled back. Existing correct/delete APIs add revisions and remove invalid active recall.

Source user events remain local_only. Candidate cloud recall accepts only memories with all explicit cloud_allowed source events; missing sources fail closed. Local/API readback stays available. Main synthetic-cloud fixture verifies local remembered contents and local run history do not appear in cloud request. Additive filter defaults preserve old API/legacy behavior; feature0 disables future writes, not safety filtering or stored records.

## Tests run / Regression results

- Task and relevant memory/session/Core integration:27 PASS,3 dependency warnings,4.89s (task-verified.log).
- Includes actual main/ASGI/Core/SQLite source checks, four lifecycles for remember/restart/correct/restart/delete/restart, source/revision API, identity filtering and prompt consumption; real argv subprocess tool output injection; synthetic cloud transport/planner only, no external service.
- Idempotency/source-type rejection/prose/quotes/privacy, no unauthorized HTTP ingress, empty request and persistence failure no-provider-dispatch, legacy/candidate feature0 rollback are exercised.
- Initial two fixture failures: assertion checked legacy prompt instead of native user messages; synthetic UserTextEvent omitted required turn_id. After correction10 PASS (task.log). Expanded fixture first run had undefined cloud parameter (task-final.log); corrected27 PASS. Initial logs are retained, not overwritten into success.
- Pre-task source temporary main reproduction: before.log, expected missing memory FAIL; no default/private DB touched.
- Ruff/mypy/format and source reverse-patch dry check: final log evidence. Full regression:426 PASS,5 opt-in SKIP,3 dependency warnings,152.36s,exit0 (full.log). mypy184files,ruff and six-file format PASS.

## Acceptance criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| Designated synthetic user statement persists across restart | PASS | actual main remember/query, reopened memory ID and subsequent Core prompt |
| Correction/deletion take effect | PASS | existing HTTP revision2 then deletion/revision3; separate fresh-session prompts and reopened active query |
| Source retained | PASS | actual event envelope text/session/type, memory_sources, revision source IDs |
| Tool text never automatically becomes fact | PASS | actual computer.execute subprocess output reaches model as tool role; memory browse remains empty |

## Remaining issues / Architecture deviations

No required production blocker identified; full regression gate PASS. Grammar intentionally bounded to explicit leading markers; no broad natural-language extraction or fuzzy corrections. Retention is unchanged: deleting a memory prevents memory recall, not wholesale purging canonical conversation history. One owner deployment assumed; this does not introduce visitor identity/auth design. Cloud does not gain access to these locally classified memories. UI memory management continues through existing API; no new WS event or manual-GUI completion claim.

Necessary Core/repository/Gateway optional plumbing exceeds the original tentative file list; D30 records the source-privacy issue discovered on actual path, needed to prevent new ingress leaking across routes. No affect/relationship algorithm, immutable identity, memory schema or storage retention policy change. Models and body are synthetic; real provider/owner walkthrough/long-duration/power-loss/private deployment release gates are separate, not implied PASS.

## Rollback method

Drain candidate and set SIRO_MEMORY_INGRESS_ENABLED=0 for next startup to stop future chat writes. Existing memory/revisions/correct/delete APIs and safe candidate recall filter remain. Legacy preserves pre-task ingress behavior. Feature0/legacy isolated main fixtures verified, no private deployment change. Scoped completion.patch reverse dry check preserves earlier dirty work; validate hashes first, never broad reset or DB restore/deletion. Test-only memories may be withdrawn via the existing deletion/revision API.
