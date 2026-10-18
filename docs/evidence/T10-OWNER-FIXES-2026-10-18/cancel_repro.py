# ruff: noqa: RUF001  (full-width punctuation is the real Chinese UI text)
"""Reproduce the owner-reported T10 cancel failure on an owned, isolated actual main.

Owner report (2026-10-18): stopping a running model-selected `computer.execute sleep 20`
left its card at 「執行中…」, and after a page reload the old 「等待完成」 still appeared.

Same isolation as ../T10-INTEGRATION-2026-10-18/acceptance.py: copied src, synthetic
account/workspace, owned runtime and SQLite in a temp root, synthetic loopback model.
The synthetic model asks for one `sleep 23` (distinctive argv) and, once given the tool
observation, answers 「等待完成」. Live services (8000, Ollama) are never contacted.

Run:  .venv/bin/python docs/evidence/T10-OWNER-FIXES-2026-10-18/cancel_repro.py [label]
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import psutil  # type: ignore[import-untyped]  # locked transitive dependency
from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parent
ACCEPTANCE = OUT.parent / "T10-INTEGRATION-2026-10-18/acceptance.py"
TRIGGER = "請執行合成等待測試"
LATE = "等待完成"
CALLS: list[dict[str, Any]] = []


def chunk(delta: dict[str, Any], finish: str | None = None) -> bytes:
    event = {"choices": [{"delta": delta, "finish_reason": finish}]}
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()


class ToolModel(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        messages = body.get("messages") or [{}]
        last = messages[-1]
        users = [m.get("content", "") for m in messages if m.get("role") == "user"]
        kind = (
            "after_tool"
            if last.get("role") == "tool"
            else ("tool_request" if users and TRIGGER in users[-1] else "plain")
        )
        CALLS.append({"at": time.time(), "kind": kind, "last_user": users[-1] if users else ""})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if kind == "tool_request":
            # A distinct argv per scenario: an identical cancelled call is correctly
            # blocked from automatic approval as prior_outcome_unknown.
            seconds = str(20 + int(users[-1].rsplit(" ", 1)[1]))
            arguments = {"argv": ["sleep", seconds], "cwd": "/", "timeout_seconds": 30}
            call = {
                "index": 0,
                "id": f"call-{len(CALLS)}",
                "type": "function",
                "function": {"name": "computer.execute", "arguments": json.dumps(arguments)},
            }
            self.wfile.write(chunk({"tool_calls": [call]}, "tool_calls"))
        else:
            text = LATE if kind == "after_tool" else "合成回覆：新的對話正常。"
            self.wfile.write(chunk({"content": text}) + chunk({}, "stop"))
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, format: str, *args: object) -> None:
        pass


def load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sleepers(probe: Any) -> list[int]:
    root = psutil.Process(probe.process.pid)
    return [
        child.pid
        for child in root.children(recursive=True)
        if child.is_running()
        and len(child.cmdline()) == 2
        and child.cmdline()[0] == "sleep"
        and child.cmdline()[1] in {"21", "22", "23"}
    ]


def card_status(page: Page) -> list[str]:
    return [
        str(text)
        for text in page.eval_on_selector_all(
            "#tool-proposals .proposal .tool-status", "nodes => nodes.map(n => n.textContent)"
        )
    ]


def start_tool(page: Page, number: int) -> None:
    page.fill("#text", f"{TRIGGER} {number}")
    page.click("#chat button[type=submit]")
    try:
        page.wait_for_function(
            "() => [...document.querySelectorAll('#tool-proposals .tool-status')]"
            ".some(n => n.textContent.includes('執行中'))",
            timeout=15000,
        )
    except Exception:
        print(
            json.dumps(
                {
                    "calls": CALLS[-3:],
                    "messages": page.inner_text("#messages"),
                    "notice": page.inner_text("#service-notice"),
                    "cards": card_status(page),
                },
                ensure_ascii=False,
            )
        )
        raise
    page.wait_for_timeout(2000)


def scenario(browser: Any, probe: Any, number: int, name: str, after_stop: str) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1280, "height": 860})
    page = context.new_page()
    late_frames: list[str] = []

    def frames(ws: Any) -> None:
        if ws.url.split("?")[0].endswith("/ws/control"):
            ws.on(
                "framereceived",
                lambda payload: late_frames.append(str(payload)) if LATE in str(payload) else None,
            )

    page.on("websocket", frames)
    page.goto(probe.origin + "/#/chat")
    page.wait_for_function("() => controlAuthenticated === true", timeout=15000)
    calls_before = len(CALLS)
    start_tool(page, number)
    running = sleepers(probe)
    stopped_at = time.time()
    page.click("#cancel")
    if after_stop in {"reload", "new_message_then_reload"}:
        if after_stop == "new_message_then_reload":
            page.wait_for_function(
                "() => !document.querySelector('#chat button[type=submit]').disabled",
                timeout=10000,
            )
            page.wait_for_timeout(1500)
            page.fill("#text", "請只回答：新的對話正常")
            page.click("#chat button[type=submit]")
            page.wait_for_timeout(1500)
        page.reload()
        page.wait_for_function("() => controlAuthenticated === true", timeout=15000)
    page.wait_for_timeout(1500)
    after_stop_processes = sleepers(probe)
    cards_soon = card_status(page)
    page.wait_for_timeout(26000)
    transcript = page.inner_text("#messages")
    result = {
        "scenario": name,
        "sleep_running_before_stop": len(running),
        "sleep_running_1_5s_after_stop": len(after_stop_processes),
        "sleep_running_after_wait": len(sleepers(probe)),
        "tool_cards_1_5s_after_stop": cards_soon,
        "tool_cards_after_wait": card_status(page),
        "late_reply_in_transcript": LATE in transcript,
        "late_reply_frames_received": len(late_frames),
        "model_calls": [c["kind"] for c in CALLS[calls_before:]],
        "after_tool_model_calls": sum(c["kind"] == "after_tool" for c in CALLS[calls_before:]),
        "seconds_observed": round(time.time() - stopped_at, 1),
    }
    print(json.dumps(result, ensure_ascii=False), flush=True)
    context.close()
    return result


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "current"
    acceptance = load(ACCEPTANCE, "t10_acceptance")
    fixture = acceptance.load_fixture()
    run_dir = OUT / f"run-{label}"
    run_dir.mkdir(exist_ok=True)
    fixture.OUT = run_dir
    probe = fixture.Probe()
    env = {
        key: value
        for key, value in probe.env.items()
        if not any(
            marker in key.upper()
            for marker in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
        )
        or key == "SIRO_CONTEXT_TOKEN_BUDGET_ENABLED"
    }
    env.pop("SIRO_OLLAMA_MODEL", None)
    model = ThreadingHTTPServer(("127.0.0.1", 0), ToolModel)
    threading.Thread(target=model.serve_forever, daemon=True).start()
    env.update(
        SIRO_RUNTIME_PROFILE="candidate",
        SIRO_OPENAI_BASE_URL=f"http://127.0.0.1:{model.server_port}",
        SIRO_OPENAI_MODEL="synthetic-loopback",
        SIRO_OPENAI_API_KEY="synthetic-loopback-not-a-secret",  # pragma: allowlist secret
    )
    probe.env = env
    results: list[dict[str, Any]] = []
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    assert executable
    try:
        probe.start()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=executable, headless=True)
            try:
                for number, (name, after) in enumerate(
                    [
                        ("stop_and_wait_same_page", "wait"),
                        ("stop_then_reload", "reload"),
                        ("stop_new_message_then_reload", "new_message_then_reload"),
                    ],
                    start=1,
                ):
                    results.append(scenario(browser, probe, number, name, after))
            finally:
                browser.close()
    finally:
        probe.close()
        model.shutdown()
        (OUT / f"cancel-{label}.json").write_text(
            json.dumps(
                {
                    "label": label,
                    "results": results,
                    "copied_package_unchanged": probe.receipt.get("copied_package_unchanged"),
                },
                ensure_ascii=False,
                indent=1,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
