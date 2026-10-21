from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Request, sync_playwright

INDEX = Path(__file__).parents[2] / "src/siro/services/presentation/static/index.html"
# 320/375/414/768 narrow widths plus 1280x800 and 1920x1080 at 200% page zoom.
VIEWPORTS = [(320, 568), (375, 667), (414, 896), (768, 1024), (640, 400), (960, 540)]
DETAIL = "tasks/0123abcd-0000-4000-8000-00000000abcd"
PAGES = ["chat", "tasks", DETAIL, "activity", "memory", "capabilities", "computer", "skills"]
PAGES += ["settings", "permissions", "system"]
LONG = "這是一段很長的繁體中文合成測試內容用來檢查窄窗換行" * 3
LONG += " https://example.invalid/" + "a" * 120

# Synthetic long data rendered through the production functions, never private data.
STRESS = r"""
L => {
  const longPath = 'docs/' + '長路徑資料夾名稱'.repeat(10) + '/' + 'x'.repeat(120) + '.md';
  goalTaskViews = [{goal_id: '0123abcd-0000-4000-8000-00000000abcd', state: 'proposed',
    next_step: null, revision: 3, steps_used: 2, max_steps: 8,
    deadline: '2026-10-18T23:59:59+08:00',
    task: {profile: goalTaskProfile, paths: [longPath, 'notes.md'],
      approved_at: '2026-10-18T10:00:00+08:00', pause_reason: 'interrupted_restart',
      intent_path: null,
      observations: [{path: longPath, status: 'completed', sha256: 'a'.repeat(64),
        read_at: '2026-10-18T10:01:00+08:00', truncated: true,
        matches: [{line: 12, text: L.slice(0, 250)}], error: null}]}}];
  goalTaskHasSnapshot = true; renderGoalTasks();
  renderCapabilities([{name: 'x', display_name: L, availability: 'unavailable',
    reason_code: 'not_ready', risk_level: 'computer', model_visible: false}]);
  renderSnapshot({authorization_mode: 'safe', identity: {name: L}, health: {}, routes: {},
    kill_switches: {cloud: true, tools: true, microphone: false,
      ['unknown_switch_' + 'y'.repeat(40)]: true}});
  renderToolProposal({proposal_id: 'p1', capability: 'browser.navigate+read', scope: L,
    target: 'https://example.invalid/' + 'b'.repeat(200), risk: L,
    automatic_approval_blocked: 'prior_outcome_unknown'});
  const longUrl = {url: 'https://example.invalid/' + 'd'.repeat(200), redacted: true};
  const tool = state => ({capability: 'browser.navigate+read', state, dispatched: true,
    error: state === 'failed' ? 'Error' : null, created_at: '2026-10-18T10:00:00+08:00',
    target: longUrl, network: {coverage: 'browser_adapter', requests: [{requested: longUrl,
      final: longUrl, redirected: true, status: 'unknown'}],
      gaps: ['http_status_not_captured', 'subresource_requests_not_listed']}});
  const activity = (id, state) => ({activity_id: id, kind: 'agent_run', origin: 'owner_request',
    state, reason: id + L, reason_truncated: true, error: null, created_at: '2026-10-18T10:00:00+08:00',
    updated_at: '2026-10-18T10:0' + id + ':00+08:00', tools: [tool(state)],
    coverage: {tools: 'journal', network: ['browser_adapter']}});
  activityView.items = new Map(['1', '2', '3'].map((id, i) =>
    [id, activity(id, ['running', 'unknown', 'failed'][i])]));
  activityView.fetchedAt = '2026-10-18T10:05:00+08:00'; activityView.status = 'ok';
  activityView.truncated = true; renderActivity();
  for (const details of document.querySelectorAll('#activity-body details')) details.open = true;
  appendMessage('user', L); appendMessage('assistant', L);
  productRequest = async () => ({items: [{memory_id: 'm1', text: L, revision: 2,
    source_event_ids: ['evt-' + 'c'.repeat(60)]}]});
  return refreshMemories();
}
"""

