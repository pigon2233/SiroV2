from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def run_control(checks: str) -> None:
    """Run the real page with synthetic socket events and a manually advanced clock."""
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    script = html.split("<script>", 1)[1].split("</script>", 1)[0]
    script = script[: script.rindex("      boot().catch(")]
    ids = json.dumps(re.findall(r'\bid="([^"]+)"', html))
    setup = r"""
const assert = require('node:assert/strict');
const roots = [], listeners = new Map(), timers = new Map(), sockets = [], calls = [];
let clock = 0, nextTimer = 0, nextToken = 0, fetchPlan, bootstrapPlan;
const performance = {now: () => clock};
const location = {origin:'http://localhost', host:'localhost', protocol:'http:', reload() {
  throw new Error('Connection recovery must not reload the page');
}};
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this._text = ''; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  appendChild(child) { child.parent = this; this.children.push(child); return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  querySelector(selector) { return find(this.children, selector); }
  addEventListener() {}
  remove() {}
}
function find(elements, selector) {
  for (const element of elements) {
    if ((selector.startsWith('#') && element.id === selector.slice(1)) ||
        (selector.startsWith('.') && element.className === selector.slice(1))) return element;
    const child = find(element.children, selector); if (child) return child;
  }
  return null;
}
const document = {
  querySelector: selector => find(roots, selector), querySelectorAll: () => [],
  getElementById: id => find(roots, '#' + id), createElement: tag => new Element(tag),
};
const window = {
  addEventListener: (name, callback) => {
    if (!listeners.has(name)) listeners.set(name, []);
    listeners.get(name).push(callback);
  }
};
const dispatchWindow = name => { for (const callback of listeners.get(name) || []) callback({}); };
const setTimeout = (callback, delay) => {
  const id = ++nextTimer; timers.set(id, {callback, delay}); return id;
};
const clearTimeout = id => timers.delete(id);
const fireTimer = predicate => {
  const entry = [...timers].find(([id, timer]) => predicate(timer));
  assert(entry, 'Expected owned timer does not exist');
  const [id, timer] = entry; timers.delete(id); clock += timer.delay; timer.callback();
};
const flush = async () => { for (let index = 0; index < 100; index++) await Promise.resolve(); };
const until = async predicate => {
  await flush(); assert(predicate(), 'Expected asynchronous step was not reached');
};
class WebSocket {
  constructor(url) {
    this.url = url; this.readyState = 0; this.sent = []; this.closeCalls = 0; sockets.push(this);
  }
  send(data) { assert.equal(this.readyState, 1); this.sent.push(JSON.parse(data)); }
  open() { this.readyState = 1; this.onopen?.(); }
  message(data) { this.onmessage?.({data: JSON.stringify(data)}); }
  close() { this.closeCalls++; this.readyState = 2; }
  disconnect() { this.readyState = 3; this.onclose?.({code:1006}); }
}
const response = (status, body) => new Response(JSON.stringify(body), {
  status, headers: {'Content-Type':'application/json'}
});
const fetch = async (url, options) => {
  calls.push({url, options});
  if (url === '/v1/session') {
    if (bootstrapPlan) return bootstrapPlan(options);
    return response(200, {token:`synthetic-${++nextToken}`, expires_in_seconds:300});
  }
  return fetchPlan ? fetchPlan(url, options) : response(200, {turn_id:'synthetic-turn'});
};
const snapshot = active_turns => ({
  type:'snapshot', identity:{identity_id:'siro'}, active_turns:active_turns || {},
  kill_switches:{}, authorization_mode:'safe', health:{}, routes:{}
});
"""
    initialize = f"""
for (const id of {ids}) {{ const node = new Element('div'); node.id = id; roots.push(node); }}
document.querySelector('#voice-output').checked = false;
"""
    helpers = r"""
const readyControl = async (state = {}) => {
  const count = sockets.length, connecting = connectControl();
  await until(() => sockets.length === count + 1);
  const owner = sockets.at(-1); owner.open(); owner.message(snapshot(state));
  await connecting; return owner;
};
const targetCalls = () => calls.filter(call => call.url !== '/v1/session');
let finished = false;
process.on('beforeExit', () => {
  if (!finished) {
    console.error('Synthetic control scenario left its promise unresolved'); process.exitCode = 1;
  }
});
"""
    result = subprocess.run(
        [
            "node",
            "-e",
            setup
            + initialize
            + script
            + helpers
            + "\n(async () => {\n"
            + checks
            + "\n})().then(() => { finished = true; }, error => {"
            + " finished = true; console.error(error); process.exitCode = 1; });",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_concurrent_connect_has_one_owner_and_open_is_not_authenticated() -> None:
    run_control(
        """
const first = connectControl(), second = connectControl();
assert.equal(first, second);
let settled = false; first.then(() => { settled = true; });
await until(() => sockets.length === 1);
const owner = sockets[0]; owner.open(); await flush();
assert.equal(settled, false); assert.equal(controlAuthenticated, false);
assert.deepEqual(owner.sent, [{type:'authenticate', token:'synthetic-1'}]);
assert.equal(targetCalls().length, 0);
owner.message(snapshot()); await first;
assert.equal(controlAuthenticated, true);
await connectControl();
assert.equal(sockets.length, 1);
"""
    )


def test_turn_waits_for_snapshot_before_http_dispatch() -> None:
    run_control(
        """
const submission = submitText('synthetic unsent until ready');
await until(() => sockets.length === 1);
const owner = sockets[0]; owner.open(); await flush();
assert.equal(targetCalls().length, 0);
owner.message(snapshot()); await submission;
assert.equal(targetCalls().length, 1);
assert.equal(targetCalls()[0].url, '/v1/conversations/browser/turns');
"""
    )


def test_stale_callbacks_cannot_change_new_owner_or_replay_text() -> None:
    run_control(
        """
const first = await readyControl(), oldOpen = first.onopen, oldMessage = first.onmessage,
      oldClose = first.onclose;
first.disconnect(); await flush();
const second = await readyControl();
const before = document.querySelector('#messages').textContent;
const timerCount = timers.size;
oldOpen();
oldMessage({data:JSON.stringify({type:'assistant_delta', text:'stale private-free canary'})});
oldClose();
assert.equal(socket, second); assert.equal(controlAuthenticated, true);
assert.equal(first.sent.length, 1); assert.equal(second.sent.length, 1);
assert.equal(document.querySelector('#messages').textContent, before);
assert.equal(timers.size, timerCount);
assert.equal(sockets.length, 2); assert.equal(targetCalls().length, 0);
"""
    )


def test_snapshot_reconciles_missed_terminal_without_replay() -> None:
    run_control(
        """
const spoken = []; playTts = text => spoken.push(text);
const first = await readyControl();
first.message({type:'turn_started', turn_id:'old-turn'});
first.message({type:'assistant_started', stream_id:'old-stream'});
first.message({type:'assistant_delta', stream_id:'old-stream', text:'synthetic partial'});
first.disconnect(); await flush();
await readyControl({browser:{turn_id:'old-turn', state:'completed'}});
assert.equal(currentTurn, undefined); assert.equal(assistantBubble, undefined);
assert(document.querySelector('#messages').textContent.includes('synthetic partial'));
assert(document.querySelector('#messages').textContent.includes('沒有重新執行'));
assert.equal(spoken.length, 0); assert.equal(targetCalls().length, 0);
"""
    )


def test_snapshot_changing_active_turn_does_not_reuse_previous_partial_bubble() -> None:
    run_control(
        """
const first = await readyControl();
first.message({type:'turn_started', turn_id:'old-turn'});
first.message({type:'assistant_started', stream_id:'old-stream'});
first.message({type:'assistant_delta', stream_id:'old-stream', text:'old partial'});
first.disconnect(); await flush();
await readyControl({browser:{turn_id:'different-turn', state:'responding'}});
assert.equal(currentTurn, 'different-turn'); assert.equal(assistantBubble, undefined);
assert.equal(targetCalls().length, 0);
"""
    )


def test_ready_timeout_rejects_and_late_snapshot_cannot_authenticate_closing_socket() -> None:
    run_control(
        """
const connecting = connectControl(), rejected = assert.rejects(connecting);
await until(() => sockets.length === 1);
const owner = sockets[0]; owner.open();
fireTimer(timer => timer.delay === 5000); await rejected;
assert.equal(owner.closeCalls, 1); assert.equal(controlAuthenticated, false);
owner.message(snapshot({browser:{turn_id:'stale-turn', state:'responding'}}));
assert.equal(controlAuthenticated, false, 'Readiness timeout must retire the closing socket');
assert.equal(currentTurn, undefined);
assert.equal(targetCalls().length, 0);
"""
    )


def test_close_before_snapshot_rejects_and_schedules_only_one_reconnect() -> None:
    run_control(
        """
const connecting = connectControl(), rejected = assert.rejects(connecting);
await until(() => sockets.length === 1);
sockets[0].open(); sockets[0].disconnect(); await rejected;
assert.equal(controlAuthenticated, false);
assert.equal(timers.size, 1); assert.equal(reconnectAttempts, 1);
assert.equal([...timers.values()][0].delay, 500);
assert.equal(targetCalls().length, 0);
"""
    )


def test_automatic_reconnect_is_bounded_to_three_attempts() -> None:
    run_control(
        """
const initial = connectControl(), rejected = assert.rejects(initial);
await until(() => sockets.length === 1);
sockets[0].open(); sockets[0].disconnect(); await rejected;
for (let retry = 1; retry <= 3; retry++) {
  fireTimer(timer => timer.delay < 5000);
  await until(() => sockets.length === retry + 1);
  sockets.at(-1).open(); sockets.at(-1).disconnect(); await flush();
}
assert.equal(sockets.length, 4); assert.equal(reconnectAttempts, 3);
assert.equal(timers.size, 0); assert.equal(targetCalls().length, 0);
"""
    )


def test_http_token_renewal_keeps_healthy_control_owner() -> None:
    run_control(
        """
const owner = await readyControl(); clock = 285_000;
await authorizedFetch('/v1/runtime');
assert.equal(calls.filter(call => call.url === '/v1/session').length, 2);
assert.equal(sockets.length, 1); assert.equal(socket, owner);
assert.equal(owner.closeCalls, 0); assert.equal(owner.sent.length, 1);
assert.equal(controlAuthenticated, true);
"""
    )


def test_unload_during_bootstrap_rejects_pending_connection_without_dispatch() -> None:
    run_control(
        """
bootstrapPlan = options => new Promise((resolve, reject) => {
  options.signal.addEventListener('abort', () => reject(options.signal.reason), {once:true});
});
const connecting = connectControl(), rejected = assert.rejects(connecting);
await until(() => calls.length === 1);
dispatchWindow('beforeunload'); await rejected;
assert.equal(pageClosing, true); assert.equal(sockets.length, 0);
assert.equal(timers.size, 0); assert.equal(targetCalls().length, 0);
await assert.rejects(connectControl());
"""
    )


def test_unload_while_waiting_for_snapshot_releases_readiness_owner_and_timer() -> None:
    run_control(
        """
let outcome;
const connecting = connectControl();
connecting.then(() => { outcome = 'resolved'; }, () => { outcome = 'rejected'; });
await until(() => sockets.length === 1);
sockets[0].open(); dispatchWindow('beforeunload'); await flush();
assert.equal(outcome, 'rejected', 'Unload must settle its pending readiness promise');
assert.equal(sockets[0].closeCalls, 1); assert.equal(timers.size, 0);
sockets[0].disconnect(); await flush();
assert.equal(timers.size, 0); assert.equal(targetCalls().length, 0);
await assert.rejects(connectControl());
"""
    )


def test_unknown_turn_outcome_is_never_resent_on_reconnect() -> None:
    run_control(
        """
let effects = 0;
fetchPlan = url => {
  if (url === '/v1/conversations/browser/turns') {
    effects++; throw new TypeError('synthetic disconnect after acceptance');
  }
  return response(404, {detail:'not found'});
};
const owner = await readyControl();
await submitText('synthetic action accepted before disconnect');
assert.equal(effects, 1);
assert(document.querySelector('#messages').textContent.includes('未確認'));
owner.disconnect(); await flush();
fireTimer(timer => timer.delay < 5000);
await until(() => sockets.length === 2);
sockets[1].open(); sockets[1].message(snapshot()); await flush();
assert.equal(effects, 1);
assert.equal(targetCalls().filter(call => call.options.method === 'POST').length, 1);
"""
    )


def test_cancel_during_readiness_wait_does_not_dispatch_queued_turn() -> None:
    run_control(
        """
const submission = submitText('synthetic queued action');
await until(() => sockets.length === 1);
sockets[0].open(); await document.querySelector('#cancel').onclick();
sockets[0].message(snapshot()); await submission;
assert.equal(targetCalls().length, 0, 'Cancelling before readiness must prevent queued dispatch');
"""
    )


def test_cancel_during_token_renewal_does_not_dispatch_queued_turn() -> None:
    run_control(
        """
await readyControl(); clock = 285_000;
let finishRenewal;
bootstrapPlan = () => new Promise(resolve => { finishRenewal = resolve; });
const submission = submitText('synthetic queued during renewal');
await until(() => calls.filter(call => call.url === '/v1/session').length === 2);
await document.querySelector('#cancel').onclick();
finishRenewal(response(200, {token:'synthetic-renewed', expires_in_seconds:300}));
await submission;
assert.equal(targetCalls().length, 0, 'Cancellation during renewal must stop queued dispatch');
"""
    )


def test_cancel_overlapping_submissions_during_renewal_cannot_revive_older_dispatch() -> None:
    run_control(
        """
await readyControl(); clock = 285_000;
let finishRenewal;
bootstrapPlan = () => new Promise(resolve => { finishRenewal = resolve; });
const first = submitText('synthetic superseded request');
await until(() => calls.filter(call => call.url === '/v1/session').length === 2);
const second = submitText('synthetic newer request'); await flush();
await document.querySelector('#cancel').onclick();
finishRenewal(response(200, {token:'synthetic-renewed', expires_in_seconds:300}));
await Promise.all([first, second]);
assert.equal(targetCalls().length, 0, 'Cancellation must not revive a superseded pending request');
"""
    )


def test_form_restores_draft_when_readiness_fails_before_dispatch() -> None:
    run_control(
        """
const input = document.querySelector('#text'); input.value = 'synthetic unsent draft';
const submitting = document.querySelector('#chat').onsubmit({preventDefault(){}});
await until(() => sockets.length === 1);
sockets[0].open(); sockets[0].disconnect(); await submitting;
assert.equal(input.value, 'synthetic unsent draft');
assert.equal(targetCalls().length, 0);
"""
    )


def test_form_preserves_new_input_when_old_draft_fails_preflight() -> None:
    run_control(
        """
const input = document.querySelector('#text'); input.value = 'synthetic old draft';
const submitting = document.querySelector('#chat').onsubmit({preventDefault(){}});
await until(() => sockets.length === 1);
input.value = 'synthetic newer draft';
sockets[0].open(); sockets[0].disconnect(); await submitting;
assert.equal(input.value, 'synthetic newer draft');
assert.equal(targetCalls().length, 0);
"""
    )


def test_form_does_not_restore_draft_after_unknown_accepted_outcome() -> None:
    run_control(
        """
let accepted = 0;
fetchPlan = url => {
  accepted++; throw new TypeError('synthetic lost response after acceptance');
};
await readyControl();
const input = document.querySelector('#text'); input.value = 'synthetic accepted draft';
await document.querySelector('#chat').onsubmit({preventDefault(){}});
assert.equal(input.value, '');
assert.equal(accepted, 1);
assert.equal(targetCalls().length, 1);
assert(document.querySelector('#messages').textContent.includes('未確認'));
"""
    )
