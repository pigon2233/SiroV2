# RI-003 final scoped source review — 2026-10-10

Review scope: the two existing source files, two new service files, and two new test files listed in `preservation.json`; D43 and the existing bounded process owner. This is a local Linux x86_64 / system CPython 3.14 single-process profile. It is not a general generated-skill execution or release audit.

An independent read-only reviewer inspected preflight, projection, mounts/environment, syscall restrictions, resource claims, and cancellation. The reviewer did not execute candidate code, edit files, read private material, or restart services. Root owns the execution results in the other evidence files.

| Finding | Evidence before repair | Small repair | Final disposition |
|---|---|---|---|
| Private IPC namespaces still permit kernel allocations outside AS/scratch accounting | `ipc-before-full-output.log` and `ipc-before.json`: one synthetic semaphore, SysV queue, and POSIX queue were all created and immediately removed | Add `semget`, `msgget`, `mq_open` to the irreversible filter before candidate imports | Independent follow-up confirmed creation denial suffices for the fresh empty namespace; actual regression included in final suite |
| A caught SIGINT after the verification task completed could print `passed` and exit 0 | `cli-late-signal-before.log`: controlled completed-task window returned 0 instead of 130 | Recheck the command-local interrupted flag after restoring the signal handler and before output | Independent follow-up confirmed fix and handler-restoration regression |

No remaining confirmed blocker was found within this declared profile. This is scoped review evidence, not proof against all kernel vulnerabilities or hostile same-UID modification of the trusted runtime.

The final report must retain these limits:

- `RLIMIT_AS` bounds candidate virtual address space, not aggregate kernel RAM. The tmpfs size bounds file data, not every inode, pipe buffer, or kernel object. No aggregate cgroup or arbitrary multiprocess claim.
- The privacy allowlist consists of ordinary visible `.py` files under `src` and `tests`; it does not detect secrets deliberately embedded in source. Other project paths are never copied or digested.
- The local kernel, system interpreter/libraries, fixed runner and source owner are trusted. Namespace/filter failure rejects execution; there is no host fallback.
- Candidates can forge their own test results. `passed` grants no authority to enable, deploy, or modify the host. RI-004/005 retain their own gates.

Primary references: [Linux IPC namespaces](https://man7.org/linux/man-pages/man7/ipc_namespaces.7.html), [Linux POSIX queue implementation](https://raw.githubusercontent.com/torvalds/linux/master/ipc/mqueue.c), [Python 3.14 SIGINT handling](https://docs.python.org/3.14/library/asyncio-runner.html#handling-keyboard-interruption). IPC isolation destroys private objects when the namespace ends; this does not establish the application's resource budget. Python's default second SIGINT can immediately raise `KeyboardInterrupt`, which explains the separately retained repeated-interrupt cleanup failure.
