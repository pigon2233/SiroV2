"""Fixed Linux single-process Python mounts shared by explicit trusted callers."""

from __future__ import annotations

from pathlib import Path

_LIBRARY_ROOT = Path("/usr/lib/x86_64-linux-gnu")
_LIBRARIES = (
    "libc.so.6",
    "libm.so.6",
    "libz.so.1",
    "libexpat.so.1",
    "libffi.so.8",
    "libseccomp.so.2",
)


def runtime_mounts() -> tuple[tuple[str, str], ...] | None:
    paths = [
        ("/usr/bin/python3.14", "/usr/bin/python3.14"),
        ("/usr/lib/python3.14", "/usr/lib/python3.14"),
        (str(_LIBRARY_ROOT / "ld-linux-x86-64.so.2"), "/lib64/ld-linux-x86-64.so.2"),
        *((str(_LIBRARY_ROOT / name), str(_LIBRARY_ROOT / name)) for name in _LIBRARIES),
    ]
    if any(not Path(source).exists() for source, _ in paths):
        return None
    return tuple((str(Path(source).resolve()), target) for source, target in paths)


def sandbox_argv(
    bwrap: str, workspace: Path, mounts: tuple[tuple[str, str], ...]
) -> tuple[str, ...]:
    argv = [
        bwrap,
        "--unshare-all",
        "--unshare-user",
        "--disable-userns",
        "--assert-userns-disabled",
        "--die-with-parent",
        "--cap-drop",
        "ALL",
        "--clearenv",
    ]
    for source, target in mounts:
        argv.extend(("--ro-bind", source, target))
    argv.extend(
        (
            "--symlink",
            "usr/lib",
            "/lib",
            "--ro-bind",
            str(workspace / "candidate"),
            "/candidate",
            "--ro-bind",
            str(workspace / "trusted"),
            "/trusted",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--size",
            str(8 * 1024 * 1024),
            "--tmpfs",
            "/tmp",
            "--remount-ro",
            "/proc",
            "--remount-ro",
            "/dev",
            "--remount-ro",
            "/",
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--setenv",
            "TMPDIR",
            "/tmp",
            "--chdir",
            "/candidate",
            "--",
            "/usr/bin/python3.14",
            "-I",
            "-S",
            "-B",
            "/trusted/runner.py",
        )
    )
    return tuple(argv)
