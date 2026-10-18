# ruff: noqa: RUF001  (full-width punctuation is the real Chinese UI text)
"""T10-UI-01 integrated browser acceptance against an owned, isolated actual main.

Reuses the D57 fixture read-only: copied current src, synthetic account/workspace,
owned Rust runtime and SQLite under a temp root. Model is the built-in
an explicit synthetic loopback OpenAI-compatible SSE server started here (fixed
reply, no provider, no network beyond 127.0.0.1); renderer is the owner's licensed local
Cubism Haru sample (gitignored models/, never copied into Git). Live user services
(ports 8000/8026, Ollama 11434) are never contacted. No private data is used.

Run:  .venv/bin/python docs/evidence/T10-INTEGRATION-2026-10-18/acceptance.py
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "docs/evidence/T19-goal-loop-2026-10-14/product/product-probe.py"
LIVE2D = ROOT / "models/live2d-sdk-5-r.5/CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo/dist"
PAGES = [
    "chat",
    "tasks",
    "memory",
    "capabilities",
    "computer",
    "skills",
    "settings",
    "permissions",
    "system",
]
STEPS: list[dict[str, Any]] = []


MODEL_CALLS: list[str] = []


class SyntheticModel(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        MODEL_CALLS.append(body["messages"][-1].get("content", "") if body.get("messages") else "")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if "請慢慢回答" in json.dumps(body, ensure_ascii=False):
            # Slow synthetic stream for the cancel check; the tail must never surface.
            try:
                self.wfile.write(
                    (
                        "data: "
                        + json.dumps(
                            {
                                "choices": [
                                    {"delta": {"content": "合成前半段。"}, "finish_reason": None}
                                ]
                            },
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    ).encode()
                )
                self.wfile.flush()
                time.sleep(3)
                self.wfile.write(
                    (
                        "data: "
                        + json.dumps(
                            {
                                "choices": [
                                    {
                                        "delta": {"content": "合成後半段不應出現"},
                                        "finish_reason": "stop",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                        + "\n\ndata: [DONE]\n\n"
                    ).encode()
                )
            except OSError:
                pass
            return
        for event in (
            {"choices": [{"delta": {"content": "合成回覆：收到。"}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ):
            self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, format: str, *args: object) -> None:
        pass


def load_fixture() -> Any:
    spec = importlib.util.spec_from_file_location("t10_d57_probe", ORIGINAL)
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run_dir = OUT / "run"
    run_dir.mkdir(exist_ok=True)
    module.OUT = run_dir
    return module


def step(name: str, ok: bool, **detail: Any) -> None:
    STEPS.append(
        {
            "step": name,
            "result": "PASS" if ok else "FAIL",
            "at_utc": datetime.now(UTC).isoformat(),
            **detail,
        }
    )
    (OUT / "STEPS.json").write_text(json.dumps(STEPS, ensure_ascii=False, indent=1) + "\n")
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    assert ok, (name, detail)


class Watch:
    """Browser-side side-effect counters: non-GET requests, sockets, renderer reloads, audio."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.mutations: list[str] = []
        self.sockets: list[str] = []
        self.renderer_navigations = 0
        page.on("request", self._request)
        page.on("websocket", lambda ws: self.sockets.append(ws.url.split("?")[0]))
        page.on("framenavigated", self._frame)

    def _request(self, request: Any) -> None:
        if request.method != "GET" and "/v1/session" not in request.url:
            self.mutations.append(f"{request.method} {request.url.split('?')[0]}")

    def _frame(self, frame: Any) -> None:
        if frame != self.page.main_frame and "/live2d/" in frame.url:
            self.renderer_navigations += 1

    def mark(self) -> tuple[int, int, int]:
        return len(self.mutations), len(self.sockets), self.renderer_navigations

    def audio_playing(self) -> bool:
        return bool(
            self.page.evaluate(
                "() => [...document.querySelectorAll('audio')].some(a => !a.paused)"
                " || (typeof ttsAudio !== 'undefined' && ttsAudio && !ttsAudio.paused)"
            )
        )


