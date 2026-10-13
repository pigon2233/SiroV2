"""Real Chromium / real 300-second TTL; isolated synthetic gateway and tiny WAV only."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import socket
import time
import wave
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from playwright.async_api import async_playwright

from siro.adapters.body.web import WebSocketBodyTransport
from siro.services.presentation.gateway import GatewayHub, GatewayState, SessionTokens, create_app

OUTPUT = Path(__file__).resolve().parent


class CountedTokens(SessionTokens):
    def __init__(self) -> None:
        super().__init__()
        self.issued_at: dict[str, float] = {}

    def issue(self) -> tuple[str, float]:
        token, ttl = super().issue()
        self.issued_at[token] = time.monotonic()
        return token, ttl


class TinyWav:
    def __init__(self) -> None:
        self.calls = 0

    async def render(self, text: str, *, rate: float, pitch: float, energy: float) -> bytes:
        self.calls += 1
        target = io.BytesIO()
        with wave.open(target, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(bytes(2400))
        return target.getvalue()


async def verify(chromium: str | None) -> None:
    page_errors: list[str] = []
    result: dict[str, object] = {
        "status": "STARTING",
        "scope": "Actual index.html / Chromium / Uvicorn / real 300-second token lifetime",
        "backend": "Synthetic on_turn and silent 150ms WAV; no model, human voice, or Live2D claim",
        "isolation": "Ephemeral 127.0.0.1 only; no product service, database, provider or secrets",
    }

    def save() -> None:
        sanitized_errors = []
        for error in page_errors:
            for token in tokens.issued_at:
                error = error.replace(token, "<synthetic-token-redacted>")
            sanitized_errors.append(error)
        result["page_js_errors"] = sanitized_errors
        (OUTPUT / "ui-verification.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    tokens, hub, body, speech = CountedTokens(), GatewayHub(), WebSocketBodyTransport(), TinyWav()
    state = GatewayState()
    state.routes.update(
        model="synthetic:verification", tts="synthetic:tiny-wav", body="placeholder"
    )
    turns: list[str] = []
    http_requests: list[dict[str, object]] = []  # Token comparisons stay only in this process.
    websocket_counts: dict[str, int] = {}
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    listener.setblocking(False)
    port = listener.getsockname()[1]
    assert port != 8026
    origin = f"http://127.0.0.1:{port}"

    async def on_turn(session_id: str, text: str, input_mode: str) -> None:
        turns.append(text)
        stream = f"synthetic-{len(turns)}"
        for event in (
            {"type": "assistant_started"},
            {"type": "assistant_delta", "text": f"合成驗收第 {len(turns)} 輪: 已收到。"},
            {"type": "assistant_terminal", "state": "completed", "error": None},
        ):
            await hub.broadcast({**event, "session_id": session_id, "stream_id": stream})

    app = create_app(
        allowed_origins={origin},
        state=state,
        hub=hub,
        tokens=tokens,
        body_transport=body,
        text_to_speech=speech,
        on_turn=on_turn,
    )

    @app.middleware("http")
    async def observe(request, call_next):
        response = await call_next(request)
        http_requests.append(
            {
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "token": request.headers.get("authorization", "").removeprefix("Bearer "),
            }
        )
        return response

    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    browser = None
    verification_passed = False
    save()
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if serving.done():
                    await serving
                await asyncio.sleep(0.05)
        async with async_playwright() as playwright:
            options = {"headless": True, "args": ["--autoplay-policy=no-user-gesture-required"]}
            if chromium:
                options["executable_path"] = chromium
            browser = await playwright.chromium.launch(**options)
            context = await browser.new_context(viewport={"width": 1440, "height": 1050})
            await context.add_init_script("""(() => {
              const NativeAudio = window.Audio;
              window.__verificationAudio = [];
              window.Audio = function(...args) {
                const audio = new NativeAudio(...args);
                const check = {played:false, ended:false, error:false};
                window.__verificationAudio.push(check);
                audio.addEventListener('playing', () => check.played = true);
                audio.addEventListener('ended', () => check.ended = true);
                audio.addEventListener('error', () => check.error = true);
                return audio;
              };
              window.Audio.prototype = NativeAudio.prototype;
              Object.setPrototypeOf(window.Audio, NativeAudio);
            })();""")
            page = await context.new_page()
            page.on("pageerror", lambda error: page_errors.append(str(error)))

            def websocket_opened(websocket) -> None:
                path = urlsplit(websocket.url).path
                websocket_counts[path] = websocket_counts.get(path, 0) + 1

            page.on("websocket", websocket_opened)
            await page.goto(origin, wait_until="networkidle")
            loaded_script = await page.locator("script").text_content()
            assert loaded_script is not None

            def source_script_hash() -> str:
                path = OUTPUT.parents[2] / "src/siro/services/presentation/static/index.html"
                text = path.read_text(encoding="utf-8").split("<script>", 1)[1]
                return hashlib.sha256(text.split("</script>", 1)[0].encode()).hexdigest()

            loaded_hash = hashlib.sha256(loaded_script.encode()).hexdigest()
            result.update(
                loaded_main_script_sha256=loaded_hash,
                source_main_script_sha256_at_load=source_script_hash(),
                verification_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            )
            assert result["source_main_script_sha256_at_load"] == loaded_hash
            await page.wait_for_function(
                "document.querySelector('#connection').textContent === '已連線'"
            )
            async with asyncio.timeout(5):
                while not body.connected:
                    await asyncio.sleep(0.05)
            await page.locator("#voice-output").check()

            async def submit(number: int) -> None:
                await page.locator("#text").fill(f"合成 session 驗收訊息 {number}")
                await page.locator("#chat button[type=submit]").click()
                await page.wait_for_function(
                    "n => document.querySelectorAll('.message.assistant').length === n && "
                    "window.__verificationAudio.length === n && "
                    "window.__verificationAudio.every(a => a.played && a.ended && !a.error)",
                    arg=number,
                    timeout=10000,
                )
                assert len(turns) == number and speech.calls == number

            await submit(1)
            original_body = body._socket
            original_control = tuple(hub._clients)
            initial_websockets = dict(websocket_counts)
            initial_issues = len(tokens.issued_at)
            assert hub.client_count == 1
            assert initial_websockets == {"/ws/control": 1, "/ws/body": 1}
            assert initial_issues == 2
            assert not page_errors
            first_request = next(r for r in http_requests if str(r["path"]).endswith("/turns"))
            first_token = str(first_request["token"])
            started = tokens.issued_at[first_token]
            assert tokens._ttl == 300
            await page.screenshot(path=str(OUTPUT / "ui-before-expiry.png"), full_page=True)
            result.update(
                status="WAITING_REAL_TTL",
                initial_turns=1,
                initial_tts=1,
                initial_token_issues=initial_issues,
                initial_websockets=initial_websockets,
            )
            save()
            while time.monotonic() - started <= 306:
                remaining = 306.1 - (time.monotonic() - started)
                await asyncio.sleep(min(25, max(0.1, remaining)))
                elapsed = time.monotonic() - started
                result["elapsed_seconds"] = round(elapsed, 3)
                save()
                print(
                    f"REAL_TTL_WAIT elapsed={elapsed:.1f}s token_issues={len(tokens.issued_at)}",
                    flush=True,
                )
            assert not tokens.valid(first_token)
            await submit(2)
            turn_requests = [r for r in http_requests if str(r["path"]).endswith("/turns")]
            assert [r["status"] for r in turn_requests] == [200, 200]
            changed = turn_requests[0]["token"] != turn_requests[1]["token"]
            assert changed and len(tokens.issued_at) == initial_issues + 1
            assert body._socket is original_body and body.connected
            assert tuple(hub._clients) == original_control
            assert websocket_counts == initial_websockets
            result.update(
                status="REAL_TTL_PASSED",
                elapsed_seconds=round(time.monotonic() - started, 3),
                after_expiry_turns=len(turns),
                after_expiry_tts=speech.calls,
                after_expiry_token_issues=len(tokens.issued_at),
                http_token_changed=changed,
                healthy_control_preserved=True,
                healthy_body_preserved=True,
                healthy_websockets_preserved=True,
            )
            await page.screenshot(path=str(OUTPUT / "ui-after-expiry.png"), full_page=True)
            save()

            # Cache invalidation is an isolated restart-auth simulation, not a real service restart.
            tokens._tokens.clear()
            before_issues = len(tokens.issued_at)
            before_requests = len(turn_requests)
            await submit(3)
            turn_requests = [r for r in http_requests if str(r["path"]).endswith("/turns")]
            assert [r["status"] for r in turn_requests[before_requests:]] == [401, 200]
            assert len(tokens.issued_at) == before_issues + 1
            assert tuple(hub._clients) == original_control and body._socket is original_body
            result["synthetic_token_invalidation"] = {
                "turn_http_statuses": [401, 200],
                "accepted_turns": 1,
                "additional_token_issues": 1,
                "additional_tts": 1,
                "healthy_control_and_body_preserved": True,
            }
            save()

            before_counts = (len(turns), speech.calls, len(tokens.issued_at))
            control_count = websocket_counts["/ws/control"]
            channel = next(iter(hub._clients.values()))
            await channel.socket.close(code=1012, reason="synthetic control reconnect")
            async with asyncio.timeout(10):
                while not (hub.client_count == 1 and tuple(hub._clients) != original_control):
                    await asyncio.sleep(0.05)
            await page.wait_for_function(
                "document.querySelector('#connection').textContent === '已連線'"
            )
            await asyncio.sleep(1)
            assert websocket_counts["/ws/control"] == control_count + 1
            assert before_counts == (len(turns), speech.calls, len(tokens.issued_at))
            assert body._socket is original_body and body.connected
            result.update(
                status="CHECKS_PASSED_AWAITING_CLEANUP",
                final_turns=len(turns),
                final_tts=speech.calls,
                final_token_issues=len(tokens.issued_at),
                final_websockets=websocket_counts,
                control_reconnect={
                    "new_control_connections": 1,
                    "replayed_turns": 0,
                    "replayed_tts": 0,
                    "additional_token_issues": 0,
                    "body_owner_preserved": True,
                },
                native_audio=await page.evaluate("window.__verificationAudio"),
                token_retained_count=len(tokens._tokens),
                source_main_script_sha256_at_finish=source_script_hash(),
            )
            assert result["source_main_script_sha256_at_finish"] == loaded_hash
            assert not page_errors
            await page.screenshot(path=str(OUTPUT / "ui-after-reconnect.png"), full_page=True)
            save()
            await browser.close()
            browser = None
        verification_passed = True
    except BaseException as error:
        result.update(status="FAILED", failure_type=type(error).__name__)
        save()
        raise
    finally:
        try:
            try:
                if browser is not None and browser.is_connected():
                    await browser.close()
            finally:
                try:
                    await body.detach(reason="synthetic verification cleanup")
                finally:
                    server.should_exit = True
                    try:
                        await asyncio.wait_for(serving, 10)
                    finally:
                        listener.close()
            result["cleanup"] = {
                "browser_closed": browser is None or not browser.is_connected(),
                "body_detached": not body.connected,
                "control_clients_remaining": hub.client_count,
                "uvicorn_stopped": serving.done() and not serving.cancelled(),
                "listener_closed": listener.fileno() == -1,
            }
            assert hub.client_count == 0 and not body.connected
            assert browser is None or not browser.is_connected()
        except BaseException as error:
            result.update(status="FAILED_CLEANUP", cleanup_failure_type=type(error).__name__)
            save()
            raise
        else:
            if verification_passed:
                result["status"] = "PASS"
            save()
            print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chromium", help="Explicit installed Chromium executable, if required")
    asyncio.run(verify(parser.parse_args().chromium))
