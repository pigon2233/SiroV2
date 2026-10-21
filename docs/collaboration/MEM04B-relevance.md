# MEM04B: source relevance and attribute matching

Owner: Codex / current conversation; 2026-10-20 Asia/Taipei.
Status: LOCAL_VERIFIED_FOUNDATION / PARTIAL_PRODUCT / LOCAL_ONLY / NOT PUSHED.
Base: 64c2c24b52b8c0dcbed18e271765db1c0571f505.
Branch: codex/memory-relevance-20261020.
Reusing this conversation's clean managed worktree:
E:/coding/Worktrees/memory-hybrid-retrieval/SiroV2.

User requested implementation of remaining work. This subtask first addresses
MEM04 false recall and omissions; it does not claim all MEM02--06 complete.
Read STATUS, SOL_RUNBOOK, ACCEPTANCE, SECURITY_PRIVACY and collaboration rules.
Fetch succeeded; public GitHub open issues/pulls fully enumerated, both empty.
Original checkout clean at ea922ae79e6407048e0198968377c0374957b1ed; not modified.
Local claim is not an atomic/shared lock. No remote writes or deployments.

Owned paths: this document; docs/verification/MEM04B-relevance/;
src/siro/ports/memory_relevance.py;
src/siro/adapters/models/ollama_memory_relevance.py;
src/siro/core/memory_retrieval.py;
tests/integration/test_memory_relevance.py;
tests/unit/test_ollama_memory_relevance.py;
scripts/evaluate_memory_relevance.py;
tests/fixtures/memory_relevance.json.
Additional owned path (2026-10-21): src/siro/persistence/memory_vectors.py;
source-event category projection is necessary to avoid assuming every narrator
is the user. The authoritative envelope category is data, not verified identity.
Shared STATUS/DECISIONS/PLAN updates deferred to integration; task contract below
records the decision before implementation. Gateway/UI/runtime/private DB excluded.

## Contract before implementation

Optional source relevance filter, existing lexical/vector defaults unchanged.
When explicitly supplied, broaden candidate floor to 0.3 (at most eight) then
require local semantic selection. Must match requested subject, attribute and
qualifiers, include both conflicting source statements, and not infer missing
facts. Candidate source text is untrusted data; model output only selects source
indices with exact supporting quotes. It never rewrites memories, grants access,
records facts or authorizes actions. Core validates selections and rechecks source
hashes/revisions/privacy after the await; concurrent changes fail closed.

Use already-installed qwen3:4b-instruct, pinned digest
0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0.
No new models/packages. Loopback only, no redirect/proxy/cloud, bounded whole
inputs/output/context/time, structured schema and strict response validation.
Cancellation propagates; no hidden retries or degraded-success claims. Bounded
in-memory cache keyed by query and scoped source bindings/model/prompt version;
no raw text/response logging. Usage reports count classifier inputs and outputs,
not just final chat prompt savings. Cache is a performance optimization, not auth.

Official API checked: https://docs.ollama.com/capabilities/structured-outputs and
https://docs.ollama.com/api/chat. New System One API requires a newer daemon and
decision models, so is not adopted. No daemon update.

Acceptance: protocol failure/injection/scope/mutation/cancellation/cache tests;
rerun original fixed20+4 and holdout10+10 (now known development regression), plus
new fixed contrast cases frozen before first inference. Report semantic misses
and added token/latency; require >=18/20 source recall and zero unsupported-source
selection on the fixed absent-attribute/other-person/injection contrast cases
before claiming this filter ready. No end-to-end answer/permission/production claim.

2026-10-21 continuation: prior /tmp process/results disappeared after interruption;
no full first-run score is claimed. New evidence is persisted in this task's
directory. v1/v2/v3 protocol experiments are retained. v3 forces one keyed verdict
per candidate using dynamic schema; v4 additionally projects source event types
from the same source-bound SQLite read. First person may refer to the user only
for user-statement categories; assistant/tool/unclassified categories do not prove
user facts. This remains non-authoritative, with no new migration or memory writes.
The user's unrelated typo edit in the previous MEM04 report is preserved/excluded.

Cost decision (before final protocol): independent JSON pairs passed 31/32
contrasts and all 14 old absent-source questions, but cost about 4k classifier
input tokens per question. Next experiment uses the existing model as a one-token
yes/no classifier with a short policy. It emits no quote or rewritten memory:
indices select original repository bytes, retaining post-await source checks.
Budget-length termination after exactly one valid label completes this classifier
protocol, never a completed chat/tool action. Extra tokens, unknown labels,
malformed usage, tool calls, model/source changes and errors reject the operation.
All pair costs and failed unmeasured calls are counted. No new models/packages.

Final selection: the one-token v6 experiment scored 17/20 retrieval (below 18/20),
so it is rejected and only retained as evidence. Restore validated v5 independent
JSON pairs, not the cheaper failing protocol. v5: 19/20 development recall,
10/10 former holdout positives, all 14 absent-source queries empty, 31/32 contrast
sets (one conservative preference omission). Full product/answer readiness still
not claimed; measure v5 token overhead explicitly rather than claiming minimality.

Final boundary hardening: preflight every independent pair before any HTTP,
including policy bytes, 1024 framing reserve and 768 output reserve against the
16384 context. Reject the whole operation when oversized; never shorten sources.
The new regression failed before implementation and passes after it.
Final selected regression: 698 passed, zero failed/skipped, seven warnings;
source fingerprints stable during the run. Scoped Ruff/format and strict mypy
passed on seven files. See ../verification/MEM04B-relevance/REPORT.md for evidence,
limitations, repeat commands and integration handoff. Shared STATUS/DECISIONS
updates remain deferred to their owner. No live service, UI or private DB changed.