def nav(page: Page, name: str) -> None:
    page.click(f".primary-nav a[data-nav='{name}']") if page.locator(
        f".primary-nav a[data-nav='{name}']"
    ).count() else page.evaluate("n => navigateToPage(n)", name)
    page.wait_for_function("n => activePage === n", arg=name)


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.jpg"), type="jpeg", quality=70)


def wait_text(page: Page, selector: str, text: str, timeout: float = 15000) -> None:
    page.wait_for_function(
        "([s, t]) => (document.querySelector(s)?.textContent || '').includes(t)",
        arg=[selector, text],
        timeout=timeout,
    )


def renderer_ready(page: Page) -> dict[str, Any]:
    wait_text(page, "#renderer-status", "Live2D 已就緒", 30000)
    frame = page.frame_locator("#companion")
    canvas = frame.locator("canvas").first
    canvas.wait_for(timeout=15000)
    image = page.locator("#companion").screenshot(type="png")
    return {
        "renderer_status": page.inner_text("#renderer-status"),
        "canvas_present": True,
        "renderer_png_bytes": len(image),
    }


def send(page: Page, text: str) -> None:
    before = page.locator("#messages .message.assistant").count()
    page.fill("#text", text)
    page.click("#chat button[type=submit]")
    page.wait_for_function(
        "n => { const a = [...document.querySelectorAll('#messages .message.assistant')];"
        " return a.length > n && a.at(-1).textContent.trim().length > 0; }",
        arg=before,
        timeout=20000,
    )