# Visible elements past the viewport edge are cut off by html/body overflow-x:clip,
# so they disappear instead of scrolling.
PROBE = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const shown = el => { const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  const scrolls = el => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      if (getComputedStyle(p).overflowX === 'visible') continue;
      const r = p.getBoundingClientRect();
      if (r.left >= -0.5 && r.right <= vw + 0.5) return true;
    }
    return false;
  };
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('[hidden],[inert],.skip-link') || !shown(el)) continue;
    const r = el.getBoundingClientRect();
    if ((r.right > vw + 0.5 || r.left < -0.5) && !scrolls(el))
      out.push(`${el.tagName.toLowerCase()}#${el.id} ${Math.round(r.left)}..${Math.round(r.right)} `
        + (el.textContent || '').trim().slice(0, 24));
  }
  const page = document.querySelector('.page-view:not([hidden])');
  const heading = page.querySelector('[data-page-heading]').textContent;
  return {vw, page: page.dataset.page, heading, out};
}
"""


def requests_into(requests: list[str]) -> Callable[[Request], None]:
    def record(request: Request) -> None:
        if "/v1/" in request.url:
            requests.append(request.url)

    return record


def measure(stress: bool) -> list[dict[str, object]]:
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    assert executable, "reflow check needs a local Chrome/Chromium"
    rows: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True)
        try:
            for width, height in VIEWPORTS:
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()
                requests: list[str] = []
                page.on("request", requests_into(requests))
                page.goto(INDEX.as_uri() + "#/chat")
                if stress:
                    page.evaluate(STRESS, LONG)
                for name in PAGES:
                    page.evaluate("name => { location.hash = '#/' + name; }", name)
                    page.wait_for_function(
                        "name => document.querySelector('.page-view:not([hidden])')"
                        "?.dataset.page === name.split('/')[0]",
                        arg=name,
                    )
                    row = page.evaluate(PROBE)
                    row.update(viewport=f"{width}x{height}", requested=name)
                    rows.append(row)
                assert requests == []
                context.close()
        finally:
            browser.close()
    return rows


def assert_reflows(rows: list[dict[str, object]]) -> None:
    assert len(rows) == len(VIEWPORTS) * len(PAGES)
    failures = [row for row in rows if row["out"]]
    assert failures == [], json.dumps(failures, ensure_ascii=False, indent=1)
    for row in rows:
        assert row["page"] == str(row["requested"]).split("/")[0]
        if row["requested"] == DETAIL:
            assert row["heading"] == "任務詳情"


def test_every_page_reflows_at_narrow_and_200_percent_widths() -> None:
    assert_reflows(measure(stress=False))


def test_long_synthetic_content_from_production_renderers_stays_inside_viewport() -> None:
    assert_reflows(measure(stress=True))


# Owner report 2026-10-18: at 200% zoom the sticky sidebar cut off the skills/settings links.
SHORT_VIEWPORTS = [(1280, 600), (1100, 500), (960, 470), (960, 400), (901, 420), (640, 400)]
SHORT_VIEWPORTS += [(1100, 326), (1920, 540)]
NAV_REACH = """() => [...document.querySelectorAll('.primary-nav a')].flatMap(a => {
  const r = a.getBoundingClientRect(); // visible without scrolling: hidden scrollbars give no cue
  const x = r.left + r.width / 2, y = r.top + r.height / 2, hit = document.elementFromPoint(x, y);
  const side = document.querySelector('.sidebar');
  const wide = side.scrollWidth > side.clientWidth + 1 ? ['sidebar-horizontal-scroll'] : [];
  return (hit && a.contains(hit) && y >= 0 && y <= innerHeight ? [] : [a.dataset.nav]).concat(wide);
})"""


def test_every_navigation_link_is_reachable_on_short_zoomed_viewports() -> None:
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    assert executable, "reflow check needs a local Chrome/Chromium"
    failures: dict[str, list[str]] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True)
        try:
            for width, height in SHORT_VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(INDEX.as_uri() + "#/chat")
                if missing := sorted(set(page.evaluate(NAV_REACH))):
                    failures[f"{width}x{height}"] = missing
                page.close()
        finally:
            browser.close()
    assert failures == {}, json.dumps(failures)
