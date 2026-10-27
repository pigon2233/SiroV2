"""R11 isolated drill: cold start/stop/restart, unreachable cloud, child fault, soak.

Runs the checked-out source against a throwaway data dir and ephemeral port; it never
touches the live SIRO instance. Usage: r11_drill.py OUT_DIR [soak_hours]
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def rss_kib(pid: int) -> int:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return 0


def tree(pid: int) -> list[int]:
    out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout
    kids = [int(x) for x in out.split()]
    return kids + [g for k in kids for g in tree(k)]


class Gateway:
    def __init__(self, data: Path, out: Path, extra: dict[str, str] | None = None) -> None:
        self.port = free_port()
        env = {k: v for k, v in os.environ.items() if not k.startswith("SIRO_")}
        env.update(
            PYTHONPATH=str(ROOT / "src"),
            SIRO_DATA_DIR=str(data),
            SIRO_GATEWAY_PORT=str(self.port),
            SIRO_OLLAMA_MODEL="synthetic-not-called",
            SIRO_CONTEXT_TOKEN_BUDGET_ENABLED="0",
            SIRO_WORKSPACE_ENABLED="0",
            SIRO_BROWSER_SESSION_ENABLED="0",
            **(extra or {}),
        )
        self.log = (out / f"gw-{time.monotonic_ns()}.log").open("w")
        self.proc = subprocess.Popen(
            [sys.executable, "-c", "from siro.services.presentation.gateway import main; main()"],
            env=env, stdout=self.log, stderr=self.log, cwd=ROOT,
        )

    def ready(self, timeout: float = 30) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end and self.proc.poll() is None:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/health/ready", timeout=1
                ) as r:
                    return bool(json.load(r).get("state") == "healthy")
            except Exception:
                time.sleep(0.2)
        return False

    def stop(self) -> int:
        self.proc.send_signal(signal.SIGTERM)
        try:
            return self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
            return 999


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hours = float(sys.argv[2]) if len(sys.argv) > 2 else 0
    results: dict[str, object] = {}
    data = Path(tempfile.mkdtemp(prefix="siro-r11-"))
    # 1. cold start / stop / restart x3 on the same data dir
    cycles = []
    for _ in range(3):
        t = time.monotonic()
        gw = Gateway(data, out)
        ok = gw.ready()
        cycles.append({"healthy": ok, "start_s": round(time.monotonic() - t, 2), "exit": gw.stop()})
    results["cold_cycles"] = cycles
    # 2. cloud unreachable (stands in for network loss; host network is not touched)
    gw = Gateway(
        data, out,
        {"SIRO_OPENAI_API_KEY": "synthetic", "SIRO_OPENAI_MODEL": "synthetic",
         "SIRO_OPENAI_BASE_URL": "http://127.0.0.1:9", "SIRO_RUNTIME_PROFILE": "candidate",
         "SIRO_LOCAL_FALLBACK_OLLAMA_MODEL": "synthetic-not-called"},
    )
    results["cloud_unreachable"] = {"healthy": gw.ready(), "exit": gw.stop()}
    # 3. child process fault: kill children, gateway must stay healthy
    gw = Gateway(data, out)
    healthy = gw.ready()
    kids = tree(gw.proc.pid)
    for k in kids:
        os.kill(k, signal.SIGKILL)
    time.sleep(1)
    results["child_fault"] = {"children_killed": len(kids), "healthy_after": healthy and gw.ready(5), "exit": gw.stop()}
    (out / "phase1.json").write_text(json.dumps(results, indent=2))
    # 4. soak
    if hours:
        gw = Gateway(data, out)
        assert gw.ready()
        samples = out / "soak.csv"
        samples.write_text("epoch,healthy,rss_kib\n")
        end = time.time() + hours * 3600
        while time.time() < end and gw.proc.poll() is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{gw.port}/health/ready", timeout=3):
                    h = 1
            except Exception:
                h = 0
            with samples.open("a") as f:
                f.write(f"{int(time.time())},{h},{rss_kib(gw.proc.pid)}\n")
            time.sleep(60)
        (out / "soak-final.json").write_text(
            json.dumps({"alive": gw.proc.poll() is None, "exit_on_stop": gw.stop()})
        )


if __name__ == "__main__":
    main()
