"""Irreversible limits for the fixed trusted synchronous Python profile."""

from __future__ import annotations

import ctypes
import errno
import resource


def restrict(*, memory_mb: int = 256, cpu_seconds: int = 5) -> None:
    if type(memory_mb) is not int or not 16 <= memory_mb <= 256:
        raise ValueError("unsupported memory limit")
    if type(cpu_seconds) is not int or not 1 <= cpu_seconds <= 5:
        raise ValueError("unsupported CPU limit")
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
        (resource.RLIMIT_AS, memory_mb * 1024 * 1024),
        (resource.RLIMIT_CPU, cpu_seconds),
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
