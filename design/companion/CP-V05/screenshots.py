"""Screenshot the CP-V05 reference mock at desktop width, 320 px and 200% zoom.

Usage (WSL): uv run python design/companion/CP-V05/screenshots.py <chromium>
200% zoom is a 1280x800 window at device scale 2, i.e. a 640x400 CSS viewport.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
SIZES = {
    "desktop": ({"width": 1280, "height": 800}, 1),
    "320": ({"width": 320, "height": 720}, 2),
    "zoom200": ({"width": 640, "height": 400}, 2),
}
SCENARIOS = ["normal", "empty", "offline", "gap", "denied", "unavailable"]


def main() -> None:
    out = HERE / "screens"
    out.mkdir(exist_ok=True)
    url = (HERE / "reference.html").resolve().as_uri()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=sys.argv[1], headless=True)
        for size, (viewport, scale) in SIZES.items():
            page = browser.new_page(viewport=viewport, device_scale_factor=scale)
            for scenario in SCENARIOS if size != "zoom200" else ["normal", "offline"]:
                page.goto(f"{url}?scenario={scenario}")
                page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
                wide = page.evaluate("document.documentElement.scrollWidth > innerWidth")
                print(size, scenario, "horizontal scroll" if wide else "fits")
                page.screenshot(path=str(out / f"{scenario}-{size}.png"), full_page=True)
            page.close()
        page = browser.new_page(viewport={"width": 1000, "height": 760})
        page.goto(f"{url}?bubble=1")
        page.screenshot(path=str(out / "bubbles.png"), full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
