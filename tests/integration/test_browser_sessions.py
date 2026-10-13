from __future__ import annotations

import asyncio
import contextlib
import json
import os
import threading
from collections.abc import AsyncIterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from siro.adapters.browser import ScopedBrowserDriver
from siro.adapters.computer import ComputerActionError
from siro.services.tools.browser_session import BrowserSessions
from siro.services.tools.execution import ExecutionCleanupError, ExecutionContext

PAGE = b"""<title>RT012 synthetic</title><label>Name<input id="name"></label>
<button onclick="location.href='/next'">Next</button><p id="result">Waiting</p>
<button onclick="result.textContent='Saved '+nameInput.value">Save</button>
<script>let nameInput=document.querySelector('#name');nameInput.value=sessionStorage.name||'';
nameInput.oninput=()=>sessionStorage.name=nameInput.value;</script>"""


@pytest.fixture
def origin() -> Any:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            with contextlib.suppress(BrokenPipeError):
                self.wfile.write(PAGE)

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(2)


def owner(session: str = "A", run: str = "run1") -> ExecutionContext:
    return ExecutionContext(run, session, run, authorized=True)


@pytest.mark.asyncio
async def test_real_chrome_cross_run_form_isolation_stale_ttl_close(origin: str) -> None:
    now = [0.0]
    pool = BrowserSessions(ScopedBrowserDriver, clock=lambda: now[0], ttl=10, capacity=2)
    try:
        a = await pool.execute("navigate+read", {"url": origin}, owner())
        b = await pool.execute("navigate+read", {"url": origin}, owner("B"))
        assert a["screen_version"] != b["screen_version"]
        a = await pool.execute(
            "fill",
            {
                "role": "textbox",
                "name": "Name",
                "screen_version": a["screen_version"],
                "value": "SIRO",
            },
            owner(),
        )
        a = await pool.execute(
            "click",
            {"role": "button", "name": "Next", "screen_version": a["screen_version"]},
            owner(run="run2"),
        )
        assert a["url"].endswith("/next")
        a = await pool.execute(
            "click",
            {"role": "button", "name": "Save", "screen_version": a["screen_version"]},
            owner(run="run3"),
        )
        assert "Saved SIRO" in a["text"]
        b = await pool.execute(
            "click",
            {"role": "button", "name": "Save", "screen_version": b["screen_version"]},
            owner("B"),
        )
        assert "Saved SIRO" not in b["text"]
        with pytest.raises(ComputerActionError, match="screen changed"):
            await pool.execute(
                "click",
                {"role": "button", "name": "Save", "screen_version": a["screen_version"]},
                owner("B"),
            )
        # Failed action closes only B, A remains readable.
        assert "Saved SIRO" in (await pool.execute("read", {}, owner()))["text"]
        old = a["screen_version"]
        result = await pool.execute("close", {}, owner())
        assert result == {"state": "closed"}
        a = await pool.execute("navigate+read", {"url": origin}, owner())
        with pytest.raises(ComputerActionError, match="screen changed"):
            await pool.execute(
                "fill",
                {"role": "textbox", "name": "Name", "screen_version": old, "value": "wrong"},
                owner(),
            )
        await pool.execute("navigate+read", {"url": origin}, owner())
        drivers = [e.driver for e in pool._sessions.values()]
        now[0] = 11
        await pool.expire()
        assert not pool._sessions
        assert all(d is not None and d._browser is None and d._playwright is None for d in drivers)
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_real_chrome_stale_after_fill_and_origin_reset(origin: str) -> None:
    pool = BrowserSessions(ScopedBrowserDriver)
    try:
        observation = await pool.execute("navigate+read", {"url": origin}, owner())
        args: dict[str, object] = {
            "role": "textbox",
            "name": "Name",
            "screen_version": observation["screen_version"],
            "value": "new",
        }
        await pool.execute("fill", args, owner())
        with pytest.raises(ComputerActionError, match="screen changed"):
            await pool.execute("fill", args, owner())
        with pytest.raises(ComputerActionError, match="missing"):
            await pool.execute("read", {}, owner())
        await pool.execute("navigate+read", {"url": origin}, owner())
        driver = pool._sessions["A"].driver
        observation = await pool.execute(
            "navigate+read", {"url": origin.replace("127.0.0.1", "localhost")}, owner()
        )
        assert driver is not None and driver._browser is None
        assert observation["url"].startswith("http://localhost")
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_capacity_authorization_and_idle_reaper(origin: str) -> None:
    pool = BrowserSessions(ScopedBrowserDriver, capacity=1, ttl=0.15)
    await pool.start()
    try:
        with pytest.raises(PermissionError):
            await pool.execute("navigate+read", {"url": origin}, ExecutionContext("r", "A", "e"))
        await pool.execute("navigate+read", {"url": origin}, owner())
        with pytest.raises(ComputerActionError, match="capacity"):
            await pool.execute("navigate+read", {"url": origin}, owner("B"))
        for _ in range(30):
            if not pool._sessions:
                break
            await asyncio.sleep(0.03)
        assert not pool._sessions
    finally:
        reaper = pool._reaper
        await pool.close()
        assert reaper is not None and reaper.done()


