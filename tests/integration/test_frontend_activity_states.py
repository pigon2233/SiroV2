"""CP-P03: the activity page tells stale data from a live connection and shows unknown outcomes."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import Page, sync_playwright
from test_frontend_reflow import INDEX

SEED = """
([state, status]) => {
  const item = (id, itemState) => ({activity_id: id, kind: 'agent_run', origin: 'owner_request',
    state: itemState, reason: '查資料' + id, reason_truncated: false, error: null,
    created_at: '2026-10-18T10:00:00+08:00', updated_at: '2026-10-18T10:0' + id + ':00+08:00',
    tools: [], coverage: {tools: 'journal', network: []}});
  activityView.items = new Map([['1', item('1', 'running')], ['2', item('2', state)]]);
  activityView.fetchedAt = '2026-10-18T10:05:00+08:00'; activityView.status = status;
  renderActivity();
  const text = selector => document.querySelector(selector).textContent;
  return {
    feed: text('#activity-feed'), banner: text('#activity-banner'),
    stops: [...document.querySelectorAll('#activity-body .act-stop')].map(b => ({
      disabled: b.disabled, label: b.textContent.trim(), id: b.dataset.activityStop || null})),
    body: text('#activity-body'),
  };
}
"""


@contextmanager
def activity_page() -> Iterator[Page]:
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    assert executable, "activity check needs a local Chrome/Chromium"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page(viewport={"width": 1100, "height": 800})
            page.goto(INDEX.as_uri() + "#/activity")
            yield page
        finally:
            browser.close()


def test_offline_disables_stop_and_says_the_data_is_old() -> None:
    with activity_page() as page:
        offline = page.evaluate(SEED, ["completed", "offline"])
    assert offline["stops"] != [] and all(stop["disabled"] for stop in offline["stops"])
    assert all("連線後可用" in stop["label"] and stop["id"] is None for stop in offline["stops"])
    assert "斷線" in offline["feed"] and "的資料" in offline["feed"]
    assert "狀態可能已經變了" in offline["banner"] and "停止按鈕先停用" in offline["banner"]


def test_live_connection_is_distinct_from_cached_data() -> None:
    with activity_page() as page:
        live = page.evaluate(SEED, ["completed", "ok"])
        cached = page.evaluate(SEED, ["completed", "offline"])
    assert "即時更新中" in live["feed"] and "最後更新" in live["feed"] and live["banner"] == ""
    assert "即時更新中" not in cached["feed"] and "斷線" in cached["feed"]
    assert cached["banner"] != live["banner"]
    # Same timestamp either way: only the wording tells whether it is still being updated.
    assert any(not stop["disabled"] and stop["id"] == "1" for stop in live["stops"])
    assert not any(not stop["disabled"] for stop in cached["stops"])


def test_unknown_outcome_is_labelled_and_explained_not_shown_as_done() -> None:
    with activity_page() as page:
        shown = page.evaluate(SEED, ["unknown", "ok"])
        badge = page.evaluate(
            "() => document.querySelector('#activity-body [data-state=\"unknown\"]').textContent"
        )
    assert "結果未確認" in shown["body"] and "請自己確認一次" in shown["body"]
    assert "不知道它有沒有做完" in shown["body"]
    assert "完成" not in badge.replace("做完", "")
