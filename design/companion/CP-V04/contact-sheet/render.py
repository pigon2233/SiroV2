"""Render every clip of the SIRO VRM activity pack on the registered owner model as contact sheets.

Usage (WSL): uv run python render.py <repo> <out-dir> <chromium>. Needs a prepared renderer
(scripts/prepare_vrm_renderer.py) and the registered model in config/body-assets/siro-vrm/.
Clips are played as delivered (no renderer life layers, notebook prop or gaze); spring bones run
at 30 fps from the clip start so clothing settles as it would.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

from playwright.sync_api import Route, sync_playwright

PAGE = Path(__file__).with_name("sheet.html")
FRONT = (0, 0.85, 4.2)
THREE_QUARTER = (2.6, 1.0, 3.2)
SIDE = (4.2, 0.8, 0.0)
TIMES = [0.0, 0.2, 0.4, 0.6, 0.8, 0.97]


def views(names: list[str]) -> list[dict[str, object]]:
    half = len(names) // 2 + 1
    close = [i / 10 for i in range(10)]
    return [
        {"name": "front-1", "camera": FRONT, "clips": names[:half], "times": TIMES},
        {"name": "front-2", "camera": FRONT, "clips": names[half:], "times": TIMES},
        {"name": "threequarter-1", "camera": THREE_QUARTER, "clips": names[:half], "times": TIMES},
        {"name": "threequarter-2", "camera": THREE_QUARTER, "clips": names[half:], "times": TIMES},
        {
            "name": "walk-side",
            "camera": SIDE,
            "clips": ["walk_start", "walk", "walk_stop", "turn_step"],
            "times": [i / 8 for i in range(8)],
            "target": 0.7,
        },
        {
            "name": "wave-close-front",
            "camera": (0, 1.35, 1.6),
            "target": 1.3,
            "clips": ["wave", "bye"],
            "times": close,
        },
        {
            "name": "wave-close-side",
            "camera": (1.6, 1.35, 0.0),
            "target": 1.3,
            "clips": ["wave"],
            "times": close,
        },
    ]


def main() -> None:
    repo, out, chromium = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    out.mkdir(parents=True, exist_ok=True)
    dist = repo / "models" / "vrm-renderer"
    model = repo / "config" / "body-assets" / "siro-vrm" / "model.vrm"
    pack_file = repo / "assets" / "companion" / "siro-vrm" / "0.1.0" / "pack.json"
    pack = json.loads(pack_file.read_text(encoding="utf-8"))["activities"]

    def serve(route: Route) -> None:
        path = route.request.url.split("//", 1)[1].split("/", 1)[1].split("?")[0]
        if path in ("", "sheet.html"):
            route.fulfill(body=PAGE.read_bytes(), content_type="text/html")
            return
        if path == "model.vrm":
            route.fulfill(body=model.read_bytes(), content_type="model/gltf-binary")
            return
        file = (dist / path).resolve()
        if file.is_relative_to(dist.resolve()) and file.is_file():
            kind = "text/javascript" if file.suffix == ".js" else "application/octet-stream"
            route.fulfill(body=file.read_bytes(), content_type=kind)
            return
        route.fulfill(status=404, body="missing")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=chromium,
            headless=True,
            args=[
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
                "--ignore-gpu-blocklist",
            ],
        )
        page = browser.new_page()
        page.route("http://sheet.test/**", serve)
        page.goto("http://sheet.test/sheet.html")
        page.wait_for_function("window.sheetReady", timeout=60000)
        names = [entry["activity"] for entry in pack]
        sheets = page.evaluate("([p, v]) => window.renderSheet(p, v)", [pack, views(names)])
        for name, url in sheets.items():
            (out / f"{name}.png").write_bytes(base64.b64decode(url.split(",", 1)[1]))
            print("wrote", name)
        browser.close()


if __name__ == "__main__":
    main()
