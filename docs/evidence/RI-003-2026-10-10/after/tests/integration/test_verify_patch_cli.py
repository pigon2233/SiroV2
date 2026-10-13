from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest
from test_isolated_patch_verification import project, proposal, real_profile

from siro.core.evolution import PatchProposal, VerificationReport


def run_cli(root: Path, path: Path) -> subprocess.CompletedProcess[str]:
    repository = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [sys.executable, "-m", "siro.cli", "verify-patch", str(path), "--project-root", str(root)],
        env={"PATH": os.defpath, "PYTHONPATH": str(repository / "src")},
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.mark.parametrize("value,code,status", [(2, 0, "passed"), (3, 1, "failed_checks")])
@real_profile
def test_actual_owner_cli(tmp_path: Path, value: int, code: int, status: str) -> None:
    root = project(tmp_path)
    path = tmp_path / "proposal.json"
    path.write_text(proposal(new=f"VALUE = {value}\n").model_dump_json())
    result = run_cli(root, path)
    assert result.returncode == code, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == status and payload["workspace_removed"]
    assert (root / "src/value.py").read_text() == "VALUE = 1\n"


@pytest.mark.parametrize("kind", ["invalid_json", "oversized", "symlink", "hardlink", "missing"])
def test_cli_rejects_input_without_printing_raw_payload(tmp_path: Path, kind: str) -> None:
    root = project(tmp_path)
    path = tmp_path / "proposal.json"
    path.write_text("SYNTHETIC-PRIVATE-CANARY")
    if kind == "oversized":
        path.write_bytes(b"SYNTHETIC-PRIVATE-CANARY" + b"x" * (4 * 1024 * 1024))
    elif kind in {"symlink", "hardlink"}:
        original = tmp_path / "original"
        path.rename(original)
        if kind == "symlink":
            path.symlink_to(original)
        else:
            os.link(original, path)
    elif kind == "missing":
        path.unlink()
    result = run_cli(root, path)
    assert result.returncode == 2, result.stderr + result.stdout
    assert "SYNTHETIC-PRIVATE-CANARY" not in result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "rejected_input"


def test_cli_signal_after_completed_task_cannot_print_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from siro import cli
    from siro.services.tools import patch_verification

    root = project(tmp_path)
    path = tmp_path / "proposal.json"
    path.write_text(proposal().model_dump_json())

    async def completed(
        root: Path, candidate: PatchProposal, *, profile: str
    ) -> VerificationReport:
        return VerificationReport(candidate.proposal_id, "passed", ("src/value.py",), (), True)

    original_run = asyncio.run
    previous_handler = signal.getsignal(signal.SIGINT)

    def finish_with_interrupt(
        coroutine: Coroutine[Any, Any, VerificationReport],
    ) -> VerificationReport:
        report = original_run(coroutine)
        # Verification and its cleanup have finished; CLI handler is still active.
        signal.raise_signal(signal.SIGINT)
        return report

    monkeypatch.setattr(patch_verification, "verify_isolated_patch", completed)
    monkeypatch.setattr(asyncio, "run", finish_with_interrupt)
    assert cli.main(["verify-patch", str(path), "--project-root", str(root)]) == 130
    assert not capsys.readouterr().out
    assert signal.getsignal(signal.SIGINT) == previous_handler


@real_profile
@pytest.mark.parametrize("interruptions", [1, 2])
def test_actual_cli_sigint_reaps_owned_namespace_and_workspace(
    tmp_path: Path, interruptions: int
) -> None:
    root = project(tmp_path)
    path = tmp_path / "proposal.json"
    path.write_text(proposal(new="import time\ntime.sleep(30)\nVALUE=2\n").model_dump_json())
    temporary = tmp_path / "workspaces"
    temporary.mkdir()
    repository = Path(__file__).resolve().parents[2]
    process = subprocess.Popen(
        [sys.executable, "-m", "siro.cli", "verify-patch", str(path), "--project-root", str(root)],
        env={"PATH": os.defpath, "PYTHONPATH": str(repository / "src"), "TMPDIR": str(temporary)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    owned: set[int] = set()
    handles: dict[int, int] = {}
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and process.poll() is None:
            children = Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().split()
            ready = False
            for value in children:
                child = int(value)
                try:
                    command = Path(f"/proc/{child}/cmdline").read_bytes()
                except FileNotFoundError:
                    continue
                if b"bwrap" in command and b"--probe" not in command:
                    owned.add(child)
                    pending = [child]
                    while pending:
                        parent = pending.pop()
                        for p in Path(f"/proc/{parent}/task/{parent}/children").read_text().split():
                            pid = int(p)
                            if pid not in owned:
                                owned.add(pid)
                                pending.append(pid)
                    handles.update({pid: os.pidfd_open(pid) for pid in owned})
                    ready = True
            if ready:
                break
            time.sleep(0.01)
        assert owned, "CLI never reached the owned candidate namespace"
        process.send_signal(signal.SIGINT)
        if interruptions == 2:
            time.sleep(0.01)
            process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=8)
        assert process.returncode == 130, stdout + stderr
        assert not list(temporary.iterdir())
        for pid in owned:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
        assert (root / "src/value.py").read_text() == "VALUE = 1\n"
    finally:
        for handle in handles.values():
            try:
                signal.pidfd_send_signal(handle, signal.SIGKILL)
            except ProcessLookupError:
                pass
            finally:
                os.close(handle)
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=6)
