from __future__ import annotations

import pytest
from test_frontend_control import run_control

SWITCHES = r"""
await readyControl();
let reloads = 0; location.reload = () => { reloads++; };
renderSnapshot({kill_switches:{cloud:false, tools:true, microphone:false},
  authorization_mode:'safe', identity:{}, health:{}, routes:{}});
const buttons = document.querySelector('#switches').children;
const status = document.querySelector('#switch-status');
const puts = () => targetCalls().filter(call => call.options?.method === 'PUT');
"""


def test_switch_shows_pending_then_reloads_only_after_confirmed_success() -> None:
    run_control(
        SWITCHES
        + r"""
let resolvePut;
fetchPlan = () => new Promise(resolve => { resolvePut = resolve; });
const pending = buttons[1].onclick(); await until(() => resolvePut);
assert(status.textContent.includes('正在關閉電腦與工具操作'));
assert([...buttons].every(button => button.disabled)); assert.equal(reloads, 0);
resolvePut(response(200, {})); await pending;
assert.equal(reloads, 1); assert.equal(puts().length, 1);
assert.equal(puts()[0].url, '/v1/kill-switches/tools');
assert.equal(puts()[0].options.body, JSON.stringify({enabled:false}));
"""
    )


@pytest.mark.parametrize("failure", ["status", "network"])
def test_switch_failure_is_visible_not_resent_and_not_reloaded(failure: str) -> None:
    plan = {
        "status": "fetchPlan = () => response(503, {detail:'unavailable'});",
        "network": "fetchPlan = () => Promise.reject(new TypeError('offline'));",
    }[failure]
    run_control(
        SWITCHES
        + plan
        + r"""
await buttons[1].onclick();
assert.equal(reloads, 0); assert.equal(puts().length, 1);
assert(status.textContent.includes('可能尚未關閉'));
assert(status.textContent.includes('沒有自動重送'));
assert([...buttons].every(button => !button.disabled));
"""
    )


MEMORY = r"""
await readyControl();
const status = document.querySelector('#memory-search-status');
const organization = document.querySelector('#organization-status');
const item = {memory_id:'synthetic-memory', text:'synthetic tea', revision:1,
  source_event_ids:['synthetic-source']};
fetchPlan = () => response(200, {items:[item]});
await refreshMemories();
const card = document.querySelector('#memory-items').children[0];
const [, , correct, remove] = card.children;
const mutations = () => targetCalls()
  .filter(call => ['POST', 'DELETE'].includes(call.options?.method));
"""


@pytest.mark.parametrize("action", ["correct", "remove"])
def test_memory_change_failure_is_shown_on_memory_page_without_resend(action: str) -> None:
    run_control(
        MEMORY
        + f"const action = {action!r};"
        + r"""
window.prompt = () => 'synthetic corrected tea'; window.confirm = () => true;
let rejectChange;
fetchPlan = () => new Promise((_, reject) => { rejectChange = reject; });
const pending = (action === 'correct' ? correct : remove).onclick();
await until(() => rejectChange);
assert(correct.disabled && remove.disabled);
assert(status.textContent.includes(action === 'correct' ? '正在更正' : '正在刪除'));
rejectChange(new Error('synthetic failure')); await pending;
assert(status.textContent.includes(action === 'correct' ? '更正未確認' : '刪除未確認'));
assert(status.textContent.includes('沒有自動重送'));
assert(!organization.textContent.includes('synthetic failure'));
assert(!correct.disabled && !remove.disabled); assert.equal(mutations().length, 1);
"""
    )


def test_cancelled_dialogs_send_nothing() -> None:
    run_control(
        MEMORY
        + r"""
window.prompt = () => null; window.confirm = () => false;
await correct.onclick(); await remove.onclick();
assert.equal(mutations().length, 0); assert(!correct.disabled && !remove.disabled);
"""
    )


@pytest.mark.parametrize(
    ("reason", "renewed"),
    [("invalid session token", True), ("authentication timeout", False)],
)
def test_reconnect_after_server_restart_renews_only_rejected_token(
    reason: str, renewed: bool
) -> None:
    run_control(
        f"const reason = {reason!r}, renewed = {str(renewed).lower()};"
        + r"""
const first = connectControl(); first.catch(() => {});
await until(() => sockets.length === 1);
sockets[0].open();
assert.deepEqual(sockets[0].sent, [{type:'authenticate', token:'synthetic-1'}]);
sockets[0].readyState = 3; sockets[0].onclose({code:1008, reason});
assert.equal(controlAuthenticated, false);
await flush(); fireTimer(timer => timer.delay === 500);
await until(() => sockets.length === 2);
sockets[1].open();
assert.equal(sockets[1].sent[0].token, renewed ? 'synthetic-2' : 'synthetic-1');
assert.equal(calls.filter(call => call.url === '/v1/session').length, renewed ? 2 : 1);
sockets[1].message(snapshot()); await flush();
assert.equal(controlAuthenticated, true);
assert.equal(targetCalls().length, 0);
"""
    )