def run(probe: Any) -> None:
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    assert executable
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=executable,
            headless=True,
            args=[
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 860})
            page = context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            watch = Watch(page)
            page.goto(probe.origin + "/#/chat")
            page.wait_for_function("() => controlAuthenticated === true", timeout=15000)
            ready = renderer_ready(page)
            sockets = list(watch.sockets)
            step(
                "real_live2d_renderer_and_single_body_owner",
                watch.renderer_navigations == 1
                and sum(url.endswith("/ws/body") for url in sockets) == 1
                and sum(url.endswith("/ws/control") for url in sockets) == 1,
                **ready,
                sockets=sockets,
                renderer_loads=watch.renderer_navigations,
            )
            shot(page, "01-chat-live2d")

            # Navigation sweep: zero mutations, sockets, renderer reloads or audio.
            before = watch.mark()
            for name in [*PAGES, "chat"]:
                nav(page, name)
            page.go_back()
            page.go_back()
            page.go_forward()
            page.wait_for_timeout(300)
            nav(page, "chat")
            after = watch.mark()
            step(
                "navigation_has_no_resend_socket_renderer_restart_or_audio",
                before == after and not watch.audio_playing(),
                before=before,
                after=after,
                renderer_still_ready="Live2D 已就緒" in page.inner_text("#renderer-status"),
            )

            # Flow 1: chat -> task -> approve -> result -> chat.
            send(page, "你好")
            history = page.inner_text("#messages")
            nav(page, "tasks")
            page.click("#goal-task-refresh")
            page.wait_for_function(
                "() => !document.querySelector('#goal-task-create').disabled", timeout=10000
            )
            page.fill("#goal-task-paths", "notes.md")
            page.click("#goal-task-create")
            wait_text(page, "#goal-task-items", "待批准（尚未執行）")
            assert probe.reads() == 0
            page.click("#goal-task-items a:has-text('查看任務詳情')")
            page.wait_for_function("() => /^#\\/tasks\\/[0-9a-f-]{36}$/.test(location.hash)")
            shot(page, "02-task-detail-proposed")
            page.click("#goal-task-items button:has-text('批准這些檔案的唯讀任務')")
            wait_text(page, "#goal-task-items", "閱讀完成", 20000)
            result = page.inner_text("#goal-task-items")
            shot(page, "03-task-detail-completed")
            goal = probe.snapshot()["goals"][0]
            page.click("#goal-task-back")
            page.wait_for_function("() => location.hash === '#/tasks'")
            before = watch.mark()
            nav(page, "chat")
            step(
                "flow1_chat_task_result_chat",
                goal["state"] == "completed"
                and probe.reads() == 1
                and "Review a synthetic note" in result
                and "TODO: Keep provenance" in result
                and page.inner_text("#messages") == history
                and watch.mark() == before,
                goal_state=goal["state"],
                runtime_reads=probe.reads(),
                sources_visible=["第 2 行", "第 4 行"],
                chat_history_kept=True,
            )

            # Flow 2: remember via chat -> search -> correct -> delete -> provenance.
            send(page, "記住：我喜歡喝無糖茶")
            nav(page, "memory")
            page.fill("#memory-query", "無糖茶")
            page.click("#memory-search-form button[type=submit]")
            wait_text(page, "#memory-search-status", "顯示 1 筆符合的記憶")
            card = page.inner_text("#memory-items")
            shot(page, "04-memory-search")
            page.once("dialog", lambda dialog: dialog.accept("我喜歡喝冰的無糖茶"))
            page.click("#memory-items button:has-text('更正')")
            wait_text(page, "#memory-items", "冰的無糖茶")
            status, memories = probe.request("/v1/memories?limit=100")
            corrected = memories["items"][0]
            assert status == 200 and corrected["revision"] == 2
            assert corrected["text"] == "我喜歡喝冰的無糖茶"
            corrected_card = page.inner_text("#memory-items")
            page.once("dialog", lambda dialog: dialog.accept())
            page.click("#memory-items button:has-text('刪除記憶')")
            page.wait_for_function(
                "() => document.querySelectorAll('#memory-items button').length === 0"
            )
            _, remaining = probe.request("/v1/memories?limit=100&query=" + "%E7%84%A1%E7%B3%96")
            shot(page, "05-memory-deleted")
            step(
                "flow2_memory_search_correct_delete",
                "第 1 版" in card
                and "來源" in card
                and "第 2 版" in corrected_card
                and remaining["items"] == [],
                first_card_has_source=True,
                corrected_revision=2,
                remaining_after_delete=0,
            )

            # Flow 3: settings -> permissions -> stop tools -> visible + enforced -> restore.
            nav(page, "settings")
            page.click(".destination-list a[data-nav='permissions']")
            page.wait_for_function("() => activePage === 'permissions'")
            page.wait_for_selector("#switches button:has-text('電腦與工具操作：已開啟')")
            with page.expect_navigation():
                page.click("#switches button:has-text('電腦與工具操作：已開啟')")
            page.wait_for_function("() => controlAuthenticated === true", timeout=15000)
            page.wait_for_selector("#switches button:has-text('電腦與工具操作：已關閉')")
            shot(page, "06-tools-stopped")
            probe.token = None
            tools_stopped = probe.snapshot()["available"] is False
            nav(page, "tasks")
            page.click("#goal-task-refresh")
            page.wait_for_timeout(800)
            create_disabled = page.locator("#goal-task-create").is_disabled()
            nav(page, "permissions")
            with page.expect_navigation():
                page.click("#switches button:has-text('電腦與工具操作：已關閉')")
            page.wait_for_function("() => controlAuthenticated === true", timeout=15000)
            page.wait_for_selector("#switches button:has-text('電腦與工具操作：已開啟')")
            probe.token = None
            tools_restored = probe.snapshot()["available"] is True
            puts = [m for m in watch.mutations if m.startswith("PUT ")]
            step(
                "flow3_settings_stop_tools",
                create_disabled
                and len(puts) == 2
                and tools_stopped
                and tools_restored
                and probe.reads() == 1,
                puts=puts,
                create_disabled_while_stopped=create_disabled,
                server_tasks_unavailable_while_stopped=tools_stopped,
                server_tasks_available_after_restore=tools_restored,
                runtime_reads=probe.reads(),
            )

            # Cancel: stop button halts a streaming reply; late tail never resurrects.
            nav(page, "chat")
            calls_before = len(MODEL_CALLS)
            page.fill("#text", "請慢慢回答")
            page.click("#chat button[type=submit]")
            wait_text(page, "#messages", "合成前半段", 10000)
            page.click("#cancel")
            page.wait_for_timeout(4500)
            transcript = page.inner_text("#messages")
            step(
                "cancel_stops_reply_without_late_output",
                "合成後半段" not in transcript
                and len(MODEL_CALLS) == calls_before + 1
                and not watch.audio_playing(),
                model_calls_for_turn=len(MODEL_CALLS) - calls_before,
            )

            # Disconnect on the same open page: visible state, manual reconnect, no resend.
            turns_before = [m for m in watch.mutations if "/turns" in m]
            calls_before = len(MODEL_CALLS)
            probe.stop()
            wait_text(page, "#connection", "連線中斷", 15000)
            shot(page, "07a-disconnected")
            probe.token = None
            probe.start()
            page.wait_for_timeout(1500)
            page.click("#connection")
            wait_text(page, "#connection", "已連線", 15000)
            step(
                "disconnect_visible_reconnect_without_resend",
                [m for m in watch.mutations if "/turns" in m] == turns_before
                and len(MODEL_CALLS) == calls_before
                and "合成後半段" not in page.inner_text("#messages"),
                turn_posts=len(turns_before),
                model_calls_during_reconnect=len(MODEL_CALLS) - calls_before,
            )
            context.close()

            # Fresh 375px browser after the restart: saved task kept, deleted memory stays deleted.
            context = browser.new_context(viewport={"width": 375, "height": 760})
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            watch = Watch(page)
            page.goto(probe.origin + "/#/tasks")
            page.wait_for_function("() => controlAuthenticated === true", timeout=15000)
            page.click("#goal-task-refresh")
            wait_text(page, "#goal-task-items", "閱讀完成")
            _, remaining = probe.request("/v1/memories?limit=100")
            shot(page, "07-restart-375-tasks")
            nav(page, "chat")
            renderer_ready_after = renderer_ready(page)["renderer_status"]
            shot(page, "08-restart-375-chat")
            step(
                "restart_keeps_state_without_replay",
                probe.reads() == 0
                and remaining["items"] == []
                and not watch.audio_playing()
                and not [m for m in watch.mutations if "goal-tasks" in m],
                runtime_reads_after_restart=probe.reads(),
                memories=0,
                renderer_status=renderer_ready_after,
            )
            step("no_page_errors", errors == [], errors=errors)
            context.close()
        finally:
            browser.close()


