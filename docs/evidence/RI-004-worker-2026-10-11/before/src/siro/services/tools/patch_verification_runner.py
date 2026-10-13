"""Trusted single-process runner mounted outside the candidate source tree."""

from __future__ import annotations

import ctypes
import errno
import resource
import sys
import unittest
from pathlib import Path


def restrict() -> None:
    libc = ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libc.so.6", use_errno=True)
    libc.prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise RuntimeError("no_new_privs unavailable")
    for kind, limit in (
        (resource.RLIMIT_AS, 256 * 1024 * 1024),
        (resource.RLIMIT_CPU, 5),
        (resource.RLIMIT_FSIZE, 1024 * 1024),
        (resource.RLIMIT_NOFILE, 64),
        (resource.RLIMIT_CORE, 0),
    ):
        resource.setrlimit(kind, (limit, limit))
    library = ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libseccomp.so.2")
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    library.seccomp_attr_set.restype = ctypes.c_int
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    library.seccomp_rule_add.restype = ctypes.c_int
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_load.restype = ctypes.c_int
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    context = library.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError("seccomp unavailable")
    try:
        if library.seccomp_attr_set(context, 2, 0x80000000) != 0:  # BADARCH/KILL_PROCESS
            raise RuntimeError("seccomp architecture restriction unavailable")
        for name in (
            "fork",
            "vfork",
            "clone",
            "clone3",
            "execve",
            "execveat",
            "socket",
            "socketpair",
            "connect",
            "setns",
            "unshare",
            "mount",
            "umount2",
            "ptrace",
            "process_vm_readv",
            "process_vm_writev",
            "bpf",
            "userfaultfd",
            "io_uring_setup",
            "open_by_handle_at",
            "setrlimit",
            "prlimit64",
            "setsid",
            "setpgid",
            "memfd_create",
            "shmget",
            "shmat",
            "semget",
            "msgget",
            "mq_open",
            "perf_event_open",
            "keyctl",
            "add_key",
            "request_key",
        ):
            number = library.seccomp_syscall_resolve_name(name.encode())
            if (
                number < 0
                or library.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0) != 0
            ):
                raise RuntimeError("seccomp syscall restriction unavailable")
        if library.seccomp_load(context) != 0:
            raise RuntimeError("seccomp load failed")
    finally:
        library.seccomp_release(context)


def main() -> int:
    try:
        restrict()
    except Exception:
        print("unsupported_sandbox", flush=True)
        return 78
    if sys.argv[1:] == ["--probe"]:
        print("SIRO_PATCH_PROFILE_READY_V1", flush=True)
        return 0
    if sys.argv[1:]:
        return 78
    # Candidate paths enter imports only after irreversible OS restrictions.
    sys.dont_write_bytecode = True
    sys.path[:0] = ["/candidate/src", "/candidate"]
    for root in (Path("/candidate/src"), Path("/candidate/tests")):
        for path in sorted(root.rglob("*.py")):
            compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    suite = unittest.defaultTestLoader.discover("/candidate/tests", pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.testsRun > 0 and result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
