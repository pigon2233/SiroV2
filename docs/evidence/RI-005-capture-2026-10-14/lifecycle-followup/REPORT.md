# RI-005 next-scope private anchor / owned lifecycle prototype

2026-10-14（Asia/Taipei）。Only new research evidence in this directory; no production/tests/contracts/previous evidence changes, commit, deployment, live8026 or private data. Runtime uses only public system CPython3.14/stdlib and self-owned fixtures. Existing repository Ruff binary is used for static checks, never supplied as a runtime dependency.

## Actual outcome

Eight tiny OS cases were executed against bubblewrap0.11.1. **The final structured result is FAILED / 3 aggregate check failures**, not eight graceful PASS. The newly added assumptions “COMMAND has only stdio FDs” and “environment contains only LANG/LC_CTYPE” were not met: actual readiness reports FD numbers `[0,1,2,3]` and environment names `LANG,PWD`. FD3 identity and the required final child FD allowlist are **UNKNOWN / NOT_VERIFIED**; no private environment values were read or printed. The latest raw result is retained unchanged in [result.json](result.json); exit0 of this JSON-producing research script is not gate acceptance.

The original primitive observations remain directly visible:

| Case | Actual observation |
|---|---|
| private-anchor-alias | Host selected parent became a symlink after sealed FDs were prepared and before spawn, then was replaced again before late import. `/siro-release` initial/late/resource bytes remained captured; write failed EROFS. Actual fixture SQLite write, DB canonical path, cwd and prepared asset path/content remained correct. TERM drain marker and exit0 observed. |
| wrapper-term | Owned info channel identified the direct COMMAND; pidfd TERM produced drain marker, exit0, and monitor join. |
| repeated-wrapper-term | Three actual TERM requests to this probe's existing parent handler coalesced to one COMMAND TERM; drain marker, exit0 and monitor join observed. |
| monitor-term-negative | **Expected counterexample:** monitor TERM returned -15 while COMMAND remained alive and no graceful marker appeared. Exact held pidfd SIGKILL cleaned the owned COMMAND; it was confirmed gone. This is not graceful PASS. |
| child-exit7 | Actual COMMAND nonzero7 propagated through the monitor; pidfd exit observed. |
| popen-missing | Real FileNotFoundError, no child started. |
| setup-failure | Owned nonexistent mount rejected with exit1; no readiness or signal to an unverified PID. |
| exec-failure | Owned nonexistent executable rejected with exit1; no readiness or signal to an unverified PID. |

All parent FD numbers returned to the initial set, source/info/pidfd handles were closed, original TERM handler restored, monitors joined, and owned temporary root removed. All verified COMMANDs exited; the negative monitor case explicitly required forced COMMAND cleanup. These resource observations do not resolve the extra child-FD allowlist check.

## Minimum boundary demonstrated

The namespace starts from a private root; it does **not** bind host `/` over `/`. Same-name mappings are public `/usr` read-only and only the self-owned `/tmp` subtree read-write, with public library symlinks and proc/dev setup. `/siro-release` is a namespace-private tmpfs tree populated from sealed `ro-bind-data` FDs and remounted read-only. It never uses the mutable selected host path as a source mount destination. This fixture avoids changing canonical data paths to a `/host/...` alias; it does not prove complete host/device permission compatibility.

The existing probe parent owns `Popen`, a dedicated bounded info pipe, stdout/stderr and pidfd. It reads the complete info JSON through EOF, confirms trusted tiny COMMAND readiness PID and case tag, checks PPID/starttime, and then sends signals only through the held pidfd. Stop requests are coalesced, COMMAND drain is observed, and the monitor is joined afterward. There is no new daemon, registry or product owner. This trusted fixture's readiness is not proof against hostile startup PID reuse; a held startup gate and independent proof-FD/identity protocol remain future integration work.

Official v0.11.1 info JSON is emitted **before mount/cwd/exec**, so it is not readiness; an internal PID-namespace init can change which process it identifies. `--as-pid-1` skips the internal reaper but retains the external monitor. `--block-fd` waits after mount/pivot/drop-privileges; EOF releases it and is not cancellation. [Official bubblewrap source](https://github.com/containers/bubblewrap/blob/v0.11.1/bubblewrap.c), [option contract](https://github.com/containers/bubblewrap/blob/v0.11.1/bwrap.xml).

Actual COMMAND `PR_GET_PDEATHSIG` was **0**. Official source sets SIGKILL before COMMAND exec; public host binary metadata showed neither setuid bits nor getcap values for bwrap/python3.14. Why this setting disappeared is **UNKNOWN**. Do not infer monitor-death cleanup from the previous stdin-reading probe: stdin EOF can also make that trusted child exit. The current counterexample keeps COMMAND running independently of stdin and demonstrates that this local profile cannot rely on observed monitor exit as cleanup. No further host-policy/root-cause investigation was performed. [Linux PDEATHSIG contract](https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html).

## Reproduction, failures and cleanup

[run-receipt.json](run-receipt.json) binds the exact final script SHA before/after execution and result SHA, system Python version, real command/environment names and static check outputs. Only PATH/LANG are passed to the research runner; actual bwrap COMMAND receives LANG plus observed PWD. The final script's format and lint checks both EXIT0.

- [result-initial.json](result-initial.json): UNKNOWN_INCOMPLETE / Errno9. The original evidence harness repeated a close after its FD number had been reused for the new pidfd. Local bookkeeping was fixed by invalidating closed info-FD variables. Original probe SHA is recorded in the receipt; the initial result is not PASS.
- [result-monitor-interrupted.json](result-monitor-interrupted.json): UNKNOWN_INCOMPLETE after monitor TERM left COMMAND alive and inherited stdout prevented `communicate` completion. [monitor-interrupted-cleanup.json](monitor-interrupted-cleanup.json) records exact PID/starttime recheck, pidfd SIGKILL, exit notification and subsequent proc disappearance. Its “monitor joined” field alone is explicitly not proof of COMMAND cleanup.
- Four initial B023 static warnings concerned loop closure binding in this evidence script only. Per-run handler defaults were bound and the final script executed again; no production or acceptance threshold was changed.

```bash
/usr/bin/python3.14 docs/evidence/RI-005-capture-2026-10-14/lifecycle-followup/probe.py
.venv/bin/ruff format --check docs/evidence/RI-005-capture-2026-10-14/lifecycle-followup/probe.py
.venv/bin/ruff check docs/evidence/RI-005-capture-2026-10-14/lifecycle-followup/probe.py
```

Rollback for this uncommitted research is removal of this new directory only. Previously published FIX-020 source/evidence and contracts remain untouched. Do not lower the final extra FD/env checks or label their failure as a passing caller profile.

## Remaining gates

RI-005 remains PARTIAL. Bounded verified source capture, full Gateway/SDK/dependency identity, actual D50 lease/key integration, complete host/device permissions, PID namespace/init profiles, hostile same-UID startup identity, old/unmanaged writer absence, approved maintenance handoff, shutdown deadline policy, external stop exit-code compatibility, power loss and formal deployment remain NOT_RUN. Actual product cancellation/drain requires its own existing-launcher integration and tests. This research is a next-scope input, not product loader DONE or a FIX-020 publication blocker.
