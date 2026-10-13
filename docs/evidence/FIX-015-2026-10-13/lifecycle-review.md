# FIX-015 backup lifecycle test review — 2026-10-13

Status: **19 lifecycle cases VERIFIED for the scoped local backup profile**.

## Repaired source-bound verification

Final owned run: **19 PASS / 0.73s** (`lifecycle-final.log`); standalone Ruff
format/check and strict mypy PASS, with no new type suppressions. The first repair
run also passed the then-18 cases (**18 PASS / 1.28s**, `lifecycle-after.log`).
One actual `isinstance(Connection)` assertion in the fixture narrowed a dynamic
factory result for mypy; it also confirms the controlled SQLite factory was used.

Final scoped bindings:

- SQLiteStore: `325677351c592bc4f701fc80db71930792425542dffe692cea2ad14702c0828c`
- unchanged operations: `4ca501497228283d1b9e0ea6f2889c95c5f187f695b1be50ca0737f5dbc0d55b`
- final 19-case test: `10bc5bf46e329e74fdd611ff399ad5e944d1c984ce88dc34f38fa0bd0b3b6fd2`

Direct comparison against the captured original confirms all `SQLiteStore`
methods before `backup_to`, plus the complete `restore_from` and following body,
remain byte-identical. Only backup lifecycle and its required import changed.

The source uses one existing loop/default executor Future, with a per-call
`copy_context` and cancellation event. A Future is not another asyncio Task for
Runner cancellation to abandon. The writer lock remains held during repeated
caller cancellation until that Future resolves. Its primary result is observed
once, and cancellation is propagated afterward. Before-directory, non-DONE copy
and pre-publication checks prevent known-canceled work from publishing a new
snapshot. Real source/target handles receive explicit close attempts; primary
errors retain their type/object with only secondary failure types in notes. The
temporary cleanup path follows the same precedence and exposes a refusal after
otherwise successful publication.

The nineteenth case exercises two concurrent caller contexts through actual
SQLite snapshots. Each worker receives its own ContextVar value; neither caller
context leaks into the other or into the owner task. Both copies run offloop,
retain source facts and preserve the old `to_thread` context behavior.

No confirmed defect remains in this scoped direct-API review. Full regression,
actual process/SIGINT acceptance and source-only rollback are owned by root/the
separate signal reviewer and are **not claimed here**. OS-blocked IO timing,
powerloss, hostile path replacement, arbitrary external writers, global SQLite
connection cleanup and ZIP multi-file restore atomicity remain outside scope.

## Backup-only cancellation fences supplement

Independent process-SIGINT research identified that `Runner.close` can cancel the
retained asyncio job as well as its awaiting caller. The agreed narrow repair
therefore forwards an optional local `threading.Event` to `_backup_sync`, fences
before creating directories, during non-DONE SQLite copy progress and before final
publication. The public API stays the same. The new wrappers now accept/forward
this optional private argument; old-source calls with no event remain executable.

The current test file has **18 cases**, with a fresh exact-old-source run
**16 FAIL / 2 PASS / 0.86s** (`lifecycle-cancellation-fences-before.log`). SQLite
remained bound to `976595f41b6715a1818ec00d1130398ec3befbb793f8ed08562d96d25ddc33bc`.
Current test SHA256:
`5131fa6afc65957a13f37f7e816fb92576a49315b567dc02ae8c3ea81c55e5bd`.

The additional two cases copy a real roughly 1 MiB synthetic SQLite database in
genuine page steps. Only progress timing is controlled. Three cancellations at
non-DONE copy and at actual SQLITE_DONE must join, preserve the previous final
backup exactly and remove all owned temporary database/sidecars. SQLITE_DONE
commits only the private temporary snapshot; it is **not** final `os.replace`
publication. The separate after-real-publication test continues to require honest
retention of an already committed raw output. Before-copy cancellation now expects
no publication, while a queued writer still cannot overtake cleanup.

The original 16-case test is captured exactly as `lifecycle-before-test.py`; its
hash and raw RED remain intact below. The final strict-mypy run awaits the actual
new optional production signature, rather than suppressing call-argument errors.

## Original 16-case RED

Owned changes are only `tests/integration/test_sqlite_backup_lifecycle.py` and this
`lifecycle-*` evidence. Production, existing tests, private/live data, models and
providers were not changed or accessed by this reviewer.

The original pre-repair test file contains 16 cases. Actual corrected-fixture run:
**14 FAIL / 2 PASS / 0.63s** (`lifecycle-before-final.log`). The preceding
corrected-fixture run was **14 FAIL / 2 PASS / 0.67s** (`lifecycle-before.log`);
the final tests additionally seed an actual WAL source and compare exact source
main-file bytes after canceled ZIP completion. Source bindings:

- SQLiteStore: `976595f41b6715a1818ec00d1130398ec3befbb793f8ed08562d96d25ddc33bc`
- operations: `4ca501497228283d1b9e0ea6f2889c95c5f187f695b1be50ca0737f5dbc0d55b`
- new test: `85fef1754e41d075b05cc86823ef7017d77533280c60f199b8dff919567c1e33`

The initial run also counted 14 failures but included a **fixture defect**: the
test owner could not force-close a refused SQLite handle created in the worker
because SQLite thread affinity remained enabled. Its raw log is retained as
`lifecycle-fixture-affinity-failure.log`; it is not independent evidence of 14
production defects. Only the tracked-connection fixture now uses
`check_same_thread=False` so the owner can clean refused handles. Production
close attempts still run inside the actual backup worker. Standalone Ruff
format/check and strict mypy pass for the corrected test file.

The corrected RED demonstrates these current defects through real SQLite copies
and paths, with controlled timing/refusal seams explicitly marked:

- Single and three repeated cancellations release backup coroutine and writer
  lock while the real offloop worker remains pending. A queued writer may pass it.
- ZIP cancellation unwinds the actual `TemporaryDirectory` before the pending
  real snapshot copy; its workspace can subsequently be recreated.
- Cancellation after actual raw snapshot commit returns before worker completion;
  cancellation must not be represented as undoing that committed output.
- Pending worker errors are not delivered as the primary caller error after
  cancellation. The new contract also observes the loop exception handler to
  guard against a duplicate unobserved worker error.
- Transaction contexts leave real source/target connections open on success,
  copy error and partial target-open failure.
- Source/target close refusal is not surfaced or annotated because no explicit
  close is attempted. Both acquired handles must receive a close attempt even if
  one fails; forced fixture cleanup does not masquerade as production success.
- `finally: temporary.unlink()` masks an earlier typed copy error when cleanup
  refuses. The primary error must survive with a sanitized secondary failure note.

Two existing invariants already pass: cancellation while waiting for the writer
lock does not start a copy, and a forced final unlink error remains visible after
the raw snapshot has already committed. Tests retain these semantics rather than
requiring architecture changes or hidden rollback.

Every pause is bounded and its release is set in `finally`; every owned task is
gathered and actual worker completion observed. All databases/config/archive
bytes are synthetic and confined to pytest temporary directories. No SIGINT
process probe or full-suite result is claimed in this file yet.
