# RI-005 D48 / FIX-012 — 保留最新資料的 code-only rollback

Status: VERIFIED — code-only component; final exact-source tests/rollback and scoped audit complete. Source RI-005 / T32 / D39 / current review. Classification REQUIRED_FIX / HIGH. Source types ORIGINAL_DESIGN_ERROR + BAD_INTERFACE + TEST_GAP; not a demonstrated new regression. Existing rollback explicitly restores old whole DB and the old test requires latest writes to disappear.

Scope: smallest local ReleaseManager correction; persist complete signed sidecar for newly staged immutable version, verify target identity and actual read-only SQLite schema before code pointer rollback, never restore/migrate/replace DB in rollback. Existing release API/CLI/result shape and complete signing format unchanged; old unsafe restore expectation intentionally corrected. Existing explicit siro restore remains separate and unchanged.

Expected files: src/siro/core/releases.py; tests/integration/test_release_manager.py; new tests/integration/test_release_data_retention.py. Must NOT change launcher, Gateway/UI, SQLiteStore, migrations, Core dialogue/identity/memory, permissions, models, skills, dependency/build config, live8026 or private data. Only temporary synthetic fixtures.

Acceptance: two newly signed staged versions → late DB/WAL writes → code pointer back while exact rows/ledger remain and existing writer still usable; missing/corrupt old backup irrelevant; unknown/future/incompatible schema or target/receipt tamper zero pointer effects; interruption never restores old data; same version cannot overwrite published authority; actual CLI remains parseable. No claims of stopped-writer ownership, real startup/readiness, schema migration success or deployment. RI-005 remains PARTIAL/BLOCKED_BY_RELEASE_INTEGRATION for the next launcher/single-writer slice.

Rollback: exact3file disposable reverse/reapply; no live source operation or data rollback. Operational old source must not be used to invoke its obsolete DB-restoring rollback. Latest DB retained; evidence and previous dirty work preserved.
