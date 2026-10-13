# D47 registry/catalog foundation

This report covers only `persistence/skills.py`, `services/tools/orchestrator.py`, and the new `test_skill_activation_foundation.py`. It does not certify the activation owner, HTTP/UI, actual strict worker integration, or deployment.

## Changes

- `install_if_absent(skill, enabled=False)` verifies captured source identity off the event loop, including type-sensitive manifest/input/output metadata. `INSERT OR IGNORE` preserves an existing version's entire row. The original `install()` UPSERT behavior remains.
- Optional `set_enabled(..., identity=skill)` rejects stale id/version/package hash/root for enable and disable, retaining the original read/update SQL CAS. Matching disable remains possible when source files are corrupt; enable still verifies source.
- `is_installed(..., identity=skill)` checks stored identity independent of enabled state, without source verification or exposing the store.
- `ToolCatalog.register()` shares constructor guards, copies mutable definition/metadata, rejects duplicates, and adds descriptors by copy-on-write. Existing orchestration can use the newly registered descriptor; unavailable descriptors remain known to candidate preparation.

## Executed evidence

| Check | Result | Record |
| --- | --- | --- |
| Initial APIs absent, before either production edit | 35 FAIL / 1 PASS, 0.73s | `foundation-before.log` |
| Added installed-identity facade absent, before that source edit | 7 FAIL / 36 deselected, 0.30s | `foundation-installed-before.log` |
| Final new contract tests | 43 PASS, 0.74s | `foundation-after.log` |
| New tests plus existing registry/package identity/catalog tests | 107 PASS / 3 existing warnings, 4.27s | `foundation-regression-final.log` |
| Scoped Ruff lint/format, mypy, diff whitespace | PASS | `foundation-lint-final.log`, `foundation-format.log`, `foundation-types-final.log`, `foundation-diff.log` |
| Exact temporary-copy reverse/reapply of two existing files and one new test | PASS | `foundation-rollback.json` |

Tests use real temporary SQLite transactions for insert conflicts, concurrent insert winners, stale approval, and a controlled replacement during verification. The event-loop verification case uses a controlled blocking synthetic verifier. Catalog dispatch uses the existing orchestrator with a synthetic executor; it is not an OS worker proof. No private data, existing runtime service, model, or GPU is involved.

`foundation-baseline.json` and `foundation-before/` preserve the exact dirty pre-card bytes; `foundation-final.json`, `foundation-after/`, and `foundation-scoped.patch` preserve the final scoped bytes. Reverting source does not revert registry data. Product activation must first stop admission and join owned jobs; its owner remains responsible for joining cancellable SQLite/preparation operations before acknowledgment.
