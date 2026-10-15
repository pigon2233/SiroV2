"""Owned actual-main / Rust / HTTP probe; UI actions are performed by the caller."""

from __future__ import annotations

import hashlib
import json
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests/integration"))
from test_release_source_process import (  # noqa: E402
    environment,
    port_at,
    prepared_project,
    source_bundle,
)

NOTES = (
    "# Synthetic owner task\n- [ ] Review a synthetic note\n"
    "- [x] Already checked\nTODO: Keep provenance\n"
)
LATER = "TODO: This task must stay unapproved across restart\n"
CORRECTED = "# Corrected synthetic source\nFIXME: Review this changed note\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_hashes(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): sha(path.read_bytes())
        for path in sorted(directory.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def announce(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


class Probe:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="d57-product-")
        self.root = Path(self.temporary.name)
        self.launcher = prepared_project(self.root)
        source_before = source_hashes(ROOT / "src")
        self.bundle = source_bundle(self.root, "D57-product-fixture")
        assert source_hashes(ROOT / "src") == source_before
        (self.root / "synthetic-account").mkdir()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "notes.md").write_text(NOTES)
        (self.workspace / "later.md").write_text(LATER)
        self.port = port_at()
        self.origin = f"http://127.0.0.1:{self.port}"
        self.runtime = ROOT / "target/debug/siro-runtime"
        assert self.runtime.is_file()
        self.env = environment(self.root, self.port)
        for key in ("SIRO_RELEASE_ROOT", "SIRO_RELEASE_SIGNING_KEY"):
            self.env.pop(key, None)
        self.env.update(
            SIRO_RUNTIME_BINARY=str(self.runtime),
            SIRO_WORKSPACE_ENABLED="1",
            SIRO_GOAL_TASKS_ENABLED="1",
            SIRO_WORKSPACE_DIR=str(self.workspace),
            SIRO_MODEL_RETRY_ENABLED="0",
            SIRO_CONTEXT_MAX_BYTES="0",
            PYTHONPATH=str(self.bundle / "src"),
            TMPDIR=str(self.root),
        )
        self.process: subprocess.Popen[bytes] | None = None
        self.log = None
        self.token: str | None = None
        self.runtime_pid: int | None = None
        self.runtime_dir: Path | None = None
        self.cycle = 0
        self.first_id: str | None = None
        self.second_id: str | None = None
        self.corrected_id: str | None = None
        self.receipt: dict[str, object] = {
            "started_utc": datetime.now(UTC).isoformat(),
            "reproduction_script_sha256": sha(Path(__file__).read_bytes()),
            "origin": self.origin,
            "baseline_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "scope": "actual default candidate main; public copy; synthetic account and renderer",
            "runtime_binary_sha256": sha(self.runtime.read_bytes()),
            "host_source_sha256": source_before,
            "copied_source_sha256": {
                str(path.relative_to(self.bundle)): sha(path.read_bytes())
                for path in sorted((self.bundle / "src").rglob("*"))
                if path.is_file()
            },
            "cycles": [],
            "checkpoints": [],
            "instrumentation": (
                "Existing source_bundle helper only remaps pwd account and records imported "
                "source origins. Gateway/Core/owner/workspace/model behavior remains real; "
                "no signed release is selected."
            ),
            "live_8026_touched": False,
            "private_data_used": False,
            "provider_or_tts_requests": False,
        }

    def save(self) -> None:
        (OUT / "RESULTS.json").write_text(json.dumps(self.receipt, indent=2) + "\n")

    def request(self, path: str, method: str = "GET", body: object = None) -> tuple[int, object]:
        headers = {"Origin": self.origin, "Content-Type": "application/json"}
        if path.startswith("/v1/") and path != "/v1/session":
            if self.token is None:
                _, session = self.request("/v1/session", "POST", {})
                assert isinstance(session, dict)
                self.token = session["token"]
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            self.origin + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            result = json.load(response)
            if path.startswith("/v1/goal-tasks/"):
                assert response.headers.get("Cache-Control") == "no-store"
            return response.status, result

    def snapshot(self, owner: str = "browser") -> dict:
        status, value = self.request(f"/v1/goal-tasks/{owner}")
        assert status == 200 and isinstance(value, dict)
        return value

    def reads(self) -> int:
        assert self.runtime_dir is not None
        with sqlite3.connect(self.runtime_dir / "ledger.sqlite3") as database:
            return database.execute(
                "SELECT count(*) FROM runtime_actions WHERE capability='filesystem.read'"
            ).fetchone()[0]

    def start(self) -> None:
        self.cycle += 1
        self.token = None
        self.log = (OUT / f"cycle-{self.cycle}.log").open("w")
        self.process = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), "-B", str(self.launcher)],
            env=self.env,
            stdout=self.log,
            stderr=self.log,
            start_new_session=True,
        )
        deadline = time.monotonic() + 20
        while True:
            assert self.process.poll() is None, (OUT / f"cycle-{self.cycle}.log").read_text()
            try:
                status, health = self.request("/health/ready")
                if status == 200 and health == {"state": "healthy"}:
                    break
            except (urllib.error.URLError, TimeoutError):
                pass
            assert time.monotonic() < deadline
            time.sleep(0.05)
        children = (
            Path(f"/proc/{self.process.pid}/task/{self.process.pid}/children").read_text().split()
        )
        assert len(children) == 1, children
        self.runtime_pid = int(children[0])
        assert Path(f"/proc/{self.runtime_pid}/exe").resolve() == self.runtime.resolve()
        runtime_env = dict(
            item.split(b"=", 1)
            for item in Path(f"/proc/{self.runtime_pid}/environ").read_bytes().split(b"\0")
            if b"=" in item
        )
        self.runtime_dir = Path(runtime_env[b"SIRO_RUNTIME_DB"].decode()).parent
        assert self.runtime_dir.is_relative_to(self.root)
        assert runtime_env[b"SIRO_RUNTIME_ROOTS"].decode() == str(self.workspace)
        assert not any(b"MODEL" in key or b"API_KEY" in key for key in runtime_env)
        loaded = json.loads((self.root / "observed-source.json").read_text())
        assert loaded["gateway_file"] == str(
            self.bundle / "src/siro/services/presentation/gateway.py"
        )
        assert loaded["signing_key_present"] is False
        with urllib.request.urlopen(self.origin + "/", timeout=3) as response:
            index = response.read(1024 * 1024).decode()
        expected = (self.bundle / "src/siro/services/presentation/static/index.html").read_text()
        served_script = index.split("<script>", 1)[1].split("</script>", 1)[0]
        assert served_script == expected.split("<script>", 1)[1].split("</script>", 1)[0]
        status, runtime = self.request("/v1/runtime")
        assert status == 200
        assert runtime["runtime_profile"] == "candidate"
        assert runtime["features"]["workspace"]["available"] is True
        assert runtime["features"]["goal_tasks"]["enabled"] is True
        assert runtime["features"]["summary"]["enabled"] is False
        assert runtime["features"]["memory_organization"]["enabled"] is False
        assert self.reads() == 0
        self.receipt["cycles"].append(
            {
                "cycle": self.cycle,
                "started_utc": datetime.now(UTC).isoformat(),
                "pid": self.process.pid,
                "runtime_pid": self.runtime_pid,
                "runtime_executable": str(self.runtime),
                "loaded": loaded,
                "served_html_sha256": sha(index.encode()),
                "served_script_sha256": sha(served_script.encode()),
                "served_script_matches_copied_source": True,
                "startup_reads": 0,
                "shutdown": "NOT_YET_VERIFIED",
            }
        )
        self.save()
        announce({"ready": True, "cycle": self.cycle, "url": self.origin})

    def stop(self) -> None:
        if self.process is None:
            return
        process = self.process
        if process.poll() is None:
            process.terminate()
        code = process.wait(timeout=10)
        self.log.close()
        log = (OUT / f"cycle-{self.cycle}.log").read_text()
        assert code in (0, -signal.SIGTERM), code
        assert "Application shutdown complete." in log
        assert "Traceback" not in log and "Task was destroyed" not in log
        assert self.runtime_pid is not None and not Path(f"/proc/{self.runtime_pid}").exists()
        assert self.runtime_dir is not None and not self.runtime_dir.exists()
        self.receipt["cycles"][-1].update(
            {"shutdown": "PASS", "exit_code": code, "joined": True, "runtime_removed": True}
        )
        self.process = None
        self.save()

    def checkpoint(self, name: str) -> dict:
        value = self.snapshot()
        goals = value["goals"]
        if name == "first_proposed":
            assert len(goals) == 1 and goals[0]["state"] == "proposed"
            self.first_id = goals[0]["goal_id"]
            assert goals[0]["steps_used"] == 0 and self.reads() == 0
        elif name == "reopened_proposed":
            assert len(goals) == 1 and goals[0]["goal_id"] == self.first_id
            assert goals[0]["state"] == "proposed" and goals[0]["steps_used"] == 0
            assert self.reads() == 0
        elif name == "first_completed":
            first = next(goal for goal in goals if goal["goal_id"] == self.first_id)
            assert first["state"] == "completed" and first["steps_used"] == 1
            item = first["task"]["observations"][0]
            assert item["sha256"] == sha(NOTES.encode())
            assert item["matches"] == [
                {"line": 2, "text": "- [ ] Review a synthetic note"},
                {"line": 4, "text": "TODO: Keep provenance"},
            ]
            assert item["read_at"] and first["task"]["approved_at"]
            assert self.reads() == 1
        elif name == "second_proposed":
            second = next(goal for goal in goals if goal["goal_id"] != self.first_id)
            assert second["state"] == "proposed" and second["steps_used"] == 0
            self.second_id = second["goal_id"]
            assert self.reads() == 1
        elif name == "third_reopen":
            assert self.cycle == 3 and len(goals) == 2
            first = next(goal for goal in goals if goal["goal_id"] == self.first_id)
            second = next(goal for goal in goals if goal["goal_id"] == self.second_id)
            assert first["state"] == "completed" and first["steps_used"] == 1
            assert first["task"]["observations"][0]["sha256"] == sha(NOTES.encode())
            assert second["state"] == "proposed" and second["steps_used"] == 0
            assert self.reads() == 0
        else:
            raise ValueError("unknown checkpoint")
        result = {
            "name": name,
            "cycle": self.cycle,
            "snapshot": value,
            "runtime_reads": self.reads(),
        }
        self.receipt["checkpoints"].append(result)
        self.save()
        return result

    def correction(self) -> dict:
        (self.workspace / "notes.md").write_text(CORRECTED)
        before = self.snapshot()
        first = next(goal for goal in before["goals"] if goal["goal_id"] == self.first_id)
        assert first["task"]["observations"][0]["sha256"] == sha(NOTES.encode())
        status, proposed = self.request("/v1/goal-tasks/browser", "POST", {"paths": ["notes.md"]})
        assert status == 200 and isinstance(proposed, dict)
        goal = proposed["goal"]
        self.corrected_id = goal["goal_id"]
        status, approved = self.request(
            f"/v1/goal-tasks/browser/{self.corrected_id}/approve",
            "POST",
            {"revision": goal["revision"]},
        )
        assert status == 200 and isinstance(approved, dict)
        deadline = time.monotonic() + 5
        while True:
            current = next(
                goal for goal in self.snapshot()["goals"] if goal["goal_id"] == self.corrected_id
            )
            if current["state"] == "completed":
                break
            assert time.monotonic() < deadline
            time.sleep(0.02)
        item = current["task"]["observations"][0]
        assert item["sha256"] == sha(CORRECTED.encode())
        assert item["matches"] == [{"line": 2, "text": "FIXME: Review this changed note"}]
        assert self.reads() == 1
        other = self.snapshot("other-synthetic-session")
        assert other["goals"] == [] and other["active_goal_id"] is None
        other_status, denied = self.request(
            f"/v1/goal-tasks/other-synthetic-session/{self.second_id}/approve",
            "POST",
            {"revision": 1},
        )
        assert other_status == 404
        revision_status, revision_denied = self.request(
            f"/v1/goal-tasks/browser/{self.second_id}/approve", "POST", {"revision": 999}
        )
        assert revision_status == 409
        assert self.reads() == 1
        result = {
            "old_observation_retained": True,
            "explicit_corrected_observation": current,
            "other_session": other,
            "other_session_status": other_status,
            "other_session_denied": denied,
            "wrong_revision_status": revision_status,
            "wrong_revision_denied": revision_denied,
            "extra_reads": 1,
        }
        self.receipt["correction"] = result
        self.save()
        return result

    def close(self) -> None:
        try:
            self.stop()
        finally:
            if self.process is not None and self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=3)
                self.receipt["forced_cleanup"] = True
            path = self.root
            if self.bundle.exists():
                assert source_hashes(self.bundle) == self.receipt["copied_source_sha256"]
                self.receipt["copied_package_unchanged"] = True
            self.temporary.cleanup()
            self.receipt["temporary_removed"] = not path.exists()
            self.receipt["closed_utc"] = datetime.now(UTC).isoformat()
            self.save()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    probe = Probe()
    try:
        probe.start()
        for line in sys.stdin:
            command = json.loads(line)
            if command["command"] == "restart":
                probe.stop()
                probe.start()
            elif command["command"] == "checkpoint":
                announce(probe.checkpoint(command["name"]))
            elif command["command"] == "correction":
                announce(probe.correction())
            elif command["command"] == "finish":
                assert probe.cycle == 3
                probe.close()
                announce({"finished": True, "temporary_removed": True})
                return
            else:
                raise ValueError("unknown command")
    finally:
        probe.close()


if __name__ == "__main__":
    main()
