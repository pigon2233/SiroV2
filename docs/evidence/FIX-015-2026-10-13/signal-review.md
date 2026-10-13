# FIX-015 independent CLI signal acceptance

Current verdict: **final fixed-source eight-case actual CLI signal acceptance
PASS**. Historical failures below remain preserved and do not certify the final
source. No broad runtime/deployment/cancellation-latency claim is made.

`signal-before.json` is the first four-case probe. `signal-before-expanded.json`
adds actual raw-copy-committed-before-cancellation cases. Both bind the unchanged
five public production files at start and finish. SQLiteStore hash is
`976595f41b6715a1818ec00d1130398ec3befbb793f8ed08562d96d25ddc33bc`;
the complete per-path hashes are recorded in the JSON. Neither result certifies
any later source revision.

The expanded probe actually executes CLI backup, the original SQLite backup,
OS advisory locks and process SIGINT. A delegated backup wrapper pauses before
the real copy, or after a completed raw copy, to make the cancellation timing
repeatable. A synthetic migrated SQLite database and generated default settings
are used. No private database/settings/chat/audio/key/provider/model or live
8026 service is read or changed. Each probe-owned child is joined and each
synthetic root removed in its final cleanup; this fixture cleanup does not erase
the recorded production cleanup failure.

For ZIP with one and three SIGINT, the original implementation deletes its
private staging directory while its actual copy remains pending. The source,
destination and fixed ZIP temporary keys correctly remain busy. Releasing the
copy lets it recreate staging and leaves a snapshot plus WAL/SHM after command
exit. This confirms the FIX-015 local cleanup defect independently of D50's
correct cooperative owner behavior.

For raw backup with one/three SIGINT both before copy and after actual commit,
the original worker commits `source-snapshot` even though the command returns
130. A source repair must not describe a committed raw output as rolled back or
safe to retry automatically. The after-commit timing cases distinguish a real
SQLite commit from a merely scheduled await.

For the retained-job repair, the same script changes only the timing handshake:
first SIGINT waits for the delegated `asyncio.wait` to observe cancellation;
second interrupts Runner.run and waits for Runner.close's second task
cancellation; third interrupts that cleanup wait. Source/destination/fixed-temp
busy, real copy completion, staging cleanup, stderr, source/settings/final output
retention and next-owner writes must be verified against the actual repaired
source. Merely retaining a Python Task does not certify this process-signal
boundary. The first actual repaired probe is described below; it is not a clean
six-case task-teardown PASS.

## First repaired source: six actual mapped cases

`signal-after-first.json` and `.log` bind the same five public paths, now with
SQLiteStore hash
`325677351c592bc4f701fc80db71930792425542dffe692cea2ad14702c0828c`.
All five hashes are unchanged between probe start and finish. The other four
production source hashes remain identical to the recorded D50 source.

For ZIP with one/three SIGINT, staging stays present while real owned work is
pending and contains no entries after joined command exit. Source/settings/final
archive/fixed temporary bytes are retained. Actual independent key acquisitions
show all three cooperative keys busy during pending work and available after
join. No late work erases the next owner's output.

For raw with one/three SIGINT before copy, prior output is retained. In both
raw-after-commit cases, the already committed `source-snapshot` output remains
visible despite exit130; no false data rollback is inferred. All six child
processes are joined, every synthetic root removed, and no probe handshake or
fixture error occurs.

**New observed limitation:** all three three-SIGINT cases print `Task was
destroyed but it is pending!` for the public CLI `_backup_data` task. The third
SIGINT deliberately interrupts Runner.close's wait after its second delegated
task cancellation, so the Python coroutine teardown is abandoned even though
D50's outer owner joins actual pool IO. No recreated staging or data overwrite
was found, but this evidence cannot support a claim of complete task teardown or
clean stderr. No production/test changes were made by this independent probe.

## Expanded real in-progress copy acceptance

`signal-after-progress.json` / `.log` replay the six cases and add two real
in-progress ZIP cases against the same stable repaired source hashes. The
synthetic connection subclass delegates to actual `sqlite3.Connection.backup`;
it pauses only in the first non-DONE progress callback before delegating the
production progress callback. SQLite reports status0, 124 total pages and60
remaining after a real64-page copy. The owned scratch database already exists
before cancellation. This is not a fake backup or simulated SQLite success.

With one/three process SIGINT, cancellation stops that real in-progress copy;
both actual SQLite connections execute explicit close, and no staging directory
or snapshot remains after joined command exit. All three keys stay busy while
work is pending, source/settings/final archive/fixed temporary output remain
valid, and next-owner output is retained. The two raw-after-commit cases also
record exactly two explicit closes. Before-copy canceled cases open no backup
connections, so their zero close count is expected.

