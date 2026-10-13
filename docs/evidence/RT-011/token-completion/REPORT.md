# RT-011 native budget completion — 2026-10-05

Status: **DONE for the authorized budget slice**. Summary remains **DEFER** under the existing architecture-review SPLIT. This supersedes the earlier PARTIAL result, whose report and failure logs are preserved.

## Selection and reconstructed intent

Continue RT-011, not RT-012: RT-002/010 dependencies and FIX gates are satisfied; its missing selected-model tokenizer/window gate was the remaining budget blocker. Preserve goal, authorization source, pending tool pairs and durable journal; reject rather than truncate. Affect, memory schema, Core/model ports, HTTP/WS/state formats and active service must not change.

## Actual runtime path and implementation

Candidate main captures the selected provider, then wraps FailoverModel with ContextBudgetModel. The independent byte guard remains. GPTOSSBudget measures the same OpenAICompatibleAdapter.request_payload used for dispatch, with the pinned official tokenizer and sandboxed chat template. Input reference tokens + requested output reserve + 256 safety tokens must fit the startup window. CPU counting runs in asyncio.to_thread, with cancellation checked before dispatch. No history mutation, summary, personality-fact write or fallback to guessed byte/token ratios occurs.

Supported native profile: Groq openai/gpt-oss-20b, official context window131072/output limit65536; the existing ModelRequest output ceiling32768 remains stricter. See [Groq specification](https://console.groq.com/docs/model/openai/gpt-oss-20b), [official pinned assets](https://huggingface.co/openai/gpt-oss-20b/tree/6cee5e81ee83917806bbde320786a8fb61efebee), [tokenizers API](https://huggingface.co/docs/tokenizers/api/tokenizer), and [chat-template API](https://huggingface.co/docs/transformers/main/chat_templating).

All five local assets are SHA256 checked. Unknown providers/models, missing or altered assets, reserved Harmony markers, late system messages and unsupported multiple-call template shapes fail explicitly before provider invocation. Offline retains the byte guard; legacy retains its old path. Startup configuration is immutable for each running composition. No runtime asset downloads.

Provision public assets using `uv run python scripts/setup_context_tokenizer.py`; fresh checkouts need this before native integration tests. Cache is gitignored. A packaged profile is included in the wheel; installations outside the checkout must configure SIRO_CONTEXT_TOKENIZER_DIR to the provisioned directory.

## Files changed

The exact16 implementation/config/test paths and source hashes are in digests.json; completion.patch is scoped to this continuation. Changes cover context.py, native_context.py, packaged gpt_oss_profile.json, OpenAI payload extraction, gateway composition, setup script, dependencies/lock, cache ignore, native tests and six existing synthetic main fixtures. Those fixtures explicitly disable native policy for their unsupported synthetic models; no assertions were removed and no skips added. Documentation updates: roadmap, CONTRACTS, DECISIONS D28, STATUS, this report and the historical report link.

## Tests and independent evidence

| Verification | Result | Evidence |
| --- | --- | --- |
| Task-specific byte/native cases | 23 PASS | task-final.log |
| Executor/lifecycle regressions | 34 PASS | executor-regression.log |
| Full relevant unit/integration regression | 411 PASS,5 opt-in SKIP,3 dependency warnings | full.log |
| Ruff / mypy / formatting | PASS; mypy181files | ruff.log,mypy.log,format.log |
| Independent official HF reference | Four counts match:68,89,167,30067 | reference.log,reference-counts.json |
| Actual Groq synthetic probes | HTTP success; reference/server79/83 and176/170, both covered by256 margin | real-provider.log,real-provider-counts.json |
| Wheel resource inclusion | PASS | build.log |
| Source hashes / scoped reverse patch dry check | PASS | digests.json,completion.patch |

Boundary -1/0/+1, output reservation, malformed/unsupported profile, asset integrity, startup settings, byte-off/native-on, cancellation during counting, actual main dispatch, SQLite readback and durable provider identity are exercised. Existing regressions cover tool effect count, pending pair preservation, errors, cancellation, retry, session isolation and profile compatibility.

Initial logs are retained: test harness attempted an output value already rejected by ModelRequest; reference harness misread a BatchEncoding mapping; real probe assumed a missing .env; three full-suite failures were synthetic-model fixtures without explicit native policy settings. Final runs above passed after scoped corrections. No failure log was erased.

## Acceptance criteria

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Do not send requests over the configured budget | PASS within supported reference-token policy | Native boundary and actual main tests; no provider calls on rejection; byte cap independently enforced |
| Preserve goal/authorization/pending pairs | PASS | Same payload builder; no truncation; native/tool and byte/SQLite regressions |
| Summary must not write personality facts | PASS for authorized slice | Summary is not implemented or invoked; memory schema unchanged; summary remains DEFER |

## Regression results and limits

Related automated text/tool, retry, cancellation, provider metadata/readback, session restore and legacy/candidate baselines PASS. The five opt-in real-provider/speech suite tests remain SKIPPED; two separately recorded Groq synthetic probes are not substitutes for all those tests. GUI, GPU, power loss, long soak and deployed rollback are NOT VERIFIED. Private DB and running8000 were untouched.

Official reference tokenization is exact for the pinned local template; Groq internal framing is not claimed identical. Two probes establish only observed +4/-6 differences covered by the256 margin, not a universal bound for future service changes. Unsupported shapes fail closed. Other models require a verified profile or an explicit operator override. No compression, disk-retention or peak-RSS guarantee is introduced.

## Architecture deviations and rollback

Necessary adapter serializer extraction, gateway wiring, explicit setup and tokenizer/template dependencies exceed the original tentative file list; D28 records this, without redesign or public format changes. Token guard is outside failover, so rejected requests never invoke fallback. Existing synthetic fixtures retain their prior test scope explicitly.

At a drained next startup set SIRO_CONTEXT_TOKEN_BUDGET_ENABLED=0 to disable native policy only; also SIRO_CONTEXT_MAX_BYTES=0 to restore the pre-budget dispatch path. No DB rollback or deletion. For source rollback use only completion.patch after checking source hashes and `git apply --reverse --check`; it reverts this continuation to the earlier byte-only PARTIAL state, preserving unrelated dirty work. Source reverse check is verified; actual deployment rollback is NOT VERIFIED. Do not apply a broad checkout reset.

Only RT-011 budget was completed; RT-012 and deferred summary were not started.
