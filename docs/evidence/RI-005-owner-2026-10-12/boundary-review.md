# D50 independent OS owner boundary research

Date: 2026-10-12, Asia/Taipei. **Status: SOURCE_REVIEW_COMPLETED / D50_OWNER_SCOPED_VERIFIED; FIX-015_BACKUP_CANCEL_CLEANUP_BLOCKED.** This reviewer changed only owned boundary evidence files: the original OS probe/review, mapped signal reproducer/results, destination reproducer/results, and joint/temporary/ZIP signal reproducer/results explicitly authorized by the parent. No production/test edit, private DB/config/key/model, live8026 process operation, runtime restart or deployment occurred. The archived results contain this reviewer's actual synthetic runs, not another agent's runs. Historical conclusions below describe their recorded cutoff; the final three-key source review and separate confirmed FIX-015 cleanup blocker are recorded at the end.

Read D50 in `docs/CONTRACTS.md` and `docs/DECISIONS.md`, plus existing `scripts/start`, `scripts/stop`, `scripts/launch_companion.py`, Gateway main/lifespan, IntegratedCompanion startup, CLI release/restore/demo/backup, operations and current ReleaseManager. D49 remains separately verified; this research does not reopen its restore design.

## Actual OS probe

The original run used `/tmp/siro-d50-flock-probe.py`, exited **0**, and archived [`boundary-probe.json`](boundary-probe.json). Profile: **Python 3.14.4 / Linux kernel 7.0.0-34-generic / tmpfs**. The probe owned every process it started, joined them, and removed its entire synthetic fixture root `/tmp/siro-d50-lock-wni41qzj`. It did not operate any existing service or read private files. The recorded eleven groups are OS/prototype observations, not eleven passing production-owner tests.

Reproduce from the repository root:

```bash
./.venv/bin/python docs/evidence/RI-005-owner-2026-10-12/boundary-probe.py
```

The script writes a new result only to `/tmp/siro-d50-flock-probe.json`, leaving the archived original unchanged. Its lock files and process markers are synthetic.

| Actual experiment | Observed result | Boundary consequence |
|---|---|---|
| Four simultaneous exclusive nonblocking contenders | Three `busy`, exactly one `acquired` | Use one stable lock inode with `LOCK_EX|LOCK_NB`; reject busy without retry or PID guessing. |
| SIGKILL of that owned holder, then wait | Exit -9; subsequent contender acquired; observed kill/join/check elapsed 3.257 ms | A holder without inherited copies needs no stale-lock-file deletion. This one duration is not a timing SLO. |
| Raw fork, descriptor marked non-inheritable, parent closes its copy | Child still retained lock; contender busy until child closed its copy | CLOEXEC does not close a descriptor at fork. Inherited copies must remain part of the conservative owner boundary. |
| Raw fork child explicitly `LOCK_UN` while parent retained its descriptor | Independent contender acquired | Never unlock a shared description in child cleanup. Close-only preserves the parent's ownership. |
| Owner exec with CLOEXEC | Replacement process remained alive, independent contender acquired | Do not acquire in a launcher and claim ownership continues across its exec. Acquire in actual Gateway composition. |
| Owner exec with explicitly inherited descriptor | Independent contender stayed busy | Accidental descriptor inheritance can keep a lease alive; default CLOEXEC and helper close-fds matter. |
| Directory symlink paths refer to same real directory | Canonical roots equal; same lock alias busy | All entrypoints must derive the same canonical database identity and fixed lock domain. |
| Lock-file symlink opened with O_NOFOLLOW | ELOOP (errno40), rejected | Reject the lock-file alias rather than following its content or trusting its name. |
| Hardlinked regular lock file | Same inode, st_nlink=2 | Regular-file status alone is insufficient; check single-link ownership as required by D50. |
| Delete/recreate lock path while old holder is alive | New inode locked by a second owner | Never unlink or replace a coordination file. |
| Two synthetic data directories with the same DB target through symlink and naive parent lock | Actual DB targets equal, second parent lock acquired | A raw data-parent lock name can split ownership. Canonical DB key or explicit alias refusal is required. |

