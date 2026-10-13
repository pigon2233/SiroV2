# Runtime product delivery — 2026-10-06

Owner instruction: implement RT-013, RT-015 and RT-011 summary, superseding earlier DEFER. Preserve all existing working-tree changes and RT history. D31 defines the bounded implementation. No live private service, private DB, credentials, model assets, identity/scoring, Rust wire or schema was modified.

## Delivered behavior

- **RT-013 DONE:** candidate filesystem.read/list and authenticated owner control-panel reads use the same owned Rust workspace service. Dedicated default workspace; exact signed argument/path grants after trusted authorization, tools kill switch, no failure fallback. UTF-8 reads <=8 KiB, Unicode path hashing matches Rust JSON encoding. Missing binary reports unavailable without blocking conversation. Startup/shutdown own the unprivileged process and private socket/ledger. Existing broad computer.execute permissions remain separate.
- **RT-015 DONE:** one lifespan-owned local digest groups exact duplicate committed owner episodic memories, at most 100 sources/5 seconds per batch. Coalesced requests; no per-run retained map or durable queue. Foreground preempts active work. Snapshot rechecks source versions; correction/deletion invalidates old groups. No new facts, personality mutation, LLM/cloud call or unsolicited speech. Restart rebuilds view; UI switch is process-local, startup env provides deployment choice.
- **RT-011 summary DONE:** deterministic extractive summaries with source position/hash/version and omission markers; at most 24 same-session/privacy completed pairs restored. Keep user/system/authorization/current pending pairs and newest observations. Oversized request gets at most one compaction pass, then original byte/native guard. No provider retry for compaction, no extra LLM call, no summary schema. Memory mutation fences in-flight context and conservatively excludes older runs from summary restore. Raw journal remains intact.
- **Product entry:** scripts/start-runtime-product, three control-panel sections, memory correction/deletion controls, effective feature status in /v1/runtime. Custom port origins now match selected loopback port. Offline manual file inspection is real Rust execution; model tool planning still requires a capable selected model.

## Verification

| Check | Result / evidence |
|---|---|
| Final full Python suite | **437 passed, 5 opt-in skipped, 3 dependency warnings, 93.84s**; pytest-final.log |
| Last local filesystem check refinement | Reused already-read stat result to avoid extra synchronous I/O; workspace tests **2 passed** afterward |
| Rust workspace tests | PASS; rust-tests.log (library 6 passed) |
| Main/Core/SQLite/model-to-Rust path | PASS in test_runtime_product; synthetic model, actual Rust process and file result, actual main/catalog/journal |
| UI owner route | Auth required, root escape rejected, tools switch blocks, actual readback PASS |
| Memory source mutation | Actual main/SQLite correct/delete, no extra digest facts, stale groups removed, pre-mutation summary not restored PASS |
| Background bounds | Duplicate-start one owner, 100 triggers coalesced, active read cancelled, seven-day fake clock, no owned work/task after close PASS |
| Context | Raw journal unchanged, goals/system/pending intact, old long response excerpted, uncompressible/latest result rejected with zero provider calls PASS |
| Rollback | Drained main restart with all three flags off; original memory deletion persisted and ordinary text still responds PASS |
| Real browser UI | Local Chromium: real Rust list/read displayed; pause/refresh, memory correction/delete PASS, zero page errors; ui-result.json and product-preview.png |
| Format/lint/type/schema | Repository ruff format/check PASS; mypy PASS (191 files); schema export check and launcher shell syntax PASS |

Full-suite initial run had six fixture failures: old exact catalog lists did not include workspace capabilities; browser lifecycle fixtures assumed shutdown belonged solely to BrowserSessions. Updated expected catalog and tracked browser instance while preserving real shutdown/resource assertions. Initial log retained in pytest-full-initial.log. Earlier UI harness could not find Playwright's cached binary; reran against installed Chromium. Chinese path case exposed Python/Rust Unicode JSON hash difference, fixed locally and covered by a real-runtime test.

Existing CI format failures were addressed by excluding historical evidence snapshots and local .siro-data assets from Ruff (not src/tests), and formatting two existing test expressions without behavior change. Source/test gates remain active; no tests skipped to hide a failure. Remote CI and the entire scripts/check secret-scan pipeline were not run; do not claim remote CI PASS.

## Evidence / limits

Synthetic models and local browser/Rust were used; no real provider inference, real speech/GPU, human GUI acceptance, private deployment rollback or long wall-clock soak was performed. Seven-day fake clock is not a seven-day soak. The five opt-in external tests were skipped, not passed.

The preview at http://127.0.0.1:8026 uses an isolated temporary data directory with labeled synthetic memories and offline model; it does not replace the owner's existing deployment. preview.json records its owned PID/directory, not credentials. UI screenshot contains synthetic data only.

Extractive summary omits details and can still exceed budget when protected content is too large. It does not provide infinite history or semantic truth guarantees. Memory mutation invalidation is deliberately broad and may discard useful old conversation context. Digest lists the latest 100 eligible items, not a semantic consolidation of all memories. UI toggle persists only until restart. Runtime RPC itself retains its existing protocol limits and driver implementation; no claim of hardening all local filesystem race conditions or sandboxing computer.execute.

## Rollback and source trace

Use the three startup flags from PRODUCT_QUICKSTART after drained shutdown. Keep canonical DB/journal/memory and previous AR-06/07 fixes. A source-only scoped patch and source digests accompany this report; reverse dry-check verifies patch applicability, not deployed rollback. Existing user changes remain uncommitted and preserved. Documentation and adapted fixtures are not an instruction to blindly reverse the whole Git working tree.
