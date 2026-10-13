"""Exercise the installed production entry point with isolated offline configuration."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def test_gateway_main_starts_and_stops_with_isolated_data(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SIRO_")}
    environment.pop("GROQ_API_KEY", None)
    environment.update(SIRO_DATA_DIR=str(tmp_path), SIRO_GATEWAY_PORT=str(port))
    executable = Path(__file__).parents[2] / ".venv/bin/siro-gateway"
    with (tmp_path / "gateway.log").open("wb") as log:
        process = subprocess.Popen([str(executable)], env=environment, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 20
            while True:
                assert process.poll() is None, (tmp_path / "gateway.log").read_text()
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/health/live", timeout=1
                    ) as response:
                        assert json.load(response) == {"state": "alive"}
                    break
                except (urllib.error.URLError, TimeoutError):
                    assert time.monotonic() < deadline, "gateway startup timed out"
                    time.sleep(0.1)
            assert (tmp_path / "siro.db").is_file()
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                assert b"SIRO" in response.read()
            process.terminate()
            assert process.wait(timeout=10) in (0, -signal.SIGTERM)
            assert "Application shutdown complete." in (tmp_path / "gateway.log").read_text()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
