from __future__ import annotations

import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import UnidentifiedImageError

from siro.adapters.browser import ScopedBrowserDriver
from siro.adapters.computer import ComputerActionError, ScopeViolation
from siro.adapters.vision import PixelScreenAnalyzer
from siro.core.outcomes import ActionOutcome

PAGE = b"""<!doctype html>
<html><head><title>T24 synthetic form</title></head>
<body style="margin:0;min-height:100vh;background:rgb(20,80,210);color:white">
<label for="name">Display name</label><input id="name">
<button id="save">Save</button>
<p id="result">Waiting</p>
<button id="pointer" style="position:absolute;left:20px;top:200px;width:180px;height:50px">
Pointer action</button><p id="pointer-result">Pointer waiting</p>
<script>
save.onclick=()=>result.textContent='Saved '+document.querySelector('#name').value;
pointer.onclick=()=>document.querySelector('#pointer-result').textContent='Pointer clicked';
</script>
</body></html>"""


class CapturingOutcomes:
    def __init__(self) -> None:
        self.values: list[tuple[str, ActionOutcome]] = []

    async def report_action(
        self,
        action_id: str,
        outcome: ActionOutcome,
        *,
        occurred_at: datetime,
        importance: float,
        controllability: float,
        expected: object | None = None,
        observed: object | None = None,
    ) -> None:
        del occurred_at, importance, controllability, expected, observed
        self.values.append((action_id, outcome))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "https://example.com/outside")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, _format: str, *args: object) -> None:
        del args


@pytest.mark.asyncio
async def test_t24_real_chrome_form_readback_scope_and_stale_targets() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    outcomes = CapturingOutcomes()
    try:
        async with ScopedBrowserDriver((origin,), outcome_reporter=outcomes) as browser:
            initial = await browser.navigate(origin)
            assert initial.title == "T24 synthetic form"
            assert "Waiting" in initial.text
            with pytest.raises(ScopeViolation):
                await browser.navigate("https://example.com/")
            with pytest.raises(ScopeViolation, match="request"):
                await browser.navigate(origin + "/redirect")
            await browser.navigate(origin)
            with pytest.raises(ComputerActionError, match="exactly one"):
                await browser.select("button", "Missing")

            field = await browser.select("textbox", "Display name")
            pressed = await browser.press(field, "A")
            assert pressed.screen_version != initial.screen_version
            with pytest.raises(ComputerActionError, match="screen changed"):
                await browser.fill(field, "stale write")

            field = await browser.select("textbox", "Display name")
            filled = await browser.fill(field, "SIRO", action_id="fill-1")
            assert filled.screen_version != initial.screen_version
            assert await browser.fill(field, "SIRO", action_id="fill-1") == filled
            with pytest.raises(ComputerActionError, match="reused"):
                await browser.fill(field, "different", action_id="fill-1")
            with pytest.raises(ComputerActionError, match="screen changed"):
                await browser.fill(field, "stale write")

            save = await browser.select("button", "Save")
            result = await browser.click(save, action_id="click-1")
            assert "Saved SIRO" in result.text
            with pytest.raises(ComputerActionError, match="screen changed"):
                await browser.click(save)

            pointer_result = await browser.pointer_click(80, 225, result.screen_version)
            assert "Pointer clicked" in pointer_result.text

            image = await browser.screenshot(pointer_result.screen_version)
            visual = await PixelScreenAnalyzer().analyze(image)
            assert visual.source == "pixel-screen-analyzer:v1"
            assert visual.width > 0 and visual.height > 0
            assert "blue" in visual.description
            assert visual.confidence > 0.5
            with pytest.raises(UnidentifiedImageError):
                await PixelScreenAnalyzer().analyze(b"not an image")
            assert outcomes.values == [
                ("fill-1", "confirmed"),
                ("click-1", "confirmed"),
            ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
