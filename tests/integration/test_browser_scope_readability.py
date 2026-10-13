from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest
from playwright.async_api import Error, Page

from siro.adapters.browser import BrowserScopeReason, BrowserScopeViolation, ScopedBrowserDriver
from siro.ports.models import CancellationToken
from siro.services.tools.browser_session import BrowserSessions
from siro.services.tools.execution import ExecutionContext


@contextmanager
def pages() -> Iterator[tuple[str, str, list[str]]]:
    hits: list[str] = []

    class Foreign(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"FOREIGN CONTENT MUST NEVER BE FETCHED")

        def log_message(self, format: str, *args: object) -> None:
            pass

    foreign = ThreadingHTTPServer(("127.0.0.1", 0), Foreign)
    other = f"http://127.0.0.1:{foreign.server_port}"

    class Main(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/redirect"):
                self.send_response(302)
                self.send_header("Location", other + "/secret-query-canary")
                self.end_headers()
                return
            additions = {
                "/resources": f'<img src="{other}/image"><script src="{other}/script"></script>'
                f'<iframe src="{other}/frame"></iframe><link rel="stylesheet" href="{other}/css">',
                "/resource-redirect": '<script src="/redirect"></script>',
                "/link": f'<a href="{other}/secret-query-canary">Outside</a>',
                "/script": f'<script>location.href="{other}/secret-query-canary";</script>',
            }
            body = "<html><head><title>Authorized source</title></head><body>Readable main text"
            body += additions.get(self.path, "") + "</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, format: str, *args: object) -> None:
            pass

    main = ThreadingHTTPServer(("127.0.0.1", 0), Main)
    servers = [foreign, main]
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
    for thread in threads:
        thread.start()
    try:
        yield f"http://127.0.0.1:{main.server_port}", other, hits
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)


@pytest.mark.asyncio
async def test_partial_main_page_blocks_foreign_resources_and_resets_on_navigation() -> None:
    with pages() as (origin, _other, hits):
        async with ScopedBrowserDriver((origin,)) as browser:
            for path in ("/resources", "/resource-redirect"):
                value = await browser.navigate(origin + path)
                assert value.title == "Authorized source"
                assert "Readable main text" in value.text
                assert "FOREIGN CONTENT" not in value.text
                assert value.blocked_resources
                assert (await browser.observe()).blocked_resources
            assert not (await browser.navigate(origin)).blocked_resources
            assert hits == []


@pytest.mark.asyncio
async def test_main_scope_and_redirect_fail_with_safe_reason_then_recover() -> None:
    with pages() as (origin, other, hits):
        async with ScopedBrowserDriver((origin,)) as browser:
            for url, reason in (
                (other + "/secret-query-canary", BrowserScopeReason.MAIN_ORIGIN_DENIED),
                (origin + "/redirect", BrowserScopeReason.REDIRECT_DENIED),
            ):
                with pytest.raises(BrowserScopeViolation) as caught:
                    await browser.navigate(url)
                assert caught.value.reason is reason
                assert "secret-query-canary" not in str(caught.value)
                assert origin not in str(caught.value)
                assert other not in str(caught.value)
                assert not (await browser.navigate(origin)).blocked_resources
            assert hits == []


@pytest.mark.asyncio
async def test_main_navigation_from_link_cannot_report_success_from_old_page() -> None:
    with pages() as (origin, _other, hits):
        async with ScopedBrowserDriver((origin,)) as browser:
            await browser.navigate(origin + "/link")
            target = await browser.select("link", "Outside")
            with pytest.raises(BrowserScopeViolation) as caught:
                await browser.click(target)
            assert caught.value.reason is BrowserScopeReason.MAIN_ORIGIN_DENIED
            assert hits == []
            assert "Readable main text" in (await browser.navigate(origin)).text


@pytest.mark.asyncio
async def test_script_main_navigation_cannot_be_partial_success() -> None:
    with pages() as (origin, _other, hits):
        async with ScopedBrowserDriver((origin,)) as browser:
            with pytest.raises(BrowserScopeViolation) as caught:
                await browser.navigate(origin + "/script")
            assert caught.value.reason is BrowserScopeReason.MAIN_ORIGIN_DENIED
            assert hits == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "[https://example.com/](https://example.com/)",
        "file:///tmp/canary",
        "data:text/html,canary",
        "http://credential-canary@example.com/",
        "https://example.com:invalid/",
        "http://[broken",
    ],
)
async def test_invalid_navigation_is_safe_and_rejected_without_running_browser(url: str) -> None:
    driver = ScopedBrowserDriver(("https://example.com",))
    with pytest.raises(BrowserScopeViolation) as caught:
        await driver.navigate(url)
    assert caught.value.reason is BrowserScopeReason.INVALID_URL
    assert "canary" not in str(caught.value)


@pytest.mark.asyncio
async def test_session_partial_marker_and_explicit_new_origin_remain_compatible() -> None:
    with pages() as (origin, other, hits):
        sessions = BrowserSessions(ScopedBrowserDriver)
        context = ExecutionContext("run", "owner", "epoch", CancellationToken(), authorized=True)
        try:
            result = await sessions.execute(
                "navigate+read", {"url": origin + "/resources"}, context
            )
            assert result["load_status"] == "partial"
            assert result["reason"] == "subresource_denied"
            assert hits == []
            result = await sessions.execute("navigate+read", {"url": other}, context)
            assert "FOREIGN CONTENT" in result["text"]
            assert "load_status" not in result
            assert len(hits) == 1
            assert sessions._sessions["owner"].origin == other
            await sessions.execute("close", {}, context)
            assert not sessions._sessions
        finally:
            await asyncio.wait_for(sessions.close(), timeout=5)


@pytest.mark.asyncio
async def test_destroyed_context_keeps_pending_scope_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = ScopedBrowserDriver(("https://example.com",))

    class DestroyedPage:
        url = "https://example.com/"

        async def evaluate(self, script: str) -> None:
            driver._blocked_main = BrowserScopeReason.REDIRECT_DENIED
            raise Error("synthetic private-url-canary context destroyed")

    replaced: list[bool] = []

    async def replace_page() -> None:
        replaced.append(True)

    driver._page = cast(Page, DestroyedPage())
    monkeypatch.setattr(driver, "_replace_page", replace_page)
    with pytest.raises(BrowserScopeViolation) as caught:
        await driver.observe()
    assert caught.value.reason is BrowserScopeReason.REDIRECT_DENIED
    assert "private-url-canary" not in str(caught.value)
    assert replaced == [True]


@pytest.mark.parametrize("profile,enabled", [("legacy", "1"), ("candidate", "0")])
def test_real_main_stateless_wrapper_preserves_partial_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, enabled: str
) -> None:
    import uvicorn

    from siro.services.presentation import gateway

    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", profile)
    monkeypatch.setenv("SIRO_BROWSER_SESSION_ENABLED", enabled)
    monkeypatch.setenv("SIRO_WORKSPACE_ENABLED", "0")
    captured: dict[str, Any] = {}
    original = gateway.create_app

    def capture(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(gateway, "create_app", capture)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)
    gateway.main()

    async def verify() -> None:
        with pages() as (origin, _other, hits):
            result = await captured["on_browser_tool"](origin + "/resources")
            assert result["load_status"] == "partial"
            assert result["reason"] == "subresource_denied"
            assert "Readable main text" in result["text"]
            assert hits == []
        await captured["on_shutdown"]()

    asyncio.run(verify())
