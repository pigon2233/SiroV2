from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import Page, sync_playwright
from test_frontend_reflow import INDEX, LONG, PAGES, STRESS

# WCAG 1.4.3 text (4.5:1, large 3:1) and 1.4.11 text-entry boundaries (3:1).
# Disabled controls are exempt by WCAG; the page enables every control before auditing.
CONTRAST = r"""
() => {
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const blend = (top, bottom) => [0, 1, 2].map(i => top[i] * top[3] + bottom[i] * (1 - top[3]))
    .concat(1);
  const lum = c => { const f = v => { v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b);
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const background = el => { const stack = [];
    for (let p = el; p; p = p.parentElement) { const c = parse(getComputedStyle(p).backgroundColor);
      if (c && c[3] > 0) { stack.push(c); if (c[3] >= 1) break; } }
    let bg = [255, 255, 255, 1]; for (const c of stack.reverse()) bg = blend(c, bg); return bg; };
  const opacity = el => { let o = 1;
    for (let p = el; p; p = p.parentElement) o *= +getComputedStyle(p).opacity; return o; };
  const shown = el => { const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('[hidden],[inert]') || !shown(el)) continue;
    const text = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (!text) continue;
    const s = getComputedStyle(el), bg = background(el), fg = parse(s.color);
    const shownColor = blend([fg[0], fg[1], fg[2], fg[3] * opacity(el)], bg);
    const size = parseFloat(s.fontSize);
    const large = size >= 24 || (+s.fontWeight >= 700 && size >= 18.66);
    const value = ratio(shownColor, bg);
    if (value < (large ? 3 : 4.5)) out.push(`text ${el.id || el.tagName} ${value.toFixed(2)}`);
  }
  for (const el of document.querySelectorAll('input:not([type=checkbox]),textarea')) {
    if (el.closest('[hidden],[inert]') || !shown(el)) continue;
    const box = parseFloat(getComputedStyle(el).borderTopWidth) ? el : el.parentElement;
    const bg = background(box.parentElement);
    const value = ratio(blend(parse(getComputedStyle(box).borderTopColor), bg), bg);
    if (value < 3) out.push(`boundary ${el.id} ${value.toFixed(2)}`);
    const placeholder = parse(getComputedStyle(el, '::placeholder').color);
    const own = background(el);
    if (el.placeholder && placeholder && ratio(blend(placeholder, own), own) < 4.5)
      out.push(`placeholder ${el.id}`);
  }
  return out;
}
"""

FOCUSED = r"""
() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const s = getComputedStyle(el), r = el.getBoundingClientRect();
  const bar = document.querySelector('.toolbar').getBoundingClientRect();
  return {id: el.id || `${el.tagName}:${(el.textContent || '').trim().slice(0, 12)}`,
    tag: el.tagName, outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 2,
    hidden: Boolean(el.closest('[hidden],[inert]')),
    covered: Boolean(el.closest('main')) && r.bottom <= bar.bottom + 1,
    offscreen: r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth};
}
"""


@contextmanager
def opened(width: int, height: int) -> Iterator[Page]:
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    assert executable, "accessibility check needs a local Chrome/Chromium"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(INDEX.as_uri() + "#/chat")
            page.evaluate(STRESS, LONG)
            yield page
        finally:
            browser.close()


def show(page: Page, name: str) -> None:
    page.evaluate("name => { location.hash = '#/' + name; }", name)
    page.wait_for_function(
        "name => document.querySelector('.page-view:not([hidden])')?.dataset.page"
        " === name.split('/')[0]",
        arg=name,
    )
    page.evaluate(
        "() => { for (const c of document.querySelectorAll('button,input,textarea'))"
        " c.disabled = false; document.activeElement?.blur(); scrollTo(0, 0); }"
    )


def test_text_and_text_entry_boundaries_meet_contrast_on_every_page() -> None:
    failures: dict[str, list[str]] = {}
    with opened(1280, 900) as page:
        page.evaluate("() => { document.querySelector('#activity-notice').hidden = false; }")
        for name in PAGES:
            show(page, name)
            if found := page.evaluate(CONTRAST):
                failures[name] = found
    assert failures == {}, json.dumps(failures, ensure_ascii=False, indent=1)


def test_tab_order_has_visible_uncovered_focus_and_skips_decorative_renderer() -> None:
    failures: list[str] = []
    for width, height in [(1280, 800), (320, 568)]:
        with opened(width, height) as page:
            for name in PAGES:
                show(page, name)
                seen: list[str] = []
                for _ in range(80):
                    page.keyboard.press("Tab")
                    focus = page.evaluate(FOCUSED)
                    if focus is None:
                        continue
                    if seen and focus["id"] == seen[0]:
                        break
                    seen.append(focus["id"])
                    bad = [key for key in ("hidden", "covered", "offscreen") if focus[key]]
                    if not focus["outline"]:
                        bad.append("no-outline")
                    if focus["tag"] == "IFRAME":
                        bad.append("renderer-in-tab-order")
                    if bad:
                        failures.append(f"{width} {name} {focus['id']} {bad}")
                assert "skip-to-content" in seen, (width, name, seen[:3])
                assert len(seen) == len(set(seen)), (width, name, "focus cycle repeated early")
    assert failures == [], "\n".join(failures)


def test_settings_pages_avoid_internal_jargon() -> None:
    html = INDEX.read_text(encoding="utf-8")
    for jargon in ("控制路徑", "WebKit 沙盒", "診斷資料與日常聊天", "動作包"):
        assert jargon not in html, jargon


def test_prompt_chips_fill_the_message_box_without_sending() -> None:
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    assert executable, "accessibility check needs a local Chrome/Chromium"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(INDEX.as_uri() + "#/chat")
            page.evaluate(
                "() => document.querySelectorAll('button,textarea')"
                ".forEach(b => b.removeAttribute('disabled'))"
            )
            page.click(".prompt-chips button:last-child")
            assert page.input_value("#text") == "你可以做什麼？"  # noqa: RUF001
            assert page.evaluate("document.activeElement.id") == "text"
            assert page.evaluate("document.querySelectorAll('#messages .message').length") == 0
        finally:
            browser.close()


def test_idle_console_shows_only_the_essentials() -> None:
    html = INDEX.read_text(encoding="utf-8")
    assert '<button id="cancel" type="button" hidden>' in html
    nav = html.split('aria-label="工作畫面"', 1)[1].split("</nav>", 1)[0]
    assert nav.count("data-nav=") == 4
    assert "context-panel" not in html
