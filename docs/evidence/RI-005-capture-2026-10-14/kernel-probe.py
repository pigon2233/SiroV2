"""Own tiny Linux fixture: immutable projection is separate from graceful stop."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import mmap
import os
import select
import signal
import subprocess
import tempfile
import time
from contextlib import suppress
from pathlib import Path

SNAPSHOTS = {
    "src/siro/__init__.py": b"VALUE='approved-before'\n",
    "src/siro/late.py": b"VALUE='approved-late'\n",
    "src/siro/resource.txt": b"approved-resource\n",
}
SEALS = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
CHILD = """import errno,fcntl,importlib,importlib.resources,json,os,pathlib,signal,sys
source,data,assets,deps,key_fd,key_dev,key_ino,mode=sys.argv[1:]
sys.path[:0]=[str(pathlib.Path(source)/'src'),deps]
import siro
same_key_fd=False
try:
    st=os.fstat(int(key_fd))
    same_key_fd=(st.st_dev,st.st_ino)==(int(key_dev),int(key_ino))
except OSError:
    pass
record={
    'pid':os.getpid(),'cwd':os.getcwd(),
    'signing_key_present':'SIRO_RELEASE_SIGNING_KEY' in os.environ,
    'unrelated_key_fd_present':same_key_fd,'value':siro.VALUE,
    'source':siro.__file__,'site_imported':'site' in sys.modules,
    'sitecustomize_imported':'sitecustomize' in sys.modules}
def terminate(signum,frame):
    pathlib.Path(data,'graceful-marker').write_text('joined-synthetic-cleanup')
    print(json.dumps({'termination_handler':signum}),flush=True)
    raise SystemExit(0)
signal.signal(signal.SIGTERM,terminate)
print(json.dumps(record),flush=True)
command=sys.stdin.readline().strip()
if mode=='cancel':
    raise AssertionError('unexpected input')
assert command=='continue'
from siro import late
import public_dependency
record['late_value']=late.VALUE
record['dependency']=public_dependency.VALUE
record['resource']=importlib.resources.files(siro).joinpath('resource.txt').read_text()
try:
    importlib.import_module('siro.host_injected')
    record['host_injected_module']=True
except ModuleNotFoundError:
    record['host_injected_module']=False
try:
    pathlib.Path(source,'src/siro/resource.txt').write_text('mutation')
    record['source_write_errno']=None
except OSError as exc:
    record['source_write_errno']=exc.errno
