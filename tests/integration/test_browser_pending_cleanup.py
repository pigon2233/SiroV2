"""Actual Chromium cleanup with an owned, deliberately unfinished route.fetch()."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import signal
import threading
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn, cast
from urllib.parse import urlsplit

import pytest
from playwright.async_api import Error, Route

from siro.adapters.browser import ScopedBrowserDriver
from siro.services.tools.browser_session import BrowserSessions
from siro.services.tools.execution import ExecutionCancelled, ExecutionContext

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ("src/siro/adapters/browser.py", "src/siro/services/tools/browser_session.py")


def source_hashes() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    parent: int
    birth: int
    state: str


def process_identity(pid: int) -> ProcessIdentity | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        fields = stat[stat.rfind(")") + 2 :].split()
        return ProcessIdentity(pid, int(fields[1]), int(fields[19]), fields[0])
    except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, IndexError):
        return None


def descendants(parent: ProcessIdentity) -> list[ProcessIdentity]:
    current = process_identity(parent.pid)
    if current is None or current.birth != parent.birth:
        return []
    rows = {
        int(path.name): identity
        for path in Path("/proc").iterdir()
        if path.name.isdecimal() and (identity := process_identity(int(path.name))) is not None
    }
    owned = {parent.pid}
    while children := {pid for pid, row in rows.items() if row.parent in owned} - owned:
        owned.update(children)
    return [rows[pid] for pid in owned if pid in rows]


@dataclass
class SlowOrigin:
    origin: str
    arrived: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)


@pytest.fixture
def slow_origin() -> Iterator[SlowOrigin]:
    state = SlowOrigin("")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if urlsplit(self.path).path in {"/slow", "/slow-page"}:
                state.arrived.set()
                # The test must close or cancel without releasing this request first.
                state.release.wait(30)
                data, content_type = b"SYNTHETIC SLOW RESOURCE", "text/plain"
            else:
                data = b"<title>Owned pending route</title><p>A SYNTHETIC</p><img src='/slow'>"
                content_type = "text/html; charset=utf-8"
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        def log_message(self, _format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.origin = f"http://127.0.0.1:{server.server_port}"
    assert server.server_port != 8026
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        state.release.set()
        server.shutdown()
        server.server_close()
        thread.join(2)
        assert not thread.is_alive()


class TrackingDriver(ScopedBrowserDriver):
    """Record this driver's actual route tasks and direct Playwright child only."""

    def __init__(self, origins: tuple[str, ...]) -> None:
        super().__init__(origins)
        self.slow_route = asyncio.Event()
        self.routes: set[asyncio.Task[Any]] = set()
        self.process: asyncio.subprocess.Process | None = None
        self.node: ProcessIdentity | None = None
        self.owned: dict[tuple[int, int], ProcessIdentity] = {}
        self.listener_errors: list[str] = []

    async def __aenter__(self) -> ScopedBrowserDriver:
        result = await super().__aenter__()
        connection = cast(Any, self._playwright)._impl_obj._connection
        self.process = connection._transport._proc
        original_error = connection._on_event_listener_error

        def record_listener_error(error: BaseException) -> None:
            # This SDK prints to stderr instead of calling the asyncio exception handler.
            # Keep the original behavior, capture only its type, and clear raw stderr below.
            self.listener_errors.append(type(error).__name__)
            original_error(error)

        connection._on_event_listener_error = record_listener_error
        assert self.process is not None
        self.node = process_identity(self.process.pid)
        assert self.node is not None and self.node.parent == os.getpid()
        self.capture_owned()
        return result

    async def _route_request(self, route: Route) -> None:
        task = asyncio.current_task()
        assert task is not None
        self.routes.add(task)
        if urlsplit(route.request.url).path in {"/slow", "/slow-page"}:
            self.slow_route.set()
        try:
            await super()._route_request(route)
        finally:
            self.routes.discard(task)

    def capture_owned(self) -> None:
        if self.node is not None:
            for row in descendants(self.node):
                self.owned[row.pid, row.birth] = row

    def live_owned(self) -> list[ProcessIdentity]:
        self.capture_owned()
        return [
            row
            for pid, birth in self.owned
            if (row := process_identity(pid)) is not None
            and row.birth == birth
            and row.state != "Z"
        ]

    async def emergency_cleanup(self) -> None:
        # Only identities proved under this driver's own direct Node child may be signalled.
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for row in reversed(self.live_owned()):
                current = process_identity(row.pid)
                if current is not None and current.birth == row.birth:
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(row.pid, sig)
            await asyncio.sleep(0.1)
        if self.process is not None:
            async with asyncio.timeout(2):
                await self.process.wait()
        for task in tuple(self.routes):
            task.cancel()
        await asyncio.gather(*self.routes, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["close", "cancel"])
