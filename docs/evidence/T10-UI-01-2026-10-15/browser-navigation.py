"""Real DOM navigation against the explicitly supplied owned loopback fixture.

No routes or sockets are mocked; no chat/provider/TTS or task mutation is sent.
This cannot establish actual Live2D, native desktop or human usability quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

OUT = Path(__file__).resolve().parent
PAGES = (
    "chat",
    "tasks",
    "memory",
    "capabilities",
    "computer",
    "skills",
    "settings",
    "permissions",
    "system",
)
DRAFT = "合成驗收草稿\uff1a請保留目標、來源與前一次進度\uff1b跨頁時不要送出或重播。"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    assert (
        parsed.scheme == "http"
        and parsed.hostname == "127.0.0.1"
        and parsed.port is not None
        and parsed.port != 8026
        and not parsed.username
        and not parsed.password
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.fragment
    ), "Only the root URL announced by the owned random-loopback fixture is accepted."
    origin = f"http://127.0.0.1:{parsed.port}"
    screenshots = OUT / "browser"
    screenshots.mkdir(exist_ok=True)
    receipt: dict[str, object] = {
        "started_utc": datetime.now(UTC).isoformat(),
        "origin": origin,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "status": "IN_PROGRESS",
        "scope": "actual Chrome/DOM/HTTP navigation; no API/WS mocks",
        "actual_live2d": "NOT_TESTED; synthetic prepared-renderer",
        "native_desktop": "NOT_TESTED",
        "provider_tts": "NOT_REQUESTED",
        "requests": [],
        "websockets": [],
        "page_errors": [],
        "console_errors": [],
        "http_errors": [],
        "checks": [],
        "screenshots": [],
    }

    def save() -> None:
        (OUT / "BROWSER_RESULTS.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
        )

    def mutations() -> list[dict]:
        return [item for item in receipt["requests"] if item["method"] not in ("GET", "HEAD")]

    with sync_playwright() as driver:
        bundled = Path(driver.chromium.executable_path)
        executable = bundled if bundled.is_file() else Path("/opt/google/chrome/chrome")
        assert executable.is_file()
        receipt["browser_executable"] = str(executable)
        browser = driver.chromium.launch(executable_path=str(executable), headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on(
            "request",
            lambda request: receipt["requests"].append(
                {"method": request.method, "path": urlsplit(request.url).path}
            ),
        )
        page.on(
            "websocket",
            lambda websocket: receipt["websockets"].append(urlsplit(websocket.url).path),
        )
        page.on("pageerror", lambda error: receipt["page_errors"].append(str(error)))
        page.on(
            "console",
            lambda message: (
                receipt["console_errors"].append(message.text) if message.type == "error" else None
            ),
        )
        page.on(
            "response",
            lambda response: (
                receipt["http_errors"].append(
                    {"status": response.status, "path": urlsplit(response.url).path}
                )
                if response.status >= 400
                else None
            ),
        )

        def single_page(name: str) -> None:
            expect(page.locator(f'[data-page="{name}"]')).to_be_visible()
            state = page.locator("[data-page]").evaluate_all(
                "elements => elements.map(element => ({name:element.dataset.page, "
                "hidden:element.hidden, inert:element.inert, "
                "visible:!!(element.offsetWidth || element.offsetHeight || "
                "element.getClientRects().length)}))"
            )
            assert len(state) == len(PAGES), state
            assert [item["name"] for item in state if item["visible"]] == [name], state
            assert all(
                not item["hidden"] and not item["inert"]
                if item["name"] == name
                else item["hidden"] and item["inert"]
                for item in state
            ), state
            expect(page.locator("#cancel")).to_be_visible()
            assert page.locator("#cancel").count() == 1
            assert page.locator("#companion").count() == 1
            assert page.evaluate(
                "window.__acceptanceBodyElement === document.querySelector('#companion')"
            )

        def navigate(name: str) -> None:
            page.locator(f'[data-nav="{name}"]').first.click()
            expect(page).to_have_url(origin + "/#/" + name)
            single_page(name)

        def capture(name: str, width: int) -> None:
            metrics = page.evaluate(
                "({width:innerWidth, document:document.documentElement.scrollWidth, "
                "body:document.body.scrollWidth})"
            )
            assert metrics["document"] <= metrics["width"] + 1, metrics
            path = screenshots / f"{width}-{name}.png"
            page.screenshot(path=str(path), full_page=True)
            receipt["screenshots"].append(
                {
                    "path": str(path.relative_to(OUT)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "metrics": metrics,
                }
            )

        try:
            response = page.goto(origin + "/", wait_until="domcontentloaded")
            assert response is not None and response.status == 200
            expect(page.locator("#connection")).to_have_text("已連線")
            page.evaluate("window.__acceptanceBodyElement = document.querySelector('#companion')")
            single_page("chat")
            page.locator("#text").fill(DRAFT)
            before_mutations = list(mutations())
            before_websockets = list(receipt["websockets"])
            for name in PAGES:
                navigate(name)
                capture(name, 1440)
            navigate("chat")
            expect(page.locator("#text")).to_have_value(DRAFT)
            assert mutations() == before_mutations, mutations()
            assert receipt["websockets"] == before_websockets, receipt["websockets"]
            receipt["checks"].append(
                "all 9 real link destinations: one visible pane; others hidden/inert; "
                "same iframe; draft retained; zero navigation mutations/new WebSockets"
            )
            navigate("tasks")
            navigate("memory")
            page.go_back(wait_until="domcontentloaded")
            single_page("tasks")
            page.go_forward(wait_until="domcontentloaded")
            single_page("memory")
            assert mutations() == before_mutations
            assert receipt["websockets"] == before_websockets
            receipt["checks"].append("browser back/forward preserves actual route panes")
            for width in (320, 375, 414, 768):
                page.set_viewport_size({"width": width, "height": 1000})
                for name in ("chat", "tasks", "settings"):
                    navigate(name)
                    capture(name, width)
            assert mutations() == before_mutations
            assert receipt["websockets"] == before_websockets
            receipt["checks"].append(
                "320/375/414/768 px chat/tasks/settings no horizontal document overflow"
            )
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.goto(origin + "/#/tasks", wait_until="domcontentloaded")
            expect(page.locator("#connection")).to_have_text("已連線")
            page.evaluate("window.__acceptanceBodyElement = document.querySelector('#companion')")
            single_page("tasks")
            before_reload = len(receipt["websockets"])
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#connection")).to_have_text("已連線")
            page.evaluate("window.__acceptanceBodyElement = document.querySelector('#companion')")
            single_page("tasks")
            assert len(receipt["websockets"]) == before_reload + 1
            receipt["checks"].append(
                "direct hash and full reload retain tasks route; "
                "one fresh control socket per reload"
            )
            assert not receipt["page_errors"], receipt["page_errors"]
            assert not [
                item for item in receipt["http_errors"] if item["path"] != "/favicon.ico"
            ], receipt["http_errors"]
            # Console output is retained for human review; HTTP favicon errors
            # can be benign. Unhandled JavaScript errors are a hard failure above.
            receipt["status"] = "PASS"
        except BaseException as error:
            receipt["status"] = "FAIL"
            receipt["failure"] = f"{type(error).__name__}: {error}"
            try:
                page.screenshot(path=str(screenshots / "failure.png"), full_page=True)
            finally:
                save()
            raise
        finally:
            context.close()
            browser.close()
            receipt["browser_closed"] = True
            receipt["finished_utc"] = datetime.now(UTC).isoformat()
            save()
    print(json.dumps({"status": receipt["status"], "receipt": str(OUT / "BROWSER_RESULTS.json")}))


if __name__ == "__main__":
    main()