The measured description-sharing and exec behavior agrees with the Linux manual; `flock` is advisory and independent users may ignore it. Remote NFS/SMB semantics depend on protocol and mounts. [Linux flock manual source](https://raw.githubusercontent.com/mkerrisk/man-pages/master/man2/flock.2). Python documents that descriptors are non-inheritable by default but still inherited by raw fork; their non-inheritable flag takes effect at exec. [Python 3.14 descriptor inheritance](https://docs.python.org/3.14/library/os.html#inheritance-of-file-descriptors). No network filesystem was accessed or tested.

## Concrete caller evidence and smallest integration

- Gateway `main` initializes `shared_store` before Uvicorn/lifespan, while IntegratedCompanion creates another store for the same `data_dir/siro.db`. An ASGI-only lifespan lock would be too late. Capture the directory once and hold the OS context around actual Gateway main, before provider/composition/SQLite work, until full server shutdown returns.
- `scripts/start` currently uses a check/write PID file rather than atomic data ownership. `scripts/stop` sends TERM without proving a completed drain. They should keep routing through Gateway main; successful maintenance lease acquisition is the managed-owner boundary, not receipt of TERM. The product launcher execs into Gateway and should not transfer the lease across exec.
- CLI demo creates identities/conversations; CLI backup initializes the store and can migrate it. Both are writer callers alongside restore. Their outer synchronous CLI handler boundary should hold the same context through `asyncio.run`, including its executor join. Restore must retain that context through ZIP cleanup/config/readback. Library SQLiteStore/IntegratedCompanion calls should not take a second nonreentrant lease.
- CLI release stage/rollback with an explicit DB must share its canonical DB key. ReleaseManager Core stays independent of the OS adapter. Standalone release with no DB retains existing component behavior and cannot claim a stopped data writer. A healthcheck that tries to start a managed Gateway under maintenance ownership will be busy; genuine release→runtime handoff/readiness is the next separate integration gate.
- D49's rejected raw/ZIP restore into an absent target asserts the target directory remains absent. This makes an eagerly created target `.lock` unsuitable. The fixed account-home state namespace in D50 is a narrow compatible choice; its empty coordination artifacts must be described accurately and not mistaken for target data.

D50 specifies one neutral `exclusive_data_owner(database)` context: fixed pwd-account home `.local/state/siro/data-owners`, canonical DB SHA256 key, directory700/lock600, regular/same-UID/single-link checks, O_NOFOLLOW/CLOEXEC/nonblocking, close-only and never unlink. It avoids mutable HOME/XDG/TMP authority and PrivateTmp domains. That is smaller than a new lease manager, daemon, PID registry or SQLite-level refactor.

## Required production acceptance and remaining gates

Source/caller acceptance must still prove actual adapter atomic contention, safe busy/unavailable statuses with zero DB/pointer/config/provider effects, canonical aliases, lock-file/DB hardlink negatives, permissions, missing-target preservation, close/primary-error behavior, and context retention through startup/drain, failures and cancellation/executor join. Actual fd boundaries should be tested using synthetic child processes rather than only replacing an owner with a fake context. The compatibility baseline includes D49 raw/ZIP restore and existing launcher/operational behavior.

Only Linux/same effective UID/local filesystem/cooperating entrypoints is proposed. tmpfs is the only filesystem actually exercised by this reviewer. Neither an idle lease nor this research proves old unmanaged/external SQLite writers are stopped; first adoption needs separate evidence. Same-UID hostile path replacement, network filesystems, power loss, cross-file ZIP atomicity and arbitrary library connections remain uncertified. Actual signed launcher consumption, selected process version/readiness, approved handoff and deployment remain RI-005 gates. Final production source audit is pending implementation/refreeze.

## Narrow production audit in progress

The initial implemented source read for this audit was the new `src/siro/adapters/data_ownership.py` (observed SHA256 `62e5d5a4aa47b0be7790eed57e9eaad05ba2bf8f8c06b0472884a95771dad3f4`), CLI `727fecbcf1289294a7064f9eba498edd932a3c4c4494aaa316c8b732ff0e61ad`, and Gateway `cd731a0f792cb2f9fa7088b4aef8c82bb0719f175fe3c504598cea3cd8703829`. The adapter was still being refined concurrently, including close-error mapping; these identify the initial read and are not asserted as the frozen final hash or every subsequent probe's source. No production/test file was edited by this reviewer.

The implemented caller shape matches D50: Gateway captures data_dir before its outer owner and passes it into the existing body; initial SQLite `asyncio.run` and Uvicorn use the yielded local loop factory. CLI main covers demo/backup/restore and DB-bound release, with the three async wrappers using that factory. Uvicorn **0.53.0** installed code accepts a callable custom loop factory directly. Existing Core/SQLite/operations APIs do not take a second lease. The owner records only its own standard-library default pools; its join thread shutdown waits for those pools while repeated main-thread KeyboardInterrupt retains the fd, then closes rather than unlocks it. Actual mapped SIGINT and Gateway loop acceptance is being extended by the parent and is not inferred solely from this source shape.

This reviewer actually ran `./.venv/bin/pytest -q tests/integration/test_data_owner_lifecycle.py tests/integration/test_data_owner_callers.py` at that intermediate cutoff: **37 passed / 2.42 s / two existing pypinyin deprecation warnings**. That is an intermediate scoped run, not final whole-card acceptance. Subsequent independent counterexamples below remain part of the review, rather than being erased by the earlier green run.

### Confirmed local error-boundary gaps

All three counterexamples used owned synthetic temporary paths, returned their actual facts through the tool conversation, joined/closed owned resources, and removed fixtures. No extra result files were invented or private account-state directory accessed. Production repairs and RED tests are parent-owned pending final refreeze.

| Issue | Actual probe and observed result | Smallest requested correction |
|---|---|---|
| Unknown pwd-account lookup escapes safe boundary | Controlled `pwd.getpwuid` raises `KeyError('synthetic account lookup absent')`; actual `cli.main(['backup', ...])` raises KeyError instead of returning `data_owner_unavailable`. Target directory remains absent. | Map missing-account KeyError to the existing unavailable error, without a fallback namespace. |
| Acquisition primary error washed out by close refusal | Independent kernel fd holds the exact synthetic key; only the competing descriptor's close is injected to raise OSError. After `_finish` maps close to unavailable, the acquisition cleanup catches only OSError. Actual result: DataOwnerUnavailableError, no notes, rather than original DataOwnerBusyError. The probe finally closes both owned descriptors with the original close. | Preserve acquisition error and attach the same sanitized secondary cleanup note already used after yield. |
| Permission-denied existing DB mistaken for absence | **Actual OS permission probe:** a synthetic existing `data/siro.db`, `chmod(data,0)`; direct DB.stat raises PermissionError. Python3.14 `Path.exists()` suppresses it and the owner nevertheless yields: `owner_acquired=true`, no error, coordination created. The probe restores mode700 in finally and removes the fixture. | Treat only FileNotFoundError from stat as an intended missing DB; map other OS ownership failures to unavailable before entering the caller. |

These are **MINOR_FIX / LOW / IMPLEMENTATION_BUG / TEST_GAP** within the new adapter's safe-error/primary-error contract. None proves that the OS lock allows two cooperating writers on the same stable key, and none warrants a manager, PID fallback or architecture redesign. The permission probe is a real local OS failure; the pwd and close refusal cases are explicitly controlled faults. Final independent acceptance must re-bind the repaired source hash and demonstrate these negatives alongside ownership/IO join and existing D49 regression behavior.

### Repaired local boundaries and actual mapped interruption

The parent added RED cases and corrected the local adapter. The new source uses `canonical.stat()` with only FileNotFoundError treated as absence, maps missing pwd-account KeyError to unavailable, catches secondary acquisition cleanup failures without replacing the original primary, checks exact directory700/lock600, and hashes `os.fsencode(canonical)` so valid OS byte paths do not fail Python's plain UTF8 encoding. There is no alternate namespace, PID fallback, new policy or global event-loop policy change. Its loop factory sets/clears only the calling thread's current loop. At the subsequent intermediate cutoff this reviewer actually ran the same focused command: **43 passed / 2.70 s / two existing pypinyin deprecation warnings**. This is still not the final frozen source/run; mapped caller fixtures were being extended concurrently.

This reviewer independently invoked the **actual mapped CLI backup** in an owned child process using the real owner, real SQLite work and its new loop factory. The code is [`mapped-signal-probe.py`](mapped-signal-probe.py); the actual intermediate result is [`mapped-signal-probe.json`](mapped-signal-probe.json). The parent authorized these two evidence files; the original eleven OS/prototype groups remain untouched. Reproduce from repository root with:

```bash
./.venv/bin/python docs/evidence/RI-005-owner-2026-10-12/mapped-signal-probe.py
```

It writes only `/tmp/siro-d50-mapped-audit.json`, leaving the archived intermediate result unchanged. It creates only owned synthetic DB/state paths, clears model/API environment variables for its child, joins that child and removes its fixture. It does not start a Gateway, browser, provider or live service.

The test-only `_initialize_sync` seam first invokes the original actual initializer, then pauses a real pending SQLite UPDATE. The default-executor shutdown seam only marks entry and delegates to the original method. The caller is the original `cli.main(['backup', ...])`; no handler is replaced. First SIGINT cancels the caller; second arrives after Runner shutdown entry; third reaches the owner's subsequent wait. The code does not infer clean join from Runner exit. The actual recorded facts were:

```json
{
  "adapter_sha256_at_start": "cb5dfaa11a7b7dbcb274d36ba4ddba4648b16e08100797be10d4d1145f4925ec",
  "child_alive_after_three_sigint": true,
  "old_db_work_pending": true,
  "second_owner_busy_while_old_io_pending": true,
  "child_exit": 130,
  "child_stdout": "INTERRUPTED",
  "child_stderr_present": false,
  "old_db_work_finished_before_next_owner": true,
  "value_before_next_write": "old-owner-write",
  "final_value": "next-owner-write",
  "backup_created_after_cancel": false
}
```

Profile: Python3.14.4 / SQLite3.46.1; owned fixture `/tmp/siro-d50-mapped-audit-5el4e1qx` removed. The digest was captured at the start of this intermediate run, not invented as a final freeze digest while helper changes were ongoing. It demonstrates conservative exclusion until actual IO completion, followed by retention of the next owner's committed write. It does not promise cancellation undoes a completed effect or certify arbitrary executor/network/kernel failures. Final frozen source audit/replay remains pending.

## Final frozen source re-audit

The parent confirmed these five frozen files; this reviewer independently read/calculated the same hashes and matched them against `preservation.json`'s recorded `final_sha256` (all five matched):

| File | Actual SHA256 |
|---|---|
| `src/siro/adapters/data_ownership.py` | `cb5dfaa11a7b7dbcb274d36ba4ddba4648b16e08100797be10d4d1145f4925ec` |
| `src/siro/cli.py` | `727fecbcf1289294a7064f9eba498edd932a3c4c4494aaa316c8b732ff0e61ad` |
| `src/siro/services/presentation/gateway.py` | `8be67a5d3aeff067f00c49db1ac1b19ab3e6ba22c6c9c9911fa2b3adf2db3dd1` |
| `tests/integration/test_data_owner_callers.py` | `41ad6041cb3ca240e242d173cd5f3a2d17c71df5537ec14dfc87d0f96dbfa0df` |
| `tests/integration/test_data_owner_lifecycle.py` | `8817bd716fb68ffbb0707f0bef59e194fa8aed46a7171ebbb65a6e64981aba67` |

The final Gateway diff against the captured D50 before-file is local: the outer owner, captured data_dir, same existing body, initialization loop factory and callable Uvicorn loop. The final callable annotation suppression describes the already inspected installed Uvicorn importer rather than adding a fallback loop. CLI keeps its original mapped bodies and wraps their full operation. No D49 SQLiteStore, Core/release/migrations, permissions or unrelated lifecycle implementation is changed by this scope. The final adapter retains the actual fd through its owned-pool shutdown and close-only cleanup, rejects unsafe fixed namespace/files/aliases, maps unknown OS/account failures safely and preserves primary failures with sanitized secondary notes. The three previously reported local defects are repaired in the frozen source; no new reproducible scoped defect was found.

After refreeze this reviewer actually ran the same validation command against both final test files: **46 passed / 5.48 s / two existing pypinyin deprecation warnings**. This final scoped run includes the formal actual CLI backup/demo repeated-SIGINT cases, the real owned HTTP Gateway/competitor/shutdown case, actual fd/fork/exec/WAL cases, and controlled cleanup/join-refusal cases. The HTTP fixture uses synthetic state, an owned ephemeral loopback port explicitly excluding8026, no model request, and cleans up its process. These distinctions do not turn the controlled failures into real disk failure or certify every product/runtime profile.

The independent `mapped-signal-probe.py` was then actually replayed after refreeze, without changing its archived intermediate result. [`mapped-signal-probe-final.json`](mapped-signal-probe-final.json) records Python3.14.4 / SQLite3.46.1, frozen adapter digest `cb5dfaa...`, owned fixture `/tmp/siro-d50-mapped-audit-wkc6s5a2` removed. After all three SIGINTs the child remains alive with old IO pending and the competing actual owner is busy. After release the child exits130, no stderr or backup destination appears, the old IO has completed before the next owner enters, and final value remains `next-owner-write`. The earlier intermediate adapter digest happens to equal the final digest; this is a separate final replay, not relabeling the historical run. CLI/Gateway/test hashes above independently identify the other frozen files, while this probe directly executes the mapped CLI and adapter.

**Conclusion:** independent narrow source review is complete with no remaining reproducible blocker for D50's declared cooperating Linux/account/local-filesystem owner profile. Parent master preservation/full regression and whole-card status are separate evidence; this reviewer did not execute or invent their whole-suite/rollback counts. Network filesystems, older/unmanaged/external writers, first-adoption stopped-owner evidence, raw library callers, hostile filesystem races, power-loss/ZIP multi-file atomicity and actual signed launcher/version/readiness/handoff/deployment remain separate gates. Acquiring this lease does not retroactively stop an old version or authorize runtime activation.

## Subsequent confirmed backup write-target blocker

The parent requested an additional narrowly scoped actual caller probe before claiming D50 complete. It disproves the earlier source-only write-key assumption; the green conclusion above is historical and **does not apply to this now-failed caller path**. Source hashes at the probe were unchanged: adapter `cb5dfaa...`, CLI `727fec...`, Gateway `8be67...` as fully listed above.

This reviewer seeded two synthetic, fully migrated temporary SQLite DBs. An owned child held the target DB's actual `exclusive_data_owner` and an actual SQLite connection. The parent then invoked the original `cli.main(['backup', '--data', sourceRoot, targetRoot/'siro.db'])`, using the same synthetic coordination domain. No CLI handler or SQLite backup implementation was replaced. Actual results:

```json
{
  "target_before": "foreign-managed-latest",
  "target_holder_ready": "HELD foreign-managed-latest",
  "target_busy_before_backup": true,
  "cli_exit": 0,
  "cli_status": "backed_up",
  "target_after_backup": "source-snapshot",
  "target_inode_changed": true,
  "target_holder_alive_after_backup": true,
  "target_busy_after_backup": true,
  "holder_exit": 0,
  "holder_remaining_stdout": "OWNED_CONNECTION foreign-managed-latest",
  "holder_stderr_present": false
}
```

Profile: Python3.14.4 / SQLite3.46.1, own fixture `/tmp/siro-d50-destination-audit-ay7qb6re` removed and all child processes joined. With subsequent parent authorization, the actual reproducer/result are now archived as [`backup-destination-probe.py`](backup-destination-probe.py) and [`backup-destination-probe.json`](backup-destination-probe.json). This original RED result preserves the actual cb5df/727fec/8be67 source hashes, not a future repaired-source result. Re-run from repository root with `./.venv/bin/python docs/evidence/RI-005-owner-2026-10-12/backup-destination-probe.py`; it writes only `/tmp/siro-d50-backup-destination-probe.json`, leaving the archived original untouched. No unexecuted results are claimed.

**Classification: FIX-014 / REQUIRED_FIX / HIGH / IMPLEMENTATION_BUG / MISSING_INTEGRATION / TEST_GAP**, assigned by the parent as a blocking D50 repair without changing historical task numbering. Confirmed root cause: CLI main guards only `arguments.data/siro.db`; the existing `SQLiteStore._backup_sync` captures to an owned temporary file and calls `os.replace(temporary, destination)`. Thus a managed backup is allowed to replace a different managed DB while its correct target lease remains held. This is a write-scope gap in D50, not an OS flock failure or permission to redesign SQLiteStore.

The parent owns the smallest repair: acquire all known affected write-path keys before entering the mapped operation, canonical-key deduplication, and one shared owned IO resource that retains every fd through complete pool shutdown. A naive nested two-owner stack using the source owner's factory could close destination before IO finishes; even choosing the inner factory needs join-refusal acceptance for every fd. Extend the existing local resource's fd set rather than creating a manager or global registry. The negative test must prove a busy destination has zero source migration/target/config/body effects; success, cancellation, partial acquisition failure, aliases and shared-resource join refusal must retain the original owner invariants. Final source audit and master verification remain blocked until this local guard repair is complete and refrozen.

The accepted design is the same context with optional `write_target: Path | None`, one/two canonical byte-sorted deduplicated keys, one `_DataOwner` fd set, rollback of partial acquisition before the body, one owned-pool join before closing all fds. Existing Core/SQLiteStore/operations remain unchanged. The parent will supply the repaired-source freeze for an independent narrow joint-scope re-audit.

## Joint-scope verification and subsequent ZIP temporary-role correction

The two-key phase's real mapped backup-stage repeated-SIGINT replay is archived in [`joint-signal-probe.py`](joint-signal-probe.py) / [`joint-signal-probe.json`](joint-signal-probe.json), with adapter928359/CLI3dcb540/test77526+612650 hashes recorded in full inside the result. The original SQLite `_backup_sync` was paused before its actual work, then delegated after release. Both source and destination keys stayed busy while the work was pending; after thread/process join the snapshot had actually been committed, both keys were free and the next owner's `next-owner-write` remained. This is an honest completed-effect observation, not a claim that cancellation undid it. [`backup-destination-probe-joint.json`](backup-destination-probe-joint.json) similarly preserves the two-key phase's actual foreign-owner refusal: exit1/data_in_use, unchanged target inode/rows, original holder alive. These are intermediate results, not relabeled final three-key acceptance.

Another independent review then proved that the deterministic ZIP temporary path could collide with an input or an independently leased file. The parent kept FIX-014 open, added RED cases and extended the same resource with `temporary_write_target: Path | None`. This reviewer's own temporary-target probe first ran after that three-key implementation existed, so its first observation in [`tmp-destination-probe.json`](tmp-destination-probe.json) is **GREEN**, not invented RED evidence. Its recorded adapter3f87/CLI662947/testf12b1+ac1e hashes identify that intermediate cutoff. The fixed caller derives the exact suffix-plus-`.tmp` path only for ZIP operations and rejects direct/temporary outputs that collide with the DB, input settings or source archive. It acquires at most three canonical byte-sorted/deduplicated keys into the original local resource, and one owned-pool join completes before closing any fd. No new manager, global registry, Core/SQLiteStore/operations change or architecture redesign was added.

## Final three-key source binding and actual verification

This reviewer independently calculated these current frozen hashes and matched all five against `preservation.json`:

| File | Actual final SHA256 |
|---|---|
| `src/siro/adapters/data_ownership.py` | `3f87e47eaa5622d51f1ff6a08ad2653fbdd39ff0955c52f0868ea999295fe77d` |
| `src/siro/cli.py` | `cd78a622bd99d7779761cfbf29bdc04dab4ddccac8e45fcc6a84c85457a24a1f` |
| `src/siro/services/presentation/gateway.py` | `8be67a5d3aeff067f00c49db1ac1b19ab3e6ba22c6c9c9911fa2b3adf2db3dd1` |
| `tests/integration/test_data_owner_callers.py` | `0e2a66c8143b8ba3897ef41053189ab707cdcd55daa4aee806060f1ce6ee84c0` |
| `tests/integration/test_data_owner_lifecycle.py` | `6418c5b0176d693fc5a76cbf9ad750964284bf50e08bdc25fcfc8599d6ac8418` |

The final CLI digest includes a variable-only rename to `restore_inputs`; behavior matches the preceding three-key repair. Old cb5df/727fec and two-key928359/3dcb540 observations remain historical and do not receive these newer hashes.

This reviewer actually ran the focused final command against both current test files: **70 passed / 5.21 s / two existing pypinyin deprecation warnings**. The run includes meaningful actual OS/caller cases and explicitly controlled join/cleanup fault cases; this is not an invented whole-suite or deployment result. The parent owns whole-card/master verification counts and any independently saved full-suite logs.

[`tmp-destination-probe.py`](tmp-destination-probe.py) was actually replayed at these final hashes; [`tmp-destination-probe-final.json`](tmp-destination-probe-final.json) records an owned child holding the actual `backup.zip.tmp` key and SQLite connection. The CLI refuses with exit1/data_in_use before source-v1 migration: source bytes retained and migration versions remain `[1]`. Foreign temporary file path, bytes and inode are retained, no output archive is created, and the original holder remains alive/busy until explicitly released and joined. This added inode observation comes from the actual final run; it is not retroactively inserted into the earlier JSON. Fixture `/tmp/siro-fix014-tmp-audit-u8k0c380` was removed by this reviewer.

The true final three-key ZIP backup-stage replay and mode inspection are [`zip-joint-signal-probe.py`](zip-joint-signal-probe.py) / [`zip-joint-signal-probe.json`](zip-joint-signal-probe.json). The actual CLI ZIP handler runs; its original `_backup_sync` is only paused/delegated, Runner shutdown is marked/delegated, and SIGINT is actually delivered three times. Source, final output and deterministic temporary keys remain busy while the real snapshot work is pending. The IO finishes before all three keys can be acquired by the next owner. The child exits130 without stderr; no ZIP is published, existing output/temporary bytes remain, and the next owner's output remains intact. **The completed private SQLite snapshot is an actual effect; it is not reported as undone.** All five hashes inside this mode/result replay agree with the final table above.

**D50/FIX-014 owner finding:** no remaining reproducible lease/write-role/IO-lifetime blocker was found within the declared managed Linux/account/local-filesystem profile. Three-key owner invariants are independently verified. This does not certify older/unmanaged/external writers, first adoption, network filesystems, arbitrary library callers, hostile filesystem races, power loss, ZIP cross-file atomicity or signed launcher/version/readiness/handoff/deployment.

## Separate FIX-015: real cancelled ZIP staging orphan

The same final ZIP replay proved an original Operations/backup cleanup gap despite correct D50 key ownership. `create_backup_bundle` owns its `TemporaryDirectory` in the async coroutine, while `SQLiteStore.backup_to` awaits bare `to_thread`. Cancellation unwinds/removes the directory before the actual backup thread has joined. The released original `_backup_sync` then recreates that directory and commits the private snapshot. The lease correctly remains held, but the component leaves that snapshot after child/process join. This is a **separate preexisting implementation/ownership/test gap**, not failure of the three-key flock or justification for another manager. The parent assigned **FIX-015 / REQUIRED_FIX / MEDIUM**, with product ZIP backup-cancellation cleanup still BLOCKED.

The recorded true replay inspected only its own known `root/staging` subtree after child join and before the probe's fixture cleanup. Initial TemporaryDirectory mode was **0700**, inode373810. It was absent while old snapshot work remained pending. The recreated directory was **0775**, inode373816, UID/GID1000, demonstrating actual recreation rather than an assumed default mode. Exact remaining entries and `lstat` facts are in `zip-joint-signal-probe.json`:

| Owned orphan under `/tmp/siro-fix014-zip-joint-_v4g7efl/staging/siro-backup-48h0n2ap` | Actual mode | Size | Group/other file-readable |
|---|---|---:|---|
| Directory | 0775 | 100 | Directory listing permitted; not file-content evidence |
| `siro.db` | 0600 | 507904 | false / false |
| `.siro.db.2nr98977.tmp-shm` | 0600 | 32768 | false / false |
| `.siro.db.2nr98977.tmp-wal` | 0600 | 0 | false / false |

The private snapshot contained only the known synthetic value `source-snapshot`. No other-UID file-content exposure was measured; **do not assert 0644 files, HIGH exposure, or a 0755 directory**. Directory metadata is broader than the original private directory, but all observed regular files are600. The JSON records the child joined/exited130, actual IO finished, and component orphan present after join.

The final `root_removed=true` means **the probe owner explicitly removed its entire synthetic fixture including that orphan**, not that production Operations cleaned it. This distinction must survive any master report. The next repair belongs to the original backup join/connection-close/staging cleanup path and its own tests; this reviewer did not edit it. D50 owner can remain scoped VERIFIED while FIX-015 and the existing full RI-005 release/product gates remain blocked. Evidence files are frozen at this cutoff; no further exploration or source/test edits were performed.
