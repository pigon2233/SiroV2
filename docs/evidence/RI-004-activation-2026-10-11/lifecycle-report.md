# D47 activation lifecycle acceptance

New tests only: `tests/integration/test_skill_activation_lifecycle.py`. No production source or other tests were changed for these probes. The existing activation owner had already been implemented; these are additional acceptance cases, not pre-implementation RED claims.

`lifecycle-final.log`: **7 PASS, 2.21s**. Scoped Ruff lint/format, mypy and diff whitespace passed (`lifecycle-lint.log`, `lifecycle-format.log`, `lifecycle-types.log`, `lifecycle-diff.log`). Final test bytes are recorded in `lifecycle-test-final.json` and `lifecycle-after/`.

## Actual OS with a controlled trusted-runner delay

The first case prepares/installs/enables the real fixed D44 template through the existing helpers. Only its later private trusted runner copy is changed by the test hook: after irreversible restrictions and after the normal probe early return, it prints a fixed marker and sleeps. Approved template/package bytes and hash remain unchanged. This is controlled actual OS cancellation evidence, not fixed-template latency or performance evidence.

The test observes the actual post-restriction marker, then admits a second owner job and waits until both jobs are owned. Revoke returns only after both finish with failures/cancellation. Exactly one probe and one execution were spawned; the queued second job never spawned. All captured subprocess/descendant PIDs were gone, worker workspaces were removed, registry was disabled, and managed template hash was unchanged.

`lifecycle-first.log` initially had 1 FAIL / 6 PASS because the fixture attempted to write the readonly trusted runner copy. `lifecycle-marker-diagnostic.log` identifies PermissionError in that test hook. The hook now temporarily changes only the owned copy's mode and restores readonly mode; `lifecycle-os-queue.log` passes. Those failures are fixture errors, not confirmed production defects.

## Real SQLite pre-commit ownership

Four cases stop enabling via repeated caller cancellation, revoke, tools-off suspend or close. A hook inside real `SQLiteStore._run_transaction_sync` blocks after the actual enabled UPDATE and before its COMMIT. A separate SQLite reader still sees disabled state and a second writer is locked; the original writer lock stays held. Stop/cancel does not acknowledge while that transaction remains blocked. After release, its actual commit is followed by an identity-bound compensating disable. No enabled result returns; final registry/cache are disabled and owned control tasks are empty. No async registry success stub substitutes for the transaction.

## Cleanup semantics

Two cases block real off-loop worker workspace cleanup, cancel the owner execution twice, and require the join before acknowledgment. The normal-result case propagates cancellation rather than success. The other injects a typed primary process-owner cleanup failure and verifies that late cancellation preserves `ExecutionCleanupError`. The injected error is a controlled failure fixture, not an actual kernel cleanup failure. Both remove workspaces and clear owner jobs.

No private DB/chat/key/WAV, model/GPU, existing service restart or deployment was involved. General blocked host I/O latency and additional runtime profiles remain outside these tests.
