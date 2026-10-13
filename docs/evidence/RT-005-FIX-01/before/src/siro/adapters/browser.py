"""Scoped Playwright browser driver with stale-screen protection."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

from playwright.async_api import (
    Browser,
    Error,
    Locator,
    Page,
    Playwright,
    Route,
    async_playwright,
)

from siro.adapters.computer import ComputerActionError, ScopeViolation
from siro.core.outcomes import ActionOutcomeReporter

BrowserRole = Literal["button", "checkbox", "combobox", "heading", "link", "textbox"]


@dataclass(frozen=True, slots=True)
class BrowserObservation:
    url: str
    title: str
    text: str
    screen_version: str


@dataclass(frozen=True, slots=True)
class BrowserTarget:
    role: BrowserRole
    name: str
    screen_version: str


class ScopedBrowserDriver:
    def __init__(
        self,
        allowed_origins: tuple[str, ...],
        *,
        headless: bool = True,
        outcome_reporter: ActionOutcomeReporter | None = None,
    ) -> None:
        if not allowed_origins:
            raise ValueError("at least one browser origin is required")
        self._allowed_origins = frozenset(origin.rstrip("/") for origin in allowed_origins)
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._blocked_url: str | None = None
        self._outcomes = outcome_reporter
        self._ledger: dict[str, tuple[tuple[object, ...], BrowserObservation]] = {}

    async def __aenter__(self) -> ScopedBrowserDriver:
        executable = shutil.which("google-chrome") or shutil.which("chromium")
        if executable is None:
            raise ComputerActionError("SUPPORTED browser executable is unavailable")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            executable_path=executable, headless=self._headless
        )
        self._page = await self._browser.new_page()
        await self._page.route("**/*", self._route_request)
        return self

    async def __aexit__(self, *_error: object) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def navigate(self, url: str) -> BrowserObservation:
        self._require_url(url)
        page = self._require_page()
        self._blocked_url = None
        try:
            await page.goto(url, wait_until="domcontentloaded")
        except Error as error:
            if self._blocked_url is not None:
                blocked, self._blocked_url = self._blocked_url, None
                await self._replace_page()
                raise ScopeViolation(
                    f"browser request is outside the authorized scope: {blocked}"
                ) from error
            raise
        if self._blocked_url is not None:
            blocked, self._blocked_url = self._blocked_url, None
            await self._replace_page()
            raise ScopeViolation(f"browser request is outside the authorized scope: {blocked}")
        self._require_url(page.url)
        return await self.observe()

    async def observe(self) -> BrowserObservation:
        page = self._require_page()
        state: dict[str, Any] = await page.evaluate(
            """() => ({
              html: document.documentElement.outerHTML,
              text: document.body?.innerText ?? '',
              values: Array.from(document.querySelectorAll('input,textarea,select'))
                .map(element => [element.id, element.value])
            })"""
        )
        title = await page.title()
        material = repr((page.url, title, state["html"], state["values"])).encode()
        version = hashlib.sha256(material).hexdigest()
        return BrowserObservation(page.url, title, str(state["text"]), version)

    async def select(self, role: BrowserRole, name: str) -> BrowserTarget:
        observation = await self.observe()
        locator = self._require_page().get_by_role(role, name=name, exact=True)
        if await locator.count() != 1:
            raise ComputerActionError("target must resolve to exactly one visible semantic element")
        if not await locator.is_visible():
            raise ComputerActionError("target is not visible")
        return BrowserTarget(role, name, observation.screen_version)

    async def fill(
        self, target: BrowserTarget, value: str, *, action_id: str | None = None
    ) -> BrowserObservation:
        signature = ("fill", target.role, target.name, target.screen_version, value)
        replay = self._replay(action_id, signature)
        if replay is not None:
            return replay
        await self._verify_target(target)
        await self._locator(target).fill(value)
        result = await self.observe()
        await self._record(action_id, signature, result)
        return result

    async def click(
        self, target: BrowserTarget, *, action_id: str | None = None
    ) -> BrowserObservation:
        signature = ("click", target.role, target.name, target.screen_version)
        replay = self._replay(action_id, signature)
        if replay is not None:
            return replay
        await self._verify_target(target)
        await self._locator(target).click()
        await self._require_page().wait_for_load_state("domcontentloaded")
        result = await self.observe()
        await self._record(action_id, signature, result)
        return result

    async def press(
        self, target: BrowserTarget, key: str, *, action_id: str | None = None
    ) -> BrowserObservation:
        signature = ("press", target.role, target.name, target.screen_version, key)
        replay = self._replay(action_id, signature)
        if replay is not None:
            return replay
        await self._verify_target(target)
        await self._locator(target).press(key)
        result = await self.observe()
        await self._record(action_id, signature, result)
        return result

    async def pointer_click(self, x: float, y: float, screen_version: str) -> BrowserObservation:
        await self._verify_version(screen_version)
        await self._require_page().mouse.click(x, y)
        return await self.observe()

    def _replay(
        self, action_id: str | None, signature: tuple[object, ...]
    ) -> BrowserObservation | None:
        if action_id is None:
            return None
        previous = self._ledger.get(action_id)
        if previous is None:
            return None
        if previous[0] != signature:
            raise ComputerActionError("browser action id was reused with different arguments")
        return previous[1]

    async def _record(
        self,
        action_id: str | None,
        signature: tuple[object, ...],
        result: BrowserObservation,
    ) -> None:
        if action_id is None:
            return
        self._ledger[action_id] = (signature, result)
        if self._outcomes is not None:
            await self._outcomes.report_action(
                action_id,
                "confirmed",
                occurred_at=datetime.now(UTC),
                importance=0.5,
                controllability=0.9,
                expected=signature[0],
                observed=result.screen_version,
            )

    async def screenshot(self, screen_version: str | None = None) -> bytes:
        if screen_version is not None:
            await self._verify_version(screen_version)
        return await self._require_page().screenshot(type="png")

    async def _verify_target(self, target: BrowserTarget) -> None:
        await self._verify_version(target.screen_version)
        if await self._locator(target).count() != 1:
            raise ComputerActionError("target disappeared from the current screen")

    async def _verify_version(self, expected: str) -> None:
        if (await self.observe()).screen_version != expected:
            raise ComputerActionError("screen changed; observe and select the target again")

    def _locator(self, target: BrowserTarget) -> Locator:
        return self._require_page().get_by_role(target.role, name=target.name, exact=True)

    def _require_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("browser driver is not running")
        return self._page

    def _require_url(self, url: str) -> None:
        if self._url_allowed(url):
            return
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        raise ScopeViolation(f"browser origin is outside the authorized scope: {origin}")

    def _url_allowed(self, url: str) -> bool:
        parsed = urlsplit(url)
        if parsed.scheme in {"about", "blob", "data"}:
            return True
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return parsed.scheme in {"http", "https"} and origin in self._allowed_origins

    async def _route_request(self, route: Route) -> None:
        if self._url_allowed(route.request.url):
            response = await route.fetch(max_redirects=0)
            location = response.headers.get("location")
            if 300 <= response.status < 400 and location:
                target = urljoin(route.request.url, location)
                if not self._url_allowed(target):
                    self._blocked_url = target
                    await route.abort("blockedbyclient")
                    return
            await route.fulfill(response=response)
            return
        self._blocked_url = route.request.url
        await route.abort("blockedbyclient")

    async def _replace_page(self) -> None:
        if self._browser is None:
            raise RuntimeError("browser driver is not running")
        if self._page is not None:
            await self._page.close()
        self._page = await self._browser.new_page()
        await self._page.route("**/*", self._route_request)