@pytest.mark.asyncio
async def test_cancel_timeout_and_cleanup_failure() -> None:
    entered = asyncio.Event()

    class Driver(ScopedBrowserDriver):
        def __init__(self) -> None:
            pass

        closed = False

        async def __aenter__(self) -> Any:
            return self

        async def navigate(self, url: str) -> Any:
            entered.set()
            await asyncio.Future()

        async def __aexit__(self, *_error: object) -> None:
            self.closed = True

    driver = Driver()
    pool = BrowserSessions(lambda origins: driver, timeout=0.1)
    with pytest.raises(TimeoutError):
        await pool.execute("navigate+read", {"url": "http://localhost"}, owner())
    assert driver.closed and not pool._sessions
    driver.closed = False
    task = asyncio.create_task(pool.execute("navigate+read", {"url": "http://localhost"}, owner()))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert driver.closed and not pool._sessions

    class Broken(Driver):
        async def __aexit__(self, *_error: object) -> None:
            raise RuntimeError("synthetic close failure")

    pool = BrowserSessions(lambda origins: Broken(), timeout=0.01)
    with pytest.raises(ExecutionCleanupError):
        await pool.execute("navigate+read", {"url": "http://localhost"}, owner())
    assert pool._closed and "A" in pool._sessions
    with pytest.raises(ExecutionCleanupError):
        await pool.close()


def test_main_catalog_real_browser_across_runs_and_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    import uvicorn
    from fastapi.testclient import TestClient

    from siro.ports.models import ToolCall
    from siro.services.presentation import gateway

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    captured: dict[str, Any] = {}
    original = gateway.create_app

    def capture(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(gateway, "create_app", capture)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)
    pools: list[BrowserSessions] = []

    class TrackedSessions(BrowserSessions):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            pools.append(self)

    monkeypatch.setattr("siro.services.tools.browser_session.BrowserSessions", TrackedSessions)
    gateway.main()
    from siro.ports.models import CancellationToken, ModelChunk, ModelRequest

    class Model:
        name = "synthetic browser runtime"
        step = 0

        def __init__(self) -> None:
            self.observations: list[dict[str, str]] = []

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            observations = [json.loads(m.content) for m in request.messages if m.role == "tool"]
            if observations:
                self.observations.append(observations[-1])
            names = {tool.name for tool in request.tools}
            assert {"browser.read", "browser.fill", "browser.click", "browser.close"} <= names
            if self.step == 0:
                call = ToolCall("nav", "browser.navigate+read", {"url": origin})
            elif self.step == 1:
                call = ToolCall(
                    "fill",
                    "browser.fill",
                    {
                        "role": "textbox",
                        "name": "Name",
                        "value": "Runtime",
                        "screen_version": observations[-1]["screen_version"],
                    },
                )
            elif self.step == 2:
                call = ToolCall(
                    "click",
                    "browser.click",
                    {
                        "role": "button",
                        "name": "Save",
                        "screen_version": observations[-1]["screen_version"],
                    },
                )
            elif self.step in {3, 5}:
                call = ToolCall("read", "browser.read", {})
            else:
                yield ModelChunk("text_delta", text="Synthetic complete")
                yield ModelChunk("finished")
                self.step += 1
                return
            self.step += 1
            yield ModelChunk("tool_request", tool_call=call)
            yield ModelChunk("finished")

    model = Model()
    controller = captured["on_turn"].__self__
    controller._model = model
    with TestClient(original(**captured)) as client:
        assert client.portal is not None
        client.portal.call(controller.respond, "A", "synthetic form task")
        assert "Saved Runtime" in model.observations[-1]["text"]
        client.portal.call(controller.respond, "A", "synthetic same-session read")
        assert "Saved Runtime" in model.observations[-1]["text"]
        pool = pools[0]
        drivers = [e.driver for e in pool._sessions.values()]
    assert not pool._sessions and pool._reaper is None
    assert all(d is not None and d._browser is None and d._playwright is None for d in drivers)


