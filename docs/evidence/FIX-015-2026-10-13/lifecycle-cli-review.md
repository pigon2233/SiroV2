# FIX-015 final backup CLI boundary review — 2026-10-13

Status: **Revised source review and 59 selected cases PASS** for the local backup
profile. The initial 24 controlled PASS below was **not final acceptance** and
missed selector wakeup: real signal timing and two unchanged D50 caller cases
subsequently failed. Whole-suite, actual process-signal acceptance and rollback
remain separate root/signal-reviewer gates; they are not inferred from these
controlled tests.

This reviewer changed only `lifecycle-*` evidence during this final CLI review.
The production wrapper and its new test file belong to root.

## Final selector-wakeup revision

The first handler called `task.cancel()` without explicitly waking the event loop.
The reviewer initially failed to identify that requirement. Direct callback tests
ran while the loop was already active and therefore could not certify real OS
SIGINT delivery when the selector was blocked. The separate actual probe
`signal-cli-wakeup-before.json` records eight failed timing handshakes at the first
CLI hash `a0ca401e...`; unchanged D50 backup initialization cases also failed.
Those REDs remain valid historical evidence, without altering the old test.

The root's local correction adds only the captured loop's
`call_soon_threadsafe(lambda: None)` after canceling the exact task. I inspected the
installed Python 3.14 `asyncio.Runner._on_sigint`: its first-interrupt path likewise
cancels the main task **and then wakes a loop blocked in select with a long
timeout**. The revised backup handler retains repeated cancellation instead of
Runner's second-interrupt immediate exception, and still restores the prior
handler before Runner shutdown. No global manager or unrelated handler changed.

Final scoped bindings:

- CLI: `8e55ac903c35dc8cb0f7161306c5588238c93d6bbf08b3f90be90e14292a75b5`
- SQLite: `325677351c592bc4f701fc80db71930792425542dffe692cea2ad14702c0828c`
- CLI test (6 cases): `11c15eb5bf9bf7923422d84a9cacbec5b983df4fee8e5acac2a828136db56845`
- backup lifecycle test (19 cases): `10bc5bf46e329e74fdd611ff399ad5e944d1c984ce88dc34f38fa0bd0b3b6fd2`

Independent final run: **59 PASS / 2 existing warnings / 8.05s**,
`lifecycle-cli-wakeup-final.log`: all 25 new cases plus all 34 unchanged original
D50 caller cases, including actual backup/demo child SIGINT and offline Gateway
contention tests. Ruff format/check and strict mypy PASS on all four scoped
source/test paths. The added sixth CLI outcome directly verifies a signal flag
with successful body return still raises KeyboardInterrupt and restores the old
handler; primary typed-error and plain-cancel cases remain separate.

Fresh source-segment/hash comparison reconfirms every CLI function except
`_backup`, `main`, D50 adapter/Gateway/both old owner tests and operations are
unchanged. No further confirmed local defect remains after this narrow correction.
The separately revised eight-case true signal probe and full offline suite must
still pass against this same source; this reviewer does not claim their result.

## Historical initial source binding and controlled checks

- CLI: `a0ca401e33de76291065014d5133f37f02b721a76f9d624018d391d2292cee6d`
- SQLite: `325677351c592bc4f701fc80db71930792425542dffe692cea2ad14702c0828c`
- CLI test (5 cases): `a6a51c704e067112d5ed0f7469289e6ed01b80860fcaa1d8f749c9261bb4fd0e`
- backup lifecycle test (19 cases): `10bc5bf46e329e74fdd611ff399ad5e944d1c984ce88dc34f38fa0bd0b3b6fd2`

Historical independent selected run: **24 PASS / 0.76s**, `lifecycle-cli-final.log`, using
`test_backup_cli_cancellation.py` and `test_sqlite_backup_lifecycle.py`. Ruff
format/check and strict mypy pass on all four source/test paths, without adding
suppression. Root's 5-case CLI fixture invokes the installed handler directly;
it is controlled signal-contract evidence rather than an OS SIGINT process probe.
The 19-case lifecycle matrix uses actual temporary SQLite copies and ZIP paths
with timing/failure controls separately identified in `lifecycle-review.md`.

AST source-segment comparison against the captured old CLI confirms identical
function names and **every function except `_backup` byte-identical**, including
`_backup_data`, `_restore`, `main`, parser and existing owner/collision handling.
SQLite pre-backup methods plus D49 restore/following body remain byte-identical.
The D50 adapter, Gateway and both D50 tests remain bound to their former hashes:

- owner: `3f87e47eaa5622d51f1ff6a08ad2653fbdd39ff0955c52f0868ea999295fe77d`
- Gateway: `8be67a5d3aeff067f00c49db1ac1b19ab3e6ba22c6c9c9911fa2b3adf2db3dd1`
- owner callers test: `0e2a66c8143b8ba3897ef41053189ab707cdcd55daa4aee806060f1ce6ee84c0`
- owner lifecycle test: `6418c5b0176d693fc5a76cbf9ad750964284bf50e08bdc25fcfc8599d6ac8418`
- operations: `4ca501497228283d1b9e0ea6f2889c95c5f187f695b1be50ca0737f5dbc0d55b`

## Handler and cancellation boundary

The wrapper installs a temporary Python SIGINT handler only on the main thread,
after capturing the existing handler and the exact running backup task. The
handler sets one stack-local flag and cancels only that task; it neither raises
immediately nor globally cancels other tasks/futures. Three repeated interrupts
therefore remain normal owned cancellation requests while backup IO resolves.
The backup's retained executor Future is not an asyncio Task that
`Runner.close` can cancel through its all-tasks sweep.

`finally` restores the exact prior handler on success, plain cancellation and
typed failure. When asyncio.Runner had installed its own prior handler, normal
Runner shutdown subsequently retains its original restoration behavior. A
background-thread invocation performs no signal registration and uses the
original async invocation behavior. The passed local data loop factory remains
the same; no global event loop policy, signal manager or new owner is introduced.

Signal-driven cancellation is translated to KeyboardInterrupt only after owned
operation cleanup; a plain CancelledError remains a cancellation. A worker's
primary typed failure bypasses that cancellation translation and remains the
original object. A SIGINT flag is also checked after successful return, so a
late interrupt cannot silently become normal success merely because `cancel()`
was too late or the body resolved cancellation. This last success-return flag
branch was present in the initial source but was not directly exercised by its
5 controlled CLI cases. The final sixth case above now covers it.

The initial review did not identify the selector-wakeup defect; the actual signal
RED and narrow final repair above supersede that initial conclusion. Initialization
is still the existing SQLite initialization path, and independently blocked OS IO,
external writers, signal termination/powerloss, hostile filesystem races,
whole-product launcher/handoff and ZIP restore atomicity are not newly certified.

## Adjacent regression scope

The prior ten-file D50 matrix consists of SQLite store, both D49 restore tests,
operational CLI, release manager/signing/data retention, companion launcher and
both D50 owner tests. Add the two FIX-015 focused test files for this card.
The full regression should explicitly use `-m 'not real_provider'`; the five
external-provider cases must remain honestly unselected.
