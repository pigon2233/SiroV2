#!/usr/bin/env python3
"""Run the T24 observe-act-readback flow in a visible local Chrome window."""

from __future__ import annotations

import asyncio
import json
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from siro.adapters.browser import ScopedBrowserDriver
from siro.adapters.vision import PixelScreenAnalyzer

PAGE = """<!doctype html><html><head><title>SIRO T24 visible demo</title></head>
<body style="margin:0;min-height:100vh;background:#1450d2;color:white;font:24px sans-serif">
<main style="padding:4rem"><label for="task">Task name</label>
<input id="task"><button id="save">Save locally</button><p id="result">Waiting</p></main>
<script>save.onclick=()=>result.textContent='Saved '+task.value</script></body></html>"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args


async def run(origin: str) -> dict[str, object]:
    async with ScopedBrowserDriver((origin,), headless=False) as browser:
        await browser.navigate(origin)
        field = await browser.select("textbox", "Task name")
        await browser.fill(field, "T24 verified")
        save = await browser.select("button", "Save locally")
        result = await browser.click(save)
        if "Saved T24 verified" not in result.text:
            raise RuntimeError("visible browser readback did not match the requested action")
        image = await browser.screenshot(result.screen_version)
        visual = await PixelScreenAnalyzer().analyze(image)
        await asyncio.sleep(1)
        return {
            "url": result.url,
            "readback": "Saved T24 verified",
            "screen_version": result.screen_version,
            "visual": {
                "description": visual.description,
                "source": visual.source,
                "confidence": visual.confidence,
                "width": visual.width,
                "height": visual.height,
            },
        }


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "index.html").write_text(PAGE)
        handler = lambda *args: QuietHandler(*args, directory=directory)  # noqa: E731
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = asyncio.run(run(f"http://127.0.0.1:{server.server_port}"))
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    main()
