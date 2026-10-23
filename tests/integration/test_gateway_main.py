"""Exercise the installed production entry point with isolated offline configuration."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest


def test_gateway_main_starts_and_stops_with_isolated_data(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SIRO_")}
    environment.pop("GROQ_API_KEY", None)
    environment.update(SIRO_DATA_DIR=str(tmp_path), SIRO_GATEWAY_PORT=str(port))
    environment_root = Path(os.environ.get("UV_PROJECT_ENVIRONMENT") or Path(__file__).parents[2] / ".venv")
    executable = environment_root / "bin/siro-gateway"
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


@pytest.mark.parametrize("phase", ["spawn", "before_ack", "after_ack"])
@pytest.mark.parametrize("application", ["calculator", "firefox"])
def test_candidate_application_owned_launcher_cancel_and_ack_lifetime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str, application: str
) -> None:
    import uvicorn

    from siro.services.presentation import gateway

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    captured: dict[str, Any] = {}
    original_factory = gateway.create_app

    def factory(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return original_factory(**kwargs)

    monkeypatch.setattr(gateway, "create_app", factory)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)
    gateway.main()
    original_spawn = asyncio.create_subprocess_exec
    original_is_file = Path.is_file
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda path: True if str(path) == "/usr/bin/firefox" else original_is_file(path),
    )

    async def exercise() -> None:
        entered, release = asyncio.Event(), asyncio.Event()
        processes: list[asyncio.subprocess.Process] = []
        marker = tmp_path / "child.pid"
        code = (
            "import os,time; child=os.fork(); "
            "open('child.pid','w').write(str(child)) if child else None; "
            "time.sleep(30) if child==0 else time.sleep(.05)"
            if phase == "after_ack"
            else "import time; time.sleep(30)"
        )

        if application == "firefox" and phase == "after_ack":
            code = "import os,time; open('child.pid','w').write(str(os.getpid())); time.sleep(30)"

        async def spawn(*args: str, **kwargs: Any) -> asyncio.subprocess.Process:
            if args[0] == "pgrep":
                return await original_spawn(
                    sys.executable,
                    "-c",
                    f"print({processes[0].pid})",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    start_new_session=True,
                )
            assert args[0] == (
                "/usr/bin/firefox" if application == "firefox" else "/usr/bin/gtk-launch"
            )
            process = await original_spawn(
                sys.executable,
                "-c",
                code,
                cwd=tmp_path,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            processes.append(process)
            entered.set()
            if phase == "spawn":
                await release.wait()
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        task = asyncio.create_task(captured["on_application_tool"](application))
        await asyncio.wait_for(entered.wait(), 2)
        try:
            if phase == "after_ack":
                result = await asyncio.wait_for(task, 4)
                assert result == (
                    {"application": "計算機", "state": "launch-confirmed"}
                    if application == "calculator"
                    else {
                        "application": "Firefox",
                        "state": "running",
                        "pid": str(processes[0].pid),
                    }
                )
                assert marker.exists() and int(marker.read_text()) > 0
                task.cancel()  # completed acknowledgment must not kill user-managed app
                os.kill(int(marker.read_text()), 0)
            else:
                task.cancel()
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 2)
                assert processes[0].returncode is not None, "owned launcher not stopped/reaped"
        finally:
            release.set()
            for process in processes:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def test_candidate_main_real_local_browser_cancel_closes_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading
    from collections.abc import AsyncIterator
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    import uvicorn

    from siro.adapters import browser as browser_module
    from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, ToolCall
    from siro.services.presentation import gateway

    arrived, release = threading.Event(), threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            arrived.set()
            release.wait(15)
            self.send_response(200)
            self.end_headers()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(b"<title>synthetic local fixture</title>")

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    drivers: list[browser_module.ScopedBrowserDriver] = []
    browsers: list[Any] = []

    class TrackingBrowser(browser_module.ScopedBrowserDriver):
        async def __aenter__(self) -> TrackingBrowser:
            await super().__aenter__()
            drivers.append(self)
            browsers.append(self._browser)
            return self

    class Model:
        name = "local-browser-cancel"

        async def stream(
            self,
            request: ModelRequest,
            cancellation: CancellationToken,
        ) -> AsyncIterator[ModelChunk]:
            yield ModelChunk(
                "tool_request",
                tool_call=ToolCall(
                    "browser-0",
                    "browser.navigate+read",
                    {"url": origin},
                ),
            )
            yield ModelChunk("finished")

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    captured: dict[str, Any] = {}
    original_factory = gateway.create_app

    def factory(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return original_factory(**kwargs)

    monkeypatch.setattr(browser_module, "ScopedBrowserDriver", TrackingBrowser)
    monkeypatch.setattr(gateway, "create_app", factory)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)

    async def exercise() -> None:
        controller = captured["on_turn"].__self__
        controller._model = Model()
        task = asyncio.create_task(controller.respond("local-browser", "synthetic goal"))
        try:
            assert await asyncio.to_thread(arrived.wait, 10), "local navigation did not enter"
            started = asyncio.get_running_loop().time()
            await controller.cancel("active", "browser stop", session_id="local-browser")
            assert asyncio.get_running_loop().time() - started < 5
            await asyncio.wait_for(task, 2)
            assert len(drivers) == 1 and drivers[0]._playwright is None
            assert drivers[0]._browser is None and not browsers[0].is_connected()
            readback = await controller.recovery_readback("local-browser")
            assert readback["state"] == "cancelled"
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    try:
        gateway.main()
        asyncio.run(exercise())
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
