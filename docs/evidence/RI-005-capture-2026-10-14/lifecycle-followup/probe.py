"""Owned tiny Linux primitives; never imports SIRO or reads private host state."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import select
import signal
import subprocess
import tempfile
import time
from contextlib import suppress
from pathlib import Path

SNAPSHOTS = {
    "src/ownprobe/__init__.py": b"VALUE='captured-first'\n",
    "src/ownprobe/late.py": b"VALUE='captured-late'\n",
    "src/ownprobe/resource.txt": b"captured-resource\n",
}
SEALS = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
CHILD = """import ctypes,errno,importlib,json,os,pathlib,signal,sqlite3,sys,time
source,data,assets,nonce=sys.argv[1:]
sys.path.insert(0,str(pathlib.Path(source)/'src'))
import ownprobe
db=pathlib.Path(data,'fixture.sqlite3')
marker=pathlib.Path(data,'graceful-marker')
def stop(signum,frame):
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    pathlib.Path(data,'drain-started').write_text('owned fixture drain')
    time.sleep(0.15)
    marker.write_text('owned fixture graceful completion')
    print(json.dumps({'drained':True,'signal':signum,'nonce':nonce}),flush=True)
    raise SystemExit(0)
signal.signal(signal.SIGTERM,stop)
pdeath=ctypes.c_int()
assert ctypes.CDLL(None).prctl(2,ctypes.byref(pdeath),0,0,0)==0
open_fds=[]
for name in os.listdir('/proc/self/fd'):
    try:
        os.fstat(int(name))
    except OSError:
        continue
    open_fds.append(int(name))
print(json.dumps({'pid':os.getpid(),'nonce':nonce,'source':ownprobe.__file__,
    'value':ownprobe.VALUE,'cwd':os.getcwd(),'db_canonical':str(db.resolve()),
    'asset_canonical':str(pathlib.Path(assets,'prepared.txt').resolve()),
    'site_loaded':'site' in sys.modules,'pdeath_signal':pdeath.value,
    'open_fd_numbers':sorted(open_fds),'environment_names':sorted(os.environ)}),flush=True)
command=sys.stdin.readline().strip()
if command=='exit7':
    raise SystemExit(7)
assert command=='inspect'
from ownprobe import late
with sqlite3.connect(db) as connection:
    connection.execute('CREATE TABLE IF NOT EXISTS fixture(marker TEXT)')
    connection.execute("INSERT INTO fixture VALUES ('latest-owned-data')")
    rows=connection.execute('SELECT marker FROM fixture').fetchall()
try:
    pathlib.Path(source,'src/ownprobe/resource.txt').write_text('host mutation')
    write_errno=None
except OSError as error:
    write_errno=error.errno
print(json.dumps({'late':late.VALUE,
    'resource':pathlib.Path(source,'src/ownprobe/resource.txt').read_text(),
    'asset':pathlib.Path(assets,'prepared.txt').read_text(),
    'db_canonical':str(db.resolve()),'rows':rows,'source_write_errno':write_errno,
    'nonce':nonce}),flush=True)
while True:
    time.sleep(0.05)