All eight cases have no probe handshake error or forced fixture kill; all owned
children are joined and every synthetic root is removed. The four three-SIGINT
cases retain the same public pending-task warning. Therefore the expanded probe
supports the original FIX-015 disk-cleanup invariant, not a claim of flawless
coroutine teardown under repeated process interruption.

## First backup-only CLI signal handler: missing selector wakeup

`signal-cli-wakeup-before.json` / `.log` bind SQLiteStore325677 and new CLI
`a0ca401e33de76291065014d5133f37f02b721a76f9d624018d391d2292cee6d`.
All eight cases time out waiting for their first actual retained await to observe
SIGINT cancellation. All owned processes are subsequently joined and synthetic
roots removed by fixture cleanup, but those cleanup results do not turn the
failed command-signal handshake into PASS.

The first custom handler calls `task.cancel()` without waking the event loop's
blocking selector. The installed CPython3.14 `Runner._on_sigint` first calls
`main_task.cancel()` then `loop.call_soon_threadsafe(lambda: None)` explicitly to
wake a loop blocked by select. This concrete missing wakeup also explains the
independently reported old initialization-stage shutdown-marker failures. It is
a local handler defect; the original ownership tests and their thresholds must
remain unchanged. At this historical revision no final signal PASS had been
recorded.

## Final fixed source: eight mapped cases PASS

`signal-final.json` / `.log` and the actual assertion run
`signal-final-assertions.log` bind these unchanged public source hashes at both
start and finish:

| Public production path | SHA256 |
| --- | --- |
| `src/siro/persistence/sqlite.py` | `325677351c592bc4f701fc80db71930792425542dffe692cea2ad14702c0828c` |
| `src/siro/cli.py` | `8e55ac903c35dc8cb0f7161306c5588238c93d6bbf08b3f90be90e14292a75b5` |
| `src/siro/operations.py` | `4ca501497228283d1b9e0ea6f2889c95c5f187f695b1be50ca0737f5dbc0d55b` |
| `src/siro/adapters/data_ownership.py` | `3f87e47eaa5622d51f1ff6a08ad2653fbdd39ff0955c52f0868ea999295fe77d` |
| `src/siro/services/presentation/gateway.py` | `8be67a5d3aeff067f00c49db1ac1b19ab3e6ba22c6c9c9911fa2b3adf2db3dd1` |

The backup-only CLI signal handler now wakes its captured event loop after
requesting task cancellation. The probe delivers each real OS signal only after
the actual retained backup coroutine has consumed the previous cancellation and
entered its next wait. Exactly one/three cancellations are consumed for the
corresponding cases while owned IO remains paused; Runner.close has not started.
There is no timeout downgrade or change to the original ownership tests.

All eight cases finish130 with **zero stderr**, including zero pending-task or
unobserved-error warnings. The exact original SIGINT handler is restored after
the command in every case. ZIP staging stays present during pending owned work
and is absent after joined command completion. Source/settings/prior final
archive/fixed temporary output are retained; actual kernel acquisitions show
the source/destination/fixed-temp keys busy until join and free afterward.

The two real non-DONE SQLite cases report64 of124 pages copied before
cancellation; both actual connections explicitly close and no scratch snapshot
remains. Both raw-after-publication cases retain the actual committed
`source-snapshot` output and both connections are explicitly closed; raw-before-
copy cancellation retains previous output. No canceled result is described as
a data rollback or permission to retry.

All eight next-owner writes remain intact after a further observation interval;
every owned child is joined and every synthetic root removed. The separate
`signal-assertions.py` rejects incomplete data, warnings, probe errors, forced
fixture kills, unconsumed signals, early teardown, missing lease ownership,
unrestored signal handlers or any broken output/staging invariants. Its executed
result is PASS. Both evidence scripts also pass Ruff format/lint.

Reproduction from repository root:

```text
.venv/bin/python docs/evidence/FIX-015-2026-10-13/signal-probe.py docs/evidence/FIX-015-2026-10-13/signal-final.json 1 1
.venv/bin/python docs/evidence/FIX-015-2026-10-13/signal-assertions.py
```

This certifies the named synthetic Linux/SQLite CLI cases and local FIX-015
invariant. Hostile same-UID mutation, unmanaged writers, indefinitely blocked
OS IO, SIGKILL/powerloss, ZIP multi-file atomicity and actual approved launcher
adoption remain outside this probe. No private sources, live8026 service,
provider/model/GPU, production deployment or production/test mutation occurred
in this independent acceptance task.
