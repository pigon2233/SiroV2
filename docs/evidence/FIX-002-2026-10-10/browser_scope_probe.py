"""Real Chromium scope fixtures; trusted ephemeral A/B servers, no external websites."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import Route

from siro.adapters.browser import ScopedBrowserDriver
from siro.adapters.computer import ScopeViolation
from siro.services.tools.browser_session import BrowserSessions, _Session

REPOSITORY = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
SOURCES = (
    "src/siro/adapters/browser.py",
    "src/siro/services/tools/browser_session.py",
    "src/siro/services/tools/orchestrator.py",
    "src/siro/services/presentation/integrated.py",
    "src/siro/services/presentation/gateway.py",
)


def hashes() -> dict[str, str]:
    return {name: hashlib.sha256((REPOSITORY / name).read_bytes()).hexdigest() for name in SOURCES}


def safe_reason(error: BaseException) -> str:
    for name in ("reason", "reason_code"):
        value = getattr(error, name, None)
        if value in {
            "invalid_url",
            "main_origin_denied",
            "origin_denied",
            "navigation_denied",
            "redirect_denied",
            "subresource_denied",
            "main_frame_denied",
            "main_navigation_denied",
            "cross_origin_redirect_denied",
        }:
            return str(value)
    return "UNSPECIFIED"


def partial_marker(observation: object) -> dict[str, object]:
    # Exercise the existing session serialization; do not invent fields on the driver DTO.
    serialized = BrowserSessions._observation(_Session(), observation)
    return {
        "blocked_resources": getattr(observation, "blocked_resources", None),
        "load_status": serialized.get("load_status"),
        "reason": serialized.get("reason"),
    }


async def verify(phase: str) -> dict[str, object]:
    record: dict[str, object] = {
        "phase": phase,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope": "Real Chromium and trusted ephemeral A/B HTTP origins; purely synthetic fixtures",
        "source_sha256_start": hashes(),
        "privacy": {
            "private_data_read": False,
            "production_8026_accessed": False,
            "external_websites_accessed": False,
            "raw_error_or_sensitive_URL_written": False,
            "canary": "synthetic query and userinfo markers; values omitted from request evidence",
        },
        "cases": [],
    }
    b_hits: list[dict[str, object]] = []
    a_hits: list[str] = []
    origins: dict[str, str] = {}
    threads: list[threading.Thread] = []
    servers: list[ThreadingHTTPServer] = []
    browser_cleanup: list[bool] = []

    class BHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            b_hits.append(
                {
                    "query_present": bool(urlsplit(self.path).query),
                    "authorization_present": bool(self.headers.get("Authorization")),
                    "referer_present": bool(self.headers.get("Referer")),
                }
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<title>B outside scope</title><p>B SYNTHETIC OUTSIDE</p>")

        def log_message(self, _format: str, *args: object) -> None:
            pass

    class AHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            a_hits.append(path)
            outside = origins["B"] + "/outside?canary=SYNTHETIC_ONLY"
            button_action = f"location.href='{outside}'"
            fixtures = {
                "/plain": "",
                "/image": f'<img src="{outside}">',
                "/script": f'<script src="{outside}"></script>',
                "/iframe": f'<iframe src="{outside}"></iframe>',
                "/script-top": f"<script>window.location.href={json.dumps(outside)}</script>",
                "/iframe-top": f'<iframe src="{origins["A"]}/frame-top"></iframe>',
                "/frame-top": f"<script>top.location.href={json.dumps(outside)}</script>",
                "/button-top": f'<button onclick="{button_action}">Navigate outside</button>',
            }
            if path == "/redirect":
                self.send_response(302)
                self.send_header("Location", outside)
                self.end_headers()
                return
            html = (
                "<!doctype html><html><head><title>A synthetic readable</title></head>"
                "<body><h1>A SYNTHETIC CONTENT</h1>" + fixtures.get(path, "") + "</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        def log_message(self, _format: str, *args: object) -> None:
            pass

    class CapturingDriver(ScopedBrowserDriver):
        def __init__(self) -> None:
            super().__init__((origins["A"],))
            self.requests: list[dict[str, object]] = []

        async def _route_request(self, route: Route) -> None:
            parsed = urlsplit(route.request.url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            self.requests.append(
                {
                    "origin": "A"
                    if origin == origins["A"]
                    else "B"
                    if origin == origins["B"]
                    else "OTHER",
                    "resource_type": route.request.resource_type,
                    "is_navigation_request": route.request.is_navigation_request(),
                    "is_main_frame": route.request.frame == self._require_page().main_frame,
                    "query_present": bool(parsed.query),
                    "userinfo_present": parsed.username is not None or parsed.password is not None,
                }
            )
            await super()._route_request(route)

    try:
        for label, handler in (("B", BHandler), ("A", AHandler)):
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            assert server.server_port != 8026
            origins[label] = f"http://127.0.0.1:{server.server_port}"
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            servers.append(server)
            threads.append(thread)
        record["origins"] = origins.copy()
        cases = [
            ("allowed_A", origins["A"] + "/plain", False),
            ("direct_B", origins["B"] + "/outside?canary=SYNTHETIC_ONLY", False),
            (
                "direct_B_userinfo",
                origins["B"].replace("http://", "http://synthetic-user:synthetic-password@")
                + "/outside?canary=SYNTHETIC_ONLY",
                False,
            ),
            ("A_redirect_B", origins["A"] + "/redirect", False),
            ("A_with_B_image", origins["A"] + "/image", False),
            ("A_with_B_script", origins["A"] + "/script", False),
            ("A_with_B_iframe", origins["A"] + "/iframe", False),
            ("A_script_main_navigation_B", origins["A"] + "/script-top", False),
            ("A_iframe_script_main_navigation_B", origins["A"] + "/iframe-top", False),
            ("A_button_main_navigation_B", origins["A"] + "/button-top", True),
        ]
        for label, url, click in cases:
            before = len(b_hits)
            item: dict[str, object] = {"fixture": label}
            driver = CapturingDriver()
            try:
                async with driver:
                    record["chromium_version"] = driver._browser.version
                    try:
                        async with asyncio.timeout(8):
                            observation = await driver.navigate(url)
                            if click:
                                target = await driver.select("button", "Navigate outside")
                                observation = await driver.click(target)
                            # Give eager child-frame navigation a bounded opportunity to be routed.
                            await asyncio.sleep(0.15)
                            item.update(
                                {
                                    "outcome": "observation",
                                    "title_is_A": observation.title == "A synthetic readable",
                                    "text_contains_A": "A SYNTHETIC CONTENT" in observation.text,
                                    **(partial_marker(observation) if phase == "after" else {}),
                                    "final_observed_origin_allowed": driver._url_allowed(
                                        observation.url
                                    ),
                                    "page_current_origin_allowed": driver._url_allowed(
                                        driver._require_page().url
                                    ),
                                }
                            )
                            if phase == "after":
                                try:
                                    followup = await driver.observe()
                                    item["followup_read"] = {
                                        "outcome": "observation",
                                        "origin_allowed": driver._url_allowed(followup.url),
                                        **partial_marker(followup),
                                    }
                                except Exception as followup_error:
                                    item["followup_read"] = {
                                        "outcome": "error",
                                        "exception_type": type(followup_error).__name__,
                                        "is_scope_violation": isinstance(
                                            followup_error, ScopeViolation
                                        ),
                                        "reason": safe_reason(followup_error),
                                    }
                    except BaseException as error:
                        if isinstance(error, (KeyboardInterrupt, SystemExit)):
                            raise
                        item.update(
                            {
                                "outcome": "error",
                                "exception_type": type(error).__name__,
                                "is_scope_violation": isinstance(error, ScopeViolation),
                                "reason": safe_reason(error),
                            }
                        )
                    item["requests"] = driver.requests
                    item["B_hits"] = len(b_hits) - before
            finally:
                browser_cleanup.append(driver._browser is None and driver._playwright is None)
            record["cases"].append(item)
            # Preserve each completed fixture even if a later fixture is interrupted.
            (OUTPUT / f"browser-scope-{phase}.json").write_text(json.dumps(record, indent=2) + "\n")
    finally:
        for server in servers:
            await asyncio.to_thread(server.shutdown)
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)
        record["cleanup"] = {
            "all_browser_drivers_closed": bool(browser_cleanup) and all(browser_cleanup),
            "all_server_threads_stopped": bool(threads)
            and not any(thread.is_alive() for thread in threads),
            "server_sockets_closed": bool(servers)
            and all(server.fileno() == -1 for server in servers),
        }
        record["B_total_hits"] = len(b_hits)
        record["B_hit_metadata"] = b_hits
        record["A_fixture_hits"] = a_hits
        record["source_sha256_finish"] = hashes()
        record["same_source"] = record["source_sha256_start"] == record["source_sha256_finish"]
        record["completed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        record["verification_status"] = (
            "CAPTURE_COMPLETE"
            if record["same_source"]
            and all(record["cleanup"].values())
            and len(record["cases"]) == 10
            else "INCOMPLETE_OR_STALE_SOURCE"
        )
        if phase == "after":
            cases_by_name = {case["fixture"]: case for case in record["cases"]}
            expected_partial = ("A_with_B_image", "A_with_B_script", "A_with_B_iframe")
            expected_denied = ("direct_B", "direct_B_userinfo", "A_redirect_B")
            expected_main_denied = (
                "A_script_main_navigation_B",
                "A_iframe_script_main_navigation_B",
                "A_button_main_navigation_B",
            )
            checks = {
                "allowed_A_readable": cases_by_name.get("allowed_A", {}).get("text_contains_A")
                is True,
                "outside_origin_never_hit": not b_hits,
                "ordinary_subresources_return_partial_readable_A": all(
                    cases_by_name.get(name, {}).get("outcome") == "observation"
                    and cases_by_name[name].get("text_contains_A") is True
                    and (
                        (
                            cases_by_name[name].get("load_status") == "partial"
                            and cases_by_name[name].get("reason") == "subresource_denied"
                        )
                        or (
                            cases_by_name[name].get("followup_read", {}).get("load_status")
                            == "partial"
                            and cases_by_name[name].get("followup_read", {}).get("reason")
                            == "subresource_denied"
                        )
                    )
                    for name in expected_partial
                ),
                "direct_and_redirect_still_rejected": all(
                    cases_by_name.get(name, {}).get("is_scope_violation") is True
                    for name in expected_denied
                ),
                "main_navigation_never_claims_readable_outside_page": all(
                    cases_by_name.get(name, {}).get("is_scope_violation") is True
                    or cases_by_name.get(name, {})
                    .get("followup_read", {})
                    .get("is_scope_violation")
                    is True
                    for name in expected_main_denied
                ),
                "same_source": record["same_source"],
                "cleanup": all(record["cleanup"].values()),
            }
            record["repair_checks"] = checks
            record["repair_status"] = "PASS" if all(checks.values()) else "FAIL"
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["before", "after"], required=True)
    args = parser.parse_args()
    evidence = asyncio.run(verify(args.phase))
    (OUTPUT / f"browser-scope-{args.phase}.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    valid = evidence["verification_status"] == "CAPTURE_COMPLETE" and (
        args.phase == "before" or evidence["repair_status"] == "PASS"
    )
    raise SystemExit(0 if valid else 1)