"""


def bounded_read(fd: int, *, line: bool = False) -> bytes:
    result = bytearray()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], max(0, deadline - time.monotonic()))
        if not ready:
            break
        chunk = os.read(fd, 1 if line else 4096)
        if not chunk:
            return bytes(result)
        result.extend(chunk)
        if len(result) > 4096:
            raise ValueError("owned channel exceeded 4096 bytes")
        if line and result.endswith(b"\n"):
            return bytes(result)
    raise TimeoutError("owned channel exceeded five seconds")


def owned_identity(pid: int, parent: int) -> tuple[int, int]:
    # Read only the directly reported self-owned child, never discover host processes.
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    identity = int(fields[1]), int(fields[19])
    if identity[0] != parent:
        raise ValueError("info PID is not the owned monitor's direct child")
    return identity


def main() -> None:
    result: dict[str, object] = {
        "profile": "Linux/bubblewrap0.11.1/systemCPython3.14/tiny trusted stdlib",
        "prototype_only": True,
        "production_tests_contracts_or_existing_evidence_modified": False,
        "private_live_venv_sdk_models_or_gpu_used": False,
        "bwrap_version": subprocess.check_output(
            ["/usr/bin/bwrap", "--version"], text=True
        ).strip(),
        "source_anchor": "/siro-release",
        "same_named_mappings": ["/usr read-only", "owned /tmp subtree read-write"],
        "pid_namespace": False,
        "source_capture_bounds_or_full_host_rights_verified": False,
        "runs": [],
    }
    runs = result["runs"]
    assert isinstance(runs, list)
    children: list[subprocess.Popen[bytes]] = []
    owned_fds: set[int] = set()
    command_handles: set[int] = set()
    fd_before = set(os.listdir("/proc/self/fd"))
    old_handler = signal.getsignal(signal.SIGTERM)
    try:
        with tempfile.TemporaryDirectory(prefix="siro-own-lifecycle-") as temporary:
            root = Path(temporary)
            result["owned_temporary_root"] = str(root)
            result["canonical_db_expected"] = str(root / "data/fixture.sqlite3")
            result["fixture_key_sha256"] = hashlib.sha256(
                os.fsencode((root / "data/fixture.sqlite3").resolve())
            ).hexdigest()
            for folder in (root / "data", root / "assets", root / "host-parent/selected"):
                folder.mkdir(parents=True)
            (root / "assets/prepared.txt").write_text("public-prepared-asset")
            for name, payload in SNAPSHOTS.items():
                file = root / "host-parent/selected" / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(payload)

            def close(fd: int) -> None:
                if fd in owned_fds:
                    os.close(fd)
                    owned_fds.remove(fd)

            def launch(kind: str) -> tuple[subprocess.Popen[bytes], dict[str, object], int | None]:
                read_info, write_info = os.pipe2(os.O_CLOEXEC)
                owned_fds.update((read_info, write_info))
                snapshots: list[int] = []
                args = [
                    "/usr/bin/bwrap",
                    "--unshare-user",
                    "--disable-userns",
                    "--assert-userns-disabled",
                    "--cap-drop",
                    "ALL",
                    "--die-with-parent",
                    "--info-fd",
                    str(write_info),
                    "--ro-bind",
                    "/usr",
                    "/usr",
                    "--symlink",
                    "usr/lib",
                    "/lib",
                    "--symlink",
                    "usr/lib64",
                    "/lib64",
                    "--proc",
                    "/proc",
                    "--dev",
                    "/dev",
                    "--bind",
                    str(root),
                    str(root),
                    "--size",
                    "1048576",
                    "--tmpfs",
                    "/siro-release",
                    "--dir",
                    "/siro-release/src/ownprobe",
                ]
                try:
                    for name, payload in SNAPSHOTS.items():
                        fd = os.memfd_create(
                            "public-lifecycle-snapshot", os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC
                        )
                        owned_fds.add(fd)
                        snapshots.append(fd)
                        assert os.write(fd, payload) == len(payload)
                        os.lseek(fd, 0, os.SEEK_SET)
                        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, SEALS)
                        assert fcntl.fcntl(fd, fcntl.F_GET_SEALS) == SEALS
                        args.extend(["--ro-bind-data", str(fd), "/siro-release/" + name])
                    if kind == "private-anchor-alias":
                        (root / "host-parent").rename(root / "captured-host-parent")
                        (root / "host-alias-before/src/ownprobe").mkdir(parents=True)
                        (root / "host-alias-before/src/ownprobe/__init__.py").write_text(
                            "VALUE='host-before-spawn-wrong'\n"
                        )
                        (root / "host-parent").symlink_to(
                            root / "host-alias-before", target_is_directory=True
                        )
                    if kind == "popen-missing":
                        args[0] = str(root / "missing-bwrap")
                    if kind == "setup-failure":
                        args.extend(["--ro-bind", str(root / "missing-mount"), "/missing-mount"])
                    args.extend(["--remount-ro", "/siro-release", "--chdir", str(root), "--"])
                    if kind == "exec-failure":
                        args.append("/usr/bin/missing-own-fixture-command")
                    else:
                        args.extend(
                            [
                                "/usr/bin/python3.14",
                                "-I",
                                "-S",
                                "-B",
                                "-c",
                                CHILD,
                                "/siro-release",
                                str(root / "data"),
                                str(root / "assets"),
                                kind,
                            ]
                        )
                    child = subprocess.Popen(
                        args,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        close_fds=True,
                        pass_fds=(*snapshots, write_info),
                        start_new_session=True,
                        cwd=root,
                        env={"LANG": "C.UTF-8"},
                    )
                    children.append(child)
                    close(write_info)
                    write_info = -1
                    raw = bounded_read(read_info)
                    close(read_info)
                    read_info = -1
                    info = json.loads(raw) if raw else None
                    if kind in ("setup-failure", "exec-failure"):
                        return child, {"info_document": info}, None
                    assert isinstance(info, dict) and type(info.get("child-pid")) is int
                    assert child.stdout is not None
                    ready = json.loads(bounded_read(child.stdout.fileno(), line=True))
                    pid = info["child-pid"]
                    assert ready["pid"] == pid and ready["nonce"] == kind
                    before = owned_identity(pid, child.pid)
                    pidfd = os.pidfd_open(pid)
                    owned_fds.add(pidfd)
                    command_handles.add(pidfd)
                    assert owned_identity(pid, child.pid) == before
                    return (
                        child,
                        {
                            "info_document": info,
                            "ready": ready,
                            "pidfd_bound": True,
                            "owned_parent_and_starttime": list(before),
                            "host_parent_alias_before_spawn": kind == "private-anchor-alias",
                        },
                        pidfd,
                    )
                finally:
                    for fd in snapshots:
                        close(fd)
                    close(read_info)
                    close(write_info)

            def complete(child: subprocess.Popen[bytes]) -> tuple[bytes, bytes]:
                output, error = child.communicate(timeout=5)
                assert child.poll() is not None
                return output, error

            for kind in (
                "private-anchor-alias",
                "wrapper-term",
                "repeated-wrapper-term",
                "monitor-term-negative",
                "child-exit7",
                "popen-missing",
                "setup-failure",
                "exec-failure",
            ):
                for marker in (root / "data/graceful-marker", root / "data/drain-started"):
                    marker.unlink(missing_ok=True)
                record: dict[str, object] = {"kind": kind}
                runs.append(record)
                try:
                    child, observed, pidfd = launch(kind)
                except FileNotFoundError as error:
                    assert kind == "popen-missing"
                    record.update(
                        status="PASS_EXPECTED_REFUSAL",
                        error=type(error).__name__,
                        no_child_started=True,
                    )
                    continue
                record.update(observed)
                if kind in ("setup-failure", "exec-failure"):
                    output, error = complete(child)
                    record.update(
                        status="PASS_EXPECTED_REFUSAL" if child.returncode == 1 else "FAIL",
                        exit_code=child.returncode,
                        stdout_empty=not output,
                        stderr=error.decode().strip(),
                        readiness_observed=False,
                        no_signal_to_unverified_pid=True,
                        joined=True,
                    )
                    continue
                assert pidfd is not None and child.stdin is not None and child.stdout is not None
                if kind == "child-exit7":
                    child.stdin.write(b"exit7\n")
                    child.stdin.flush()
                    output, error = complete(child)
                    record.update(
                        status="PASS" if child.returncode == 7 else "FAIL",
                        exit_code=child.returncode,
                        stderr_empty=not error,
                        stdout_after_ready=output.decode(),
                        actual_command_exit_observed_by_pidfd=bool(
                            select.select([pidfd], [], [], 0)[0]
                        ),
                        joined=True,
                    )
                    close(pidfd)
                    command_handles.remove(pidfd)
                    continue
                if kind == "private-anchor-alias":
                    (root / "host-parent").unlink()
                    (root / "host-alias/src/ownprobe").mkdir(parents=True)
                    (root / "host-alias/src/ownprobe/late.py").write_text(
                        "VALUE='host-alias-wrong'\n"
                    )
                    (root / "host-parent").symlink_to(root / "host-alias", target_is_directory=True)
                    record["host_selected_parent_replaced_by_symlink"] = True
                child.stdin.write(b"inspect\n")
                child.stdin.flush()
                inspected = json.loads(bounded_read(child.stdout.fileno(), line=True))
                record["inspection"] = inspected
                ready = observed["ready"]
                assert isinstance(ready, dict)
                record["projection_checks"] = {
                    "source_anchor": ready["source"] == "/siro-release/src/ownprobe/__init__.py",
                    "cwd_same_canonical": ready["cwd"] == str(root),
                    "db_same_canonical": ready["db_canonical"]
                    == inspected["db_canonical"]
                    == str(root / "data/fixture.sqlite3"),
                    "asset_same_canonical": ready["asset_canonical"]
                    == str(root / "assets/prepared.txt"),
                    "late_and_resource_frozen": inspected["late"] == "captured-late"
                    and inspected["resource"] == "captured-resource\n",
                    "asset_and_rw_db": inspected["asset"] == "public-prepared-asset"
                    and ["latest-owned-data"] in inspected["rows"],
                    "source_erofs": inspected["source_write_errno"] == errno.EROFS,
                    "no_site_or_private_env": not ready["site_loaded"]
                    and set(ready["environment_names"]) <= {"LANG", "LC_CTYPE"},
                    "only_child_stdio_fds": ready["open_fd_numbers"] == [0, 1, 2],
                }
                signal_counts = {"requests": 0, "forwarded": 0}

                def wrapper_term(
                    signum: int,
                    frame: object,
                    *,
                    counts: dict[str, int] = signal_counts,
                    target: int = pidfd,
                ) -> None:
                    counts["requests"] += 1
                    if not counts["forwarded"]:
                        signal.pidfd_send_signal(target, signal.SIGTERM)
                        counts["forwarded"] = 1

                if kind == "monitor-term-negative":
                    child.terminate()
                    child.wait(timeout=5)
                    # A killed monitor cannot reap/drain its child; do not wait forever
                    # for inherited stdout, or treat monitor exit as child shutdown.
                    exited, _, _ = select.select([pidfd], [], [], 0.25)
                    record["command_alive_after_monitor_term"] = not exited
                    record["forced_command_cleanup"] = not exited
                    if not exited:
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        exited, _, _ = select.select([pidfd], [], [], 5)
                        assert exited
                else:
                    signal.signal(signal.SIGTERM, wrapper_term)
                    for _ in range(3 if kind == "repeated-wrapper-term" else 1):
                        os.kill(os.getpid(), signal.SIGTERM)
                        time.sleep(0.02)
                output, error = complete(child)
                signal.signal(signal.SIGTERM, old_handler)
                marker = (root / "data/graceful-marker").exists()
                record.update(
                    exit_code=child.returncode,
                    stderr_empty=not error,
                    graceful_marker=marker,
                    termination_output=output.decode().strip(),
                    wrapper_signal_counts=signal_counts,
                    joined=True,
                )
                gone = False
                for _ in range(100):
                    try:
                        signal.pidfd_send_signal(pidfd, 0)
                    except ProcessLookupError:
                        gone = True
                        break
                    time.sleep(0.01)
                record["actual_command_gone"] = gone
                projection = record["projection_checks"]
                assert isinstance(projection, dict)
                expected = (
                    child.returncode == -15 and not marker
                    if kind == "monitor-term-negative"
                    else child.returncode == 0 and marker
                )
                record["status"] = (
                    "PASS_EXPECTED_COUNTEREXAMPLE"
                    if kind == "monitor-term-negative" and expected and gone
                    else "PASS"
                    if expected and gone and all(projection.values())
                    else "FAIL"
                )
                close(pidfd)
                command_handles.remove(pidfd)
            result["children_joined"] = all(child.poll() is not None for child in children)
            result["unexpected_failures"] = sum(r["status"] == "FAIL" for r in runs)
        result["temporary_root_removed"] = not root.exists()
    except BaseException as error:
        result["status"] = "UNKNOWN_INCOMPLETE"
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        signal.signal(signal.SIGTERM, old_handler)
        for pidfd in tuple(command_handles):
            with suppress(ProcessLookupError):
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            select.select([pidfd], [], [], 5)
        for child in children:
            if child.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    stream.close()
        for fd in tuple(owned_fds):
            with suppress(OSError):
                os.close(fd)
            owned_fds.remove(fd)
        result["all_owned_children_joined_finally"] = all(
            child.poll() is not None for child in children
        )
        result["owned_fd_set_empty"] = not owned_fds
        result["process_fd_set_restored"] = set(os.listdir("/proc/self/fd")) == fd_before
        result["parent_term_handler_restored"] = signal.getsignal(signal.SIGTERM) == old_handler
        result["temporary_root_removed_finally"] = not root.exists() if "root" in locals() else True
    if "status" not in result:
        result["status"] = "PRIMITIVES_OBSERVED" if result["unexpected_failures"] == 0 else "FAILED"
    result["not_run"] = [
        "bounded verified source capture",
        "full Gateway/SDK/runtime",
        "D50 lease/key actual integration",
        "complete host/devices/permissions compatibility",
        "PID namespace/init profile",
        "hostile same-UID startup PID races",
        "old/unmanaged writer absence",
        "approved maintenance handoff",
        "deployment or private product acceptance",
    ]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
