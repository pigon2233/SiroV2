# Reproducible source-only rollback

Run from the SiroV2 root:

```sh
.venv/bin/python docs/evidence/T10-TASK-DETAIL-2026-10-18/rollback/verify.py
git apply --check docs/evidence/T10-TASK-DETAIL-2026-10-18/rollback/rollback.patch
```

Both commands leave the checkout unchanged. The verifier performs actual rollback and reapply only in its own temporary directory, compares exact snapshot bytes, checks a synthetic latest-data sentinel, then removes that directory.

`BASELINE_COMMIT` identifies the full original Git commit. `index.before.snapshot` is the dirty pre-DETAIL file, including D69 memory search; it is intentionally not the version at HEAD. `index.after.snapshot` is the exercised DETAIL file. `SHA256SUMS` binds these exact files. This is the complete baseline for this single-file feature, not a snapshot or rollback of the whole repository.

`rollback.patch` goes from current DETAIL to the supplied pre-DETAIL snapshot. `reapply.patch` goes the other way. The older `../task-only.patch` adds the feature: checking it forward against a checkout that already has DETAIL is expected to fail. Do not use it as a forward rollback patch.

The verifier rejects drift without editing the checkout; it never runs an application, touches a database, changes a service, or deploys. On a later source version, review and regenerate the bounded patch instead of forcing it. Production rollback and live data recovery remain NOT VERIFIED.
