from __future__ import annotations

import pytest
from test_frontend_control import run_control

SETUP = r"""
await readyControl();
const query = document.querySelector('#memory-query');
const status = document.querySelector('#memory-search-status');
const result = document.querySelector('#memory-items');
const memory = (text, revision = 1) => ({
  memory_id:'synthetic-memory', text, revision, source_event_ids:['synthetic-source']
});
const search = () => document.querySelector('#memory-search-form').onsubmit({preventDefault(){}});
"""


def test_search_uses_existing_authenticated_api_and_preserves_provenance() -> None:
    run_control(
        SETUP
        + r"""
query.value = ' 茶 & <script> ';
fetchPlan = (url, options) => {
  assert.equal(url, '/v1/memories?limit=100&query=' + encodeURIComponent('茶 & <script>'));
  assert(options.headers.get('Authorization').startsWith('Bearer synthetic-'));
  assert(options.signal instanceof AbortSignal);
  return response(200, {items:[memory('<img src=x onerror=bad()>')]});
};
await search();
assert.equal(result.children.length, 1);
assert.equal(result.children[0].children[0].textContent, '<img src=x onerror=bad()>');
assert(result.textContent.includes('synthetic-source'));
assert(result.textContent.includes('第 1 版'));
assert(status.textContent.includes('100'));
assert.equal(sockets.length, 1);
assert(targetCalls().every(call => !call.options.method || call.options.method === 'GET'));
"""
    )


def test_clear_empty_and_zero_results_have_distinct_status() -> None:
    run_control(
        SETUP
        + r"""
fetchPlan = () => response(200, {items:[]});
query.value = 'unmatched'; await search();
assert(status.textContent.includes('沒有符合'));
await document.querySelector('#memory-search-clear').onclick();
assert.equal(query.value, ''); assert(status.textContent.includes('還沒有記憶'));
assert.equal(targetCalls().at(-1).url, '/v1/memories?limit=100');
"""
    )


def test_latest_query_wins_even_if_old_fetch_ignores_abort() -> None:
    run_control(
        SETUP
        + r"""
let oldResolve, oldSignal;
fetchPlan = (url, options) => {
  if (url.includes('old')) {
    oldSignal = options.signal; return new Promise(resolve => {oldResolve = resolve;});
  }
  return response(200, {items:[memory('new result')]});
};
query.value = 'old'; const old = search(); await until(() => oldResolve);
query.value = 'new'; await search(); assert(oldSignal.aborted);
oldResolve(response(200, {items:[memory('old result')]})); await old;
assert(result.textContent.includes('new result'));
assert(!result.textContent.includes('old result'));
assert.equal(memorySearchController, undefined); assert.equal(memorySearchTimeout, undefined);
"""
    )


@pytest.mark.parametrize("boundary", ["timeout", "disconnect", "close"])
def test_cancel_boundary_removes_cards_and_rejects_late_results(boundary: str) -> None:
    action = {
        "timeout": "fireTimer(timer => timer.delay === 5000);",
        "disconnect": "socket.disconnect();",
        "close": "dispatchWindow('beforeunload');",
    }[boundary]
    run_control(
        SETUP
        + r"""
let resolve, signal;
fetchPlan = (url, options) => {signal=options.signal; return new Promise(done => {resolve=done;});};
query.value = 'pending'; const pending = search(); await until(() => resolve);
"""
        + action
        + r"""
assert(signal.aborted); assert.equal(result.children.length, 0);
resolve(response(200, {items:[memory('late result')]})); await pending;
assert(!result.textContent.includes('late result'));
assert.equal(memorySearchController, undefined);
"""
    )


@pytest.mark.parametrize("failure", ["http", "malformed", "network"])
def test_failure_clears_stale_cards_and_recovery_works(failure: str) -> None:
    response_js = {
        "http": "response(503, {detail:'private error must not be shown'})",
        "malformed": "response(200, {items:null})",
        "network": "Promise.reject(new Error('private transport failure'))",
    }[failure]
    run_control(
        SETUP
        + "fetchPlan = () => response(200, {items:[memory('previous')]}); await search();"
        + f"fetchPlan = () => {response_js}; await search();"
        + r"""
assert.equal(result.children.length, 0); assert(status.textContent.includes('無法查詢'));
assert(!status.textContent.includes('private'));
fetchPlan = () => response(200, {items:[memory('recovered')]}); await search();
assert(result.textContent.includes('recovered'));
"""
    )


def test_correction_and_delete_requery_current_search() -> None:
    run_control(
        SETUP
        + r"""
query.value='orchid';
fetchPlan = url => {
  if (url === '/v1/runtime') return response(200, {tools:[], features:{}});
  if (url === '/v1/memory-organization') return response(200, {state:'disabled', groups:[]});
  return response(200, {items:[memory('orchid', 2)]});
};
await search();
window.prompt = () => 'corrected orchid';
await result.children[0].children[2].onclick();
assert(targetCalls().some(call => call.url.endsWith('/correct') && call.options.method === 'POST'));
assert.equal(targetCalls().at(-1).url, '/v1/memories?limit=100&query=orchid');
assert(result.textContent.includes('第 2 版'));
window.confirm = () => true;
await result.children[0].children[3].onclick();
assert(targetCalls().some(call => call.options.method === 'DELETE'));
assert.equal(targetCalls().at(-1).url, '/v1/memories?limit=100&query=orchid');
"""
    )


def test_oversized_search_is_local_validation_not_request() -> None:
    run_control(
        SETUP
        + r"""
query.value = 'a'.repeat(4097); await search();
assert.equal(targetCalls().length, 0); assert(status.textContent.includes('太長'));
"""
    )
