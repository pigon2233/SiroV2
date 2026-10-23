# MEM04 — local hybrid memory retrieval

Owner: Codex, current conversation; 2026-10-20 Asia/Taipei.
Status: IMPLEMENTED_FOUNDATION / PARTIAL_PRODUCT_VALIDATION / LOCAL_ONLY / NOT PUSHED.
Base: 012dce8cb0c844b6ebbc4395c3b38591694b07ce.
Branch: codex/memory-hybrid-retrieval-20261020.
Worktree: E:/coding/Worktrees/memory-hybrid-retrieval/SiroV2.

User requested implementation after discussing vector memory/token use. This
explicitly extends the earlier plan's lexical-only phase. GitHub fetch and open
issue/PR read-only checks succeeded (no open entries); local claim is not a lock.
Original checkout belongs to other work; it is not modified. This task continues
this conversation's Memory/Core ownership, excluding Gateway, UI, audio, renderer,
service configuration, private databases and deployment. Shared STATUS, PLAN and
DECISIONS updates are deferred to integration; the contract decision is below.

Owned paths: this document; docs/verification/MEM04-*;
src/siro/ports/embeddings.py; src/siro/adapters/models/ollama_embeddings.py;
src/siro/core/memory_retrieval.py; src/siro/core/memory.py;
src/siro/core/companion.py; src/siro/persistence/memory_vectors.py;
src/siro/persistence/memory.py; src/siro/persistence/migrations/018*;
tests/integration/test_memory_vectors.py; tests/unit/test_ollama_embeddings.py;
tests/integration/test_memory_derivation_bindings.py;
tests/integration/test_memory_review.py; scripts/evaluate_memory_retrieval.py.

## Contract / decision (before implementation)

Opt-in injected retriever; default lexical behavior and live chat configuration
stay unchanged. SQLite remains authoritative; vectors never authorize or prove
facts. Filter identity/person, committed status, time, privacy, revocation and
derivation before embedding. Bind cached vectors to full source hash/revision,
embedding digest, dimensions and format version. Revalidate on cache write and
before context dispatch. Correction/delete/revocation removes cached vectors in
the same transaction. Additive schema 18; older incompatible release must refuse
the database. No private database is opened or migrated here.

Only literal loopback Ollama, no redirects/environment proxies, no new Python
dependencies. Downloaded qwen3-embedding:0.6b (639150858 bytes), digest
ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d,
into existing E-hosted WSL Ollama after read-only dependency/disk inventory.
Chat model stays qwen3:4b-instruct. Model and API references:
https://docs.ollama.com/api/embed and
https://huggingface.co/Qwen/Qwen3-Embedding-0.6B (Apache-2.0).

Bound corpus and batch sizes; exact cosine plus reciprocal-rank fusion; retain
distinct conflicting records and source packets. No fake vectors counted as
semantic quality. Fail explicitly on model/cache/source/cap errors; do not claim
successful dense retrieval when degraded. Whole-memory packet byte budget counts
provenance; bytes are not measured tokenizer tokens. Current user message,
native dialogue and pending tools are never shortened by this budget.

Acceptance: real local synthetic semantic recall comparison, persistent cache
reuse, digest isolation, invalid vectors/failures, privacy/scope/TTL and source
mutation races, transactional invalidation, bounded context, schema upgrade and
relevant Memory/context/review regressions. Record actual counts and failures.
No production enablement or overall memory completion claim.

## Handoff

Implementation and evidence: [MEM04 report](../verification/MEM04-hybrid-retrieval/REPORT.md).
631 selected regressions passed with stable before/after source fingerprint;
40 new tests included. Real local development retrieval 19/20 top-5; small
holdout 9/10 positives and 9/10 absent-source exclusions. The remaining attribute
false positive blocks a claim of general readiness. Shared-file updates remain
deferred; final delivery message supplies full local commit SHA.