record['asset']=pathlib.Path(assets,'prepared.txt').read_text()
pathlib.Path(data,'latest.txt').write_text('new-latest')
record['data_write']=pathlib.Path(data,'latest.txt').read_text()
record['pth_executed']=pathlib.Path(data,'pth-executed').exists()
record['sitecustomize_executed']=pathlib.Path(data,'sitecustomize-executed').exists()
print(json.dumps(record),flush=True)
"""


def main() -> None:
    results: dict[str, object] = {
        "prototype_only": True,
        "production_or_private_data_used": False,
        "bwrap_version": subprocess.check_output(
            ["/usr/bin/bwrap", "--version"], text=True
        ).strip(),
    }
    checks: dict[str, bool] = {}
    runs: list[dict[str, object]] = []
    results["checks"] = checks
    results["runs"] = runs
    children: list[subprocess.Popen[str]] = []
    descriptors: list[int] = []
    try:
        with tempfile.TemporaryDirectory(prefix="siro-sealed-source-probe-") as temporary:
            root = Path(temporary)
            source, data, assets = root / "approved", root / "data", root / "assets"
            dependencies = root / ".venv/lib/python3.14/site-packages"
            for directory in (data, assets, dependencies):
                directory.mkdir(parents=True)
            (assets / "prepared.txt").write_text("public-prepared-asset")
            (dependencies / "public_dependency.py").write_text(
                "VALUE='synthetic-allowed-dependency'\n"
            )
            (dependencies / "siro").mkdir()
            (dependencies / "siro/__init__.py").write_text("VALUE='wrong-host-fallback'\n")
            (dependencies / "siro/host_injected.py").write_text("VALUE='must-not-load'\n")
            (dependencies / "sitecustomize.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(data / 'sitecustomize-executed')!r}).write_text('bad')\n"
            )
            (dependencies / "editable-host.pth").write_text(
                f"import pathlib; pathlib.Path({str(data / 'pth-executed')!r}).write_text('bad')\n"
            )
            for name, payload in SNAPSHOTS.items():
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            digest = hashlib.sha256()
            for name, payload in sorted(SNAPSHOTS.items()):
                digest.update(name.encode())
                digest.update(payload)
            # Historical v1 fingerprint is observational, not an exact identity certificate.
            results["captured_complete_v1_digest"] = digest.hexdigest()
            read_key, write_key = os.pipe()
            descriptors.extend((read_key, write_key))
            os.write(write_key, b"synthetic-key-must-not-reach-child")
            os.set_inheritable(read_key, True)
            key_info = os.fstat(read_key)

            def launch(mode: str) -> tuple[subprocess.Popen[str], dict[str, object]]:
                owned: list[int] = []
                arguments = [
                    "/usr/bin/bwrap",
                    "--unshare-user",
                    "--disable-userns",
                    "--assert-userns-disabled",
                    "--cap-drop",
                    "ALL",
                    "--die-with-parent",
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
                    str(source),
                    "--dir",
                    str(source / "src/siro"),
                ]
                for name, payload in SNAPSHOTS.items():
                    descriptor = os.memfd_create(
                        "siro-public-snapshot", os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC
                    )
                    owned.append(descriptor)
                    descriptors.append(descriptor)
                    os.write(descriptor, payload)
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, SEALS)
                    assert fcntl.fcntl(descriptor, fcntl.F_GET_SEALS) == SEALS
                    for operation in ("write", "truncate", "mmap-write"):
                        try:
                            if operation == "write":
                                os.write(descriptor, b"x")
                            elif operation == "truncate":
                                os.ftruncate(descriptor, len(payload) + 1)
                            else:
                                mmap.mmap(descriptor, len(payload), access=mmap.ACCESS_WRITE)
                        except OSError as error:
                            assert error.errno in (errno.EPERM, errno.EACCES)
                        else:
                            raise AssertionError("sealed fd mutated")
                    arguments.extend(["--ro-bind-data", str(descriptor), str(source / name)])
                arguments.extend(
                    [
                        "--remount-ro",
                        str(source),
                        "--chdir",
                        str(root),
                        "--",
                        "/usr/bin/python3.14",
                        "-I",
                        "-S",
                        "-B",
                        "-c",
                        CHILD,
                        str(source),
                        str(data),
                        str(assets),
                        str(dependencies),
                        str(read_key),
                        str(key_info.st_dev),
                        str(key_info.st_ino),
                        mode,
                    ]
                )
                child = subprocess.Popen(
                    arguments,
                    cwd=root,
                    env={"LANG": "C.UTF-8", "SIRO_PUBLIC_FIXTURE": "1"},
                    pass_fds=tuple(owned),
                    close_fds=True,
                    start_new_session=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                children.append(child)
                assert child.stdout is not None and child.stdin is not None
                readable, _, _ = select.select([child.stdout], [], [], 10)
                if not readable:
                    raise AssertionError("child readiness timeout")
                line = child.stdout.readline()
                if not line:
                    child.wait(timeout=5)
                    assert child.stderr is not None
                    raise AssertionError("bwrap refused " + child.stderr.read())
                observed = json.loads(line)
                for descriptor in owned:
                    os.close(descriptor)
                    descriptors.remove(descriptor)
                return child, observed

            child, observed = launch("normal")
            for name in SNAPSHOTS:
                (source / name).write_text("same-uid-host-after-capture")
            (source / "src/siro/host_injected.py").write_text("must not become visible")
            assert child.stdin is not None
            child.stdin.write("continue\n")
            child.stdin.flush()
            output, error = child.communicate(timeout=10)
            final = json.loads(output)
            runs.append(
                {
                    "kind": "frozen-byte-data-assets-compatibility",
                    "exit_code": child.returncode,
                    "stderr_empty": not error,
                    "before": observed,
                    "after": final,
                    "actual_child_gone": not Path("/proc", str(observed["pid"])).exists(),
                }
            )
            checks.update(
                source_and_late_import_frozen=(
                    final["value"] == "approved-before" and final["late_value"] == "approved-late"
                ),
                resource_frozen=final["resource"] == "approved-resource\n",
                whole_tree_hides_host_injection=not final["host_injected_module"],
                snapshot_readonly=final["source_write_errno"] == errno.EROFS,
                cwd_data_asset_semantics=(
                    final["cwd"] == str(root)
                    and final["data_write"] == "new-latest"
                    and final["asset"] == "public-prepared-asset"
                ),
                parent_fds_closed_before_child_reads=True,
                only_allowed_dependency_without_site_hooks=(
                    final["dependency"] == "synthetic-allowed-dependency"
                    and not final["pth_executed"]
                    and not final["sitecustomize_executed"]
                    and not final["site_imported"]
                ),
                key_env_and_unrelated_fd_absent=(
                    not final["signing_key_present"] and not final["unrelated_key_fd_present"]
                ),
                fd_seals_write_grow_shrink_fixed=True,
            )
            child, observed = launch("cancel")
            child.terminate()
            output, error = child.communicate(timeout=10)
            for _attempt in range(100):
                if not Path("/proc", str(observed["pid"])).exists():
                    break
                time.sleep(0.01)
            runs.append(
                {
                    "kind": "main-pid-term",
                    "exit_code": child.returncode,
                    "stdout_after_term": output.strip(),
                    "stderr_empty": not error,
                    "actual_child_gone": not Path("/proc", str(observed["pid"])).exists(),
                    "graceful_marker": (data / "graceful-marker").exists(),
                }
            )
            checks["main_pid_term_preserves_graceful_shutdown"] = (
                data / "graceful-marker"
            ).exists()
            child, observed = launch("cancel")
            os.kill(int(observed["pid"]), signal.SIGTERM)
            output, error = child.communicate(timeout=10)
            runs.append(
                {
                    "kind": "owned-actual-child-term",
                    "exit_code": child.returncode,
                    "termination_ack": json.loads(output),
                    "stderr_empty": not error,
                    "actual_child_gone": not Path("/proc", str(observed["pid"])).exists(),
                    "graceful_marker": (data / "graceful-marker").exists(),
                }
            )
            checks["owned_actual_child_term_joins_graceful_shutdown"] = (
                child.returncode == 0 and (data / "graceful-marker").exists()
            )
            results["children_joined"] = all(child.poll() is not None for child in children)
        results["temporary_root_removed"] = not root.exists()
    finally:
        for child in children:
            if child.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)
        for descriptor in descriptors:
            with suppress(OSError):
                os.close(descriptor)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