def main() -> None:
    assert (LIVE2D / "index.html").is_file(), "licensed local Live2D sample missing"
    fixture = load_fixture()
    probe = fixture.Probe()
    env = {
        key: value
        for key, value in probe.env.items()
        if key == "SIRO_CONTEXT_TOKEN_BUDGET_ENABLED"
        or not any(
            marker in key.upper()
            for marker in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
        )
    }
    env.pop("SIRO_OLLAMA_MODEL", None)
    model = ThreadingHTTPServer(("127.0.0.1", 0), SyntheticModel)
    threading.Thread(target=model.serve_forever, daemon=True).start()
    env.update(
        SIRO_LIVE2D_DIST=str(LIVE2D),
        SIRO_MEMORY_INGRESS_ENABLED="1",
        SIRO_OPENAI_BASE_URL=f"http://127.0.0.1:{model.server_port}",
        SIRO_OPENAI_MODEL="synthetic-loopback",
        SIRO_OPENAI_API_KEY="synthetic-loopback-not-a-secret",  # pragma: allowlist secret
    )
    probe.env = env
    probe.receipt.update(
        task="T10-UI-01 integrated acceptance",
        model="synthetic loopback OpenAI-compatible SSE (fixed reply)",
        renderer="licensed local Cubism Haru sample (not in Git)",
        started=time.time(),
    )
    try:
        probe.start()
        run(probe)
        probe.receipt["browser_acceptance"] = "PASS"
    finally:
        probe.close()
        model.shutdown()
        probe.receipt["synthetic_model_calls"] = len(MODEL_CALLS)
        probe.save()
        summary = {
            "synthetic_model_calls": len(MODEL_CALLS),
            "steps": len(STEPS),
            "failed": [s["step"] for s in STEPS if s["result"] != "PASS"],
            "temporary_removed": probe.receipt.get("temporary_removed"),
            "copied_package_unchanged": probe.receipt.get("copied_package_unchanged"),
        }
        (OUT / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
