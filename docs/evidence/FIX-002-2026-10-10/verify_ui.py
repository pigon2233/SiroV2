"""Real Chrome check of the actual tool-result renderer with synthetic DOM events.

This does not start SIRO, invoke a provider, execute a tool, or validate search semantics.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

from playwright.async_api import Route, async_playwright

REPOSITORY = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
SOURCE = REPOSITORY / "src/siro/services/presentation/static/index.html"


def cases() -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    explanations = {
        "invalid_url": "網址格式不正確",
        "main_origin_denied": "主頁不在這次授權的網站範圍",
        "redirect_denied": "網站轉往未授權的來源",
        "subresource_denied": "部分跨站資源已阻擋",
    }
    for reason, explanation in explanations.items():
        scenarios.append(
            {
                "name": "failure_" + reason,
                "payload": {
                    "capability": "browser.navigate+read",
                    "error": "ScopeViolation",
                    "result": {"reason": reason},
                },
                "contains": ["失敗：ScopeViolation", explanation],
                "excludes": ["完成：", reason],
            }
        )
    for reason in (
        '<img src=x onerror="window.__resultInjected=1">synthetic-reason-canary',
        "__proto__",
        "constructor",
        "toString",
    ):
        scenarios.append(
            {
                "name": "untrusted_reason_" + str(len(scenarios)),
                "payload": {
                    "capability": "browser.read",
                    "error": "ScopeViolation",
                    "result": {"reason": reason, "message": "synthetic-message-canary"},
                },
                "exact": "失敗：ScopeViolation",
                "excludes": ["synthetic-reason-canary", "synthetic-message-canary"],
            }
        )
    scenarios.append(
        {
            "name": "ordinary_error_compatibility",
            "payload": {
                "capability": "browser.read",
                "error": "RuntimeError",
                "result": {"reason": "redirect_denied", "message": "synthetic-message-canary"},
            },
            "exact": "失敗：RuntimeError",
            "excludes": ["synthetic-message-canary", "網站轉往"],
        }
    )
    scenarios.append(
        {
            "name": "old_error_without_optional_result",
            "payload": {"capability": "browser.navigate+read", "error": "ScopeViolation"},
            "exact": "失敗：ScopeViolation",
        }
    )
    for capability in ("browser.navigate+read", "browser.read", "browser.fill", "browser.click"):
        scenarios.append(
            {
                "name": "partial_" + capability,
                "payload": {
                    "capability": capability,
                    "error": None,
                    "result": {
                        "load_status": "partial",
                        "reason": "subresource_denied",
                        "title": '<img src=x onerror="window.__resultInjected=1">Synthetic title',
                        "url": "https://synthetic.invalid/partial",
                        "text": "Synthetic visible page text",
                    },
                },
                "contains": ["部分載入", "部分跨站資源已阻擋", "Synthetic visible page text"],
                "excludes": ["完成："],
            }
        )
    for partial_reason in (
        None,
        '<img src=x onerror="window.__resultInjected=1">synthetic-reason-canary',
    ):
        scenarios.append(
            {
                "name": "partial_unknown_reason_" + str(len(scenarios)),
                "payload": {
                    "capability": "browser.read",
                    "error": None,
                    "result": {
                        "load_status": "partial",
                        "reason": partial_reason,
                        "title": "Synthetic title",
                        "url": "https://synthetic.invalid/partial",
                        "text": "Synthetic visible page text",
                    },
                },
                "contains": ["部分載入", "可能不完整", "Synthetic visible page text"],
                "excludes": ["完成：", "synthetic-reason-canary"],
            }
        )
    scenarios.extend(
        (
            {
                "name": "full_browser_compatibility",
                "payload": {
                    "capability": "browser.navigate+read",
                    "error": None,
                    "result": {
                        "title": "Synthetic complete source",
                        "url": "https://synthetic.invalid/full",
                        "text": "Synthetic full text",
                    },
                },
                "contains": ["完成：Synthetic complete source", "Synthetic full text"],
                "excludes": ["部分載入"],
            },
            {
                "name": "computer_result_text_content",
                "payload": {
                    "capability": "computer.execute",
                    "error": None,
                    "result": {
                        "returncode": 0,
                        "stdout": '<svg onload="window.__resultInjected=1">literal output',
                        "truncated": False,
                    },
                },
                "contains": ["完成（結束碼 0）", "<svg onload="],
            },
        )
    )
    return scenarios


async def verify() -> dict[str, Any]:
    source_bytes = SOURCE.read_bytes()
    html = source_bytes.decode()
    script = html[
        html.index("      function updateToolProposal(") : html.index(
            "      async function submitText("
        )
    ]
    result: dict[str, Any] = {
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope": "Actual updateToolProposal/renderToolResult functions extracted from current "
        "index.html, rendered in a fresh real Chrome DOM with synthetic tool-result payloads.",
        "limitations": [
            "Component rendering verification, not full production HTTP/WebSocket integration.",
            "No real provider or website/search semantics; no browser tool is executed.",
            "No production port 8026, service restart, private DB, keys, chats, audio, or GPU work.",
        ],
        "source": "src/siro/services/presentation/static/index.html",
        "source_sha256_start": hashlib.sha256(source_bytes).hexdigest(),
        "extracted_renderer_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "playwright_version": version("playwright"),
        "cases": [],
    }
    rows: list[dict[str, Any]] = []
    result["cases"] = rows
    page_errors: list[str] = []
    page_requests = 0
    browser_closed = False
    context_closed = False
    playwright_stopped = False
    temporary_profile: Path | None = None
    try:
        executable = shutil.which("google-chrome") or shutil.which("chromium")
        if executable is None:
            raise RuntimeError("Chrome/Chromium unavailable")
        result["browser_executable"] = executable
        with tempfile.TemporaryDirectory(prefix="siro-fix002-ui-") as directory:
            temporary_profile = Path(directory)
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    executable_path=executable,
                    headless=True,
                    downloads_path=directory,
                    env={"PATH": os.defpath, "LANG": "C.UTF-8"},
                    args=["--disable-gpu", "--no-sandbox", "--disable-background-networking"],
                )
                result["browser_version"] = browser.version
                try:
                    context = await browser.new_context(
                        viewport={"width": 1000, "height": 900}, accept_downloads=False
                    )

                    async def deny_request(route: Route) -> None:
                        nonlocal page_requests
                        page_requests += 1
                        await route.abort()

                    await context.route("**/*", deny_request)
                    page = await context.new_page()
                    page.on("pageerror", lambda error: page_errors.append(str(error)))
                    await page.set_content(
                        "<html lang='zh-Hant'><meta charset='utf-8'><title>FIX-002 tool results</title>"
                        "<style>body{font:16px sans-serif;margin:20px}"
                        "section{border:1px solid #999;margin:12px 0;padding:10px}"
                        ".tool-status{white-space:pre-wrap}</style>"
                        "<h1>FIX-002：工具結果驗收</h1><main id='tool-proposals'></main></html>"
                    )
                    await page.add_script_tag(content=script)
                    for index, case in enumerate(cases()):
                        payload = dict(case["payload"])
                        payload["proposal_id"] = "ui-" + str(index)
                        observed = await page.evaluate(
                            """data => {
                              window.__resultInjected = 0;
                              const card = document.createElement('section');
                              card.id = 'tool-' + data.proposal_id;
                              document.querySelector('#tool-proposals').appendChild(card);
                              renderToolResult(data);
                              return {text: card.textContent,
                                status_count: card.querySelectorAll('.tool-status').length,
                                unsafe_elements: card.querySelectorAll('img,svg,script').length,
                                injected: window.__resultInjected};
                            }""",
                            payload,
                        )
                        text = observed["text"]
                        passed = (
                            observed["status_count"] == 1
                            and observed["unsafe_elements"] == 0
                            and observed["injected"] == 0
                            and all(item in text for item in case.get("contains", ()))
                            and all(item not in text for item in case.get("excludes", ()))
                            and ("exact" not in case or text == case["exact"])
                        )
                        rows.append({"name": case["name"], "passed": passed, **observed})
                        if not passed:
                            raise AssertionError("Rendered case failed: " + str(case["name"]))
                    await page.screenshot(path=str(OUTPUT / "tool-results.png"), full_page=True)
                    await context.close()
                    context_closed = True
                finally:
                    await browser.close()
                    browser_closed = not browser.is_connected()
            playwright_stopped = True
    except Exception as error:
        result["failure"] = f"{type(error).__name__}: {error}"
    result["page_errors"] = page_errors
    result["page_requests"] = page_requests
    result["source_sha256_end"] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    result["source_unchanged"] = result["source_sha256_start"] == result["source_sha256_end"]
    result["cleanup"] = {
        "browser_disconnected": browser_closed,
        "context_closed": context_closed,
        "playwright_stopped": playwright_stopped,
        "temporary_directory_removed": temporary_profile is not None
        and not temporary_profile.exists(),
    }
    result["status"] = (
        "PASS"
        if "failure" not in result
        and len(rows) == len(cases())
        and all(row["passed"] for row in rows)
        and not page_errors
        and page_requests == 0
        and result["source_unchanged"]
        and all(result["cleanup"].values())
        else "FAIL"
    )
    return result


if __name__ == "__main__":
    report = asyncio.run(verify())
    destination = OUTPUT / "ui-verification.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {"status": report["status"], "cases": len(report["cases"]), "report": str(destination)}
        )
    )
    raise SystemExit(0 if report["status"] == "PASS" else 1)
