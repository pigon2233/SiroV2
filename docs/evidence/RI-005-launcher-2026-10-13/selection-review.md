# D52 signed active release selection — independent test review

## Scope

This agent changed only `tests/integration/test_release_launch_selection.py` and `selection-*` evidence. Production source was written by the parent agent. No private database, conversation, settings, credential, model, or live service was used.

## Baseline

The exact frozen 70-case suite failed 70 assertions in 1.09 seconds against `core/releases.py` SHA-256 `8279e91498816ec3ab41357b2d9ce76d7bb67d6091f79567639b4df8a2050048`. The baseline lacks the selector API and typed refusal, so this RED demonstrates missing integration. It does not claim 70 separately reproduced defects in the existing rollback implementation. Collection succeeded. The original suite and its hash are retained in `selection-before-test.py` / `selection-before.json`.

## Implemented selector acceptance

The unchanged 70-case suite passes against the new API. Fixtures use real temporary SQLite, independently signed synthetic source trees, and ordinary local files. The WAL case keeps an actual writer open and verifies latest conversation, memory, and completed action rows plus WAL bytes; the original writer remains usable.

Verified contract areas:

- Two exact signed active versions return immutable identity, canonical source directory, complete actual source digest, and the observed data schema.
- No active pointer refuses instead of falling back to last-known-good or checkout source. Invalid pointers reject JSON types, duplicate keys, unknown fields, oversized records, non-version paths, traversal, symlink, hardlink, and directory records.
- Receipt/source verification rejects missing runtime files, signed-version mismatch, extra fields, legacy/null signing format, unsigned bounds, signature/digest mismatch, and altered ordinary source bytes. Receipt JSON is bounded and duplicate-free.
- Target/source/record aliases are rejected, including direct constructor root symlink, parent/source directory symlink, ordinary source symlink/hardlink, and a real FIFO. The FIFO is not opened or read by the fixture or selector.
- Schema checks require an actual database and a bounded integer prefix; unknown/corrupt/missing ledgers, future schema, signed range mismatch, and invalid constructor schema refuse. The actual compatible schema is used even when the constructor maximum differs.
- Success and rejection preserve pointer, release tree, historical backup, configuration, and database bytes. Controlled tripwires reject any call to staging, rollback, backup, pointer writing, copytree, or subprocess health/launch effects.

Strict mypy and Ruff lint/format pass for the new test file. New API source read-only review found no confirmed selector blocker within these contracts.

## Limits

The synthetic Python files intentionally satisfy only the Core required-file contract; they do not establish Gateway ABI, module provenance, successful process launch, readiness, stopped legacy writers, signed maintenance-to-runtime handoff, or product quality. Those are separately owned caller/process/adoption acceptance gates. This review does not certify hostile same-UID filesystem races, concurrent schema change after the read snapshot, network filesystem behavior, power loss, or arbitrary generated releases. OS aliases and SQLite are real; effect tripwires and source/record tampering are controlled fixtures. Complete regression and final source binding remain parent-owned.