async def test_real_chromium_pending_fetch_cleanup_within_original_budget(
    slow_origin: SlowOrigin, action: str, capsys: pytest.CaptureFixture[str]
) -> None:
    drivers: list[TrackingDriver] = []
    loop = asyncio.get_running_loop()
    original_loop_handler = loop.get_exception_handler()
    loop_errors: list[str] = []

    def record_loop_error(_loop: asyncio.AbstractEventLoop, event: dict[str, Any]) -> None:
        loop_errors.append(type(event.get("exception")).__name__)

    loop.set_exception_handler(record_loop_error)

    def factory(origins: tuple[str, ...]) -> TrackingDriver:
        driver = TrackingDriver(origins)
        drivers.append(driver)
        return driver

    pool = BrowserSessions(factory, timeout=15)
    context = ExecutionContext("pending-fetch", "pending-fetch", "pending-fetch", authorized=True)
    operation: asyncio.Task[dict[str, str]] | None = None
    capture: dict[str, object] = {"action": action, "source_before": source_hashes()}
    began: float | None = None
    try:
        url = slow_origin.origin + ("/page" if action == "close" else "/slow-page")
        operation = asyncio.create_task(pool.execute("navigate+read", {"url": url}, context))
        if action == "close":
            observation = await asyncio.wait_for(asyncio.shield(operation), 6)
            assert "A SYNTHETIC" in observation["text"]
        async with asyncio.timeout(6):
            while not drivers or not slow_origin.arrived.is_set():
                await asyncio.sleep(0.01)
            await drivers[0].slow_route.wait()
        driver = drivers[0]
        driver.capture_owned()
        assert driver.routes, "fixture must have an unfinished actual route.fetch"
        assert not slow_origin.release.is_set()
        began = time.monotonic()
        async with asyncio.timeout(5):
            if action == "close":
                await pool.close()
            else:
                context.cancellation.cancel()
                with pytest.raises(ExecutionCancelled):
                    await operation
        capture["cleanup_seconds"] = time.monotonic() - began
        assert cast(float, capture["cleanup_seconds"]) < 4
        await asyncio.sleep(0)
        assert driver._browser is None and driver._playwright is None
        assert not driver.routes, "owned route callback must complete during cleanup"
        assert driver.process is not None and driver.process.returncode is not None
        assert not driver.live_owned(), "no own Playwright or Chromium child may remain alive"
        assert not pool._sessions
        await asyncio.sleep(0.05)
        assert not driver.listener_errors, "cleanup must consume expected route shutdown errors"
        assert not loop_errors, "cleanup must not leave unhandled asyncio exceptions"
    except BaseException as error:
        capture["failure_type"] = type(error).__name__
        raise
    finally:
        if began is not None:
            capture.setdefault("cleanup_seconds", time.monotonic() - began)
        capture["source_after"] = source_hashes()
        capture["pending_routes_after_production_cleanup"] = sum(len(d.routes) for d in drivers)
        capture["own_live_after_production_cleanup"] = [
            asdict(row) for driver in drivers for row in driver.live_owned()
        ]
        capture["sdk_listener_error_types"] = [
            kind for driver in drivers for kind in driver.listener_errors
        ]
        capture["asyncio_unhandled_error_types"] = loop_errors
        # Never save native exception messages/headers/URLs to verification evidence.
        capsys.readouterr()
        # Capture production result before fixture recovery; never mask an emergency reap as PASS.
        print("PENDING_BROWSER_CLEANUP_CAPTURE " + json.dumps(capture, sort_keys=True))
        try:
            slow_origin.release.set()
            if operation is not None and not operation.done():
                operation.cancel()
                await asyncio.gather(operation, return_exceptions=True)
            for driver in drivers:
                with contextlib.suppress(Exception):
                    async with asyncio.timeout(2):
                        await driver.__aexit__()
                await driver.emergency_cleanup()
            with contextlib.suppress(Exception):
                await pool.close()
        finally:
            loop.set_exception_handler(original_loop_handler)


class FailingRoute:
    """Protocol fixture for failure propagation; this does not launch a browser."""

    def __init__(self) -> None:
        self.request = SimpleNamespace(url="http://127.0.0.1:12345/fixture")
        self.calls: list[str] = []

    async def fetch(self, **options: object) -> NoReturn:
        self.calls.append("fetch")
        raise Error("synthetic active fetch failure")

    async def abort(self, error_code: str) -> None:
        self.calls.append("abort:" + error_code)

    async def fulfill(self, **options: object) -> None:
        self.calls.append("fulfill")

    async def continue_(self, **options: object) -> None:
        self.calls.append("continue")


@pytest.mark.asyncio
async def test_live_route_fetch_error_fails_the_request_instead_of_the_handler() -> None:
    driver = ScopedBrowserDriver(("http://127.0.0.1:12345",))
    route = FailingRoute()
    await driver._route_request(cast(Route, route))
    # CP-P02: answered as a network failure, so the navigation fails visibly right away.
    # Raising here stalled navigation for 30 s and resurfaced at Browser.close, which
    # closed the whole browser pool after one unreachable site.
    assert route.calls == ["fetch", "abort:connectionfailed"]


@pytest.mark.asyncio
async def test_route_arriving_during_shutdown_cannot_fetch_or_fulfill() -> None:
    driver = ScopedBrowserDriver(("http://127.0.0.1:12345",))
    driver._closing = True
    route = FailingRoute()
    await driver._route_request(cast(Route, route))
    assert route.calls == ["abort:blockedbyclient"]
