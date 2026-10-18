from __future__ import annotations

from test_frontend_navigation import run_navigation


def test_skip_focuses_each_current_page_without_requests_history_or_draft_loss() -> None:
    run_navigation(
        r"""
initializePageNavigation();
const skip = document.querySelector('#skip-to-content');
assert.equal(skip.tagName,'a');
assert.equal(skip.getAttribute('href'),'#main-content');
const draft=document.querySelector('#text'); draft.value='synthetic unsent draft';
for(const page of Object.keys(pageTitles)) {
 navigateToPage(page);
 const hash=location.hash, writes=historyWrites.length, requests=calls.length;
 let prevented=false; skip.onclick({preventDefault(){prevented=true;}});
 assert(prevented); assertPage(page);
 assert.equal(document.activeElement.id, page+'-heading');
 assert.equal(location.hash,hash); assert.equal(historyWrites.length,writes);
 assert.equal(calls.length,requests); assert.equal(sockets.length,0);
 assert.equal(draft.value,'synthetic unsent draft'); assert.equal(timers.size,0);
}
"""
    )


def test_skip_keeps_detail_uuid_and_existing_snapshot_without_redrawing() -> None:
    run_navigation(
        r"""
initializePageNavigation();
const card=document.createElement('p');card.textContent='synthetic saved snapshot';
document.querySelector('#goal-task-items').appendChild(card);
const hash=location.hash;
document.querySelector('#skip-to-content').onclick({preventDefault(){}});
assert.equal(document.activeElement.id,'tasks-heading'); assert.equal(location.hash,hash);
assert.equal(document.querySelector('#goal-task-items').children[0],card);
assert.equal(calls.length,0);assert.equal(historyWrites.length,0);
""",
        initial_hash="#/tasks/00000000-0000-0000-0000-000000000057",
    )


def test_missing_heading_falls_back_to_existing_main_landmark() -> None:
    run_navigation(
        r"""
initializePageNavigation();
const pane=document.querySelector('[data-page="chat"]');
pane.querySelector=()=>null;
document.querySelector('#skip-to-content').onclick({preventDefault(){}});
assert.equal(document.activeElement.id,'main-content');
assert.equal(document.querySelector('#main-content').getAttribute('tabindex'),'-1');
assert.equal(calls.length,0); assert.equal(location.hash,'#/chat');
"""
    )