@pytest.mark.asyncio
async def test_token_cancel_repeated_cancel_active_close_and_deadline() -> None:
    class Slow(ScopedBrowserDriver):
        def __init__(self) -> None:
            self.entered = asyncio.Event()
            self.closed = False

        async def __aenter__(self) -> Any:
            return self

        async def navigate(self, url: str) -> Any:
            self.entered.set()
            await asyncio.Future()

        async def __aexit__(self, *_error: object) -> None:
            await asyncio.sleep(0.05)
            self.closed = True

    from siro.services.tools.execution import ExecutionCancelled

    for mode in ("token", "repeat", "shutdown", "session-close", "deadline"):
        driver = Slow()

        def factory(origins: tuple[str, ...], driver: Slow = driver) -> Slow:
            return driver

        pool = BrowserSessions(factory)
        context = owner()
        if mode == "deadline":
            from dataclasses import replace

            context = replace(context, deadline=asyncio.get_running_loop().time() + 0.05)
        task = asyncio.create_task(
            pool.execute("navigate+read", {"url": "http://localhost"}, context)
        )
        await driver.entered.wait()
        expected: type[BaseException]
        if mode == "token":
            context.cancellation.cancel()
            expected = ExecutionCancelled
        elif mode == "repeat":
            task.cancel()
            await asyncio.sleep(0.01)
            task.cancel()
            expected = asyncio.CancelledError
        elif mode == "shutdown":
            await asyncio.wait_for(pool.close(), 1)
            expected = asyncio.CancelledError
        elif mode == "session-close":
            await asyncio.wait_for(pool.close_session("A"), 1)
            expected = asyncio.CancelledError
        else:
            expected = TimeoutError
        with pytest.raises(expected):
            await asyncio.wait_for(task, 1)
        assert driver.closed and not pool._sessions
        await pool.close()


@pytest.mark.parametrize("profile,enabled", [("legacy", "1"), ("candidate", "0")])
def test_main_rollback_stateless_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, enabled: str
) -> None:
    import uvicorn

    from siro.adapters import browser as module
    from siro.adapters.browser import BrowserObservation
    from siro.services.presentation import gateway

    instances: list[Any] = []

    class Driver(ScopedBrowserDriver):
        def __init__(self, origins: tuple[str, ...]) -> None:
            self.closed = False
            instances.append(self)

        async def __aenter__(self) -> Any:
            return self

        async def navigate(self, url: str) -> BrowserObservation:
            return BrowserObservation(url, "synthetic", "readback", "version")

        async def __aexit__(self, *_error: object) -> None:
            self.closed = True

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", profile)
    monkeypatch.setenv("SIRO_BROWSER_SESSION_ENABLED", enabled)
    monkeypatch.setattr(module, "ScopedBrowserDriver", Driver)
    captured: dict[str, Any] = {}
    original = gateway.create_app

    def capture(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(gateway, "create_app", capture)
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    gateway.main()
    tools = captured["tool_orchestrator"]
    assert not {"browser.read", "browser.fill", "browser.click", "browser.close"} & {
        d.name for d in tools.model_tools()
    }

    async def flow() -> None:
        for _ in range(2):
            result = await captured["on_browser_tool"]("http://localhost")
            assert result["screen_version"] == "version"

    asyncio.run(flow())
    assert len(instances) == 2 and all(d.closed for d in instances)
    # Unified shutdown also owns the workspace and organizer; stateless browser stays closed.
    asyncio.run(captured["on_shutdown"]())
    assert all(d.closed for d in instances)
