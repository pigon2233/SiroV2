from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def run_session_access(checks: str) -> None:
    """Exercise the page's actual factory without a browser, server, or private data."""
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    start = html.index("function createSessionAccess(")
    end = html.index("const sessionAccess = createSessionAccess();", start)
    factory = html[start:end]
    setup = r"""
const assert = require('node:assert/strict');
const origin = 'http://localhost';
const invalid = {detail: 'session token is invalid or expired'};
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return {promise, resolve, reject};
};
const reply = (status, data, path = '/v1/runtime') => {
  const response = new Response(JSON.stringify(data), {
    status, headers: {'Content-Type': 'application/json'}
  });
  Object.defineProperty(response, 'url', {value: origin + path});
  return response;
};
const issued = (token, ttl = 100) => reply(200, {
  token, expires_in_seconds: ttl
}, '/v1/session');
const authorization = options => new Headers(options.headers).get('Authorization');
const until = async predicate => {
  for (let attempt = 0; attempt < 100 && !predicate(); attempt++) await Promise.resolve();
  assert(predicate(), 'Expected asynchronous step was not reached');
};
"""
    result = subprocess.run(
        [
            "node",
            "-e",
            setup
            + factory
            + "\n(async () => {\n"
            + checks
            + "\n})().catch(error => { console.error(error); process.exitCode = 1; });",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(("ttl", "refresh_at"), [(100, 90_000), (300, 285_000)])
def test_token_refreshes_on_demand_with_bounded_expiry_margin(ttl: int, refresh_at: int) -> None:
    run_session_access(
        f"""
let clock = 0, bootstraps = 0;
const access = createSessionAccess({{origin, now: () => clock, fetcher: async () =>
  issued(`token-${{++bootstraps}}`, {ttl})
}});
assert.equal(await access.getToken(), 'token-1');
clock = {refresh_at} - 1;
assert.equal(await access.getToken(), 'token-1');
assert.equal(bootstraps, 1);
clock = {refresh_at};
assert.equal(bootstraps, 1, 'Time passing alone must not bootstrap');
assert.equal(await access.getToken(), 'token-2');
assert.equal(bootstraps, 2);
clock = 10_000_000;
assert.equal(await access.getToken(), 'token-3');
assert.equal(bootstraps, 3, 'Waking after a long suspension needs one fresh token');
"""
    )


def test_concurrent_expiry_uses_one_shared_bootstrap() -> None:
    run_session_access(
        """
let clock = 0, bootstraps = 0;
const renewal = deferred(), calls = [];
const access = createSessionAccess({origin, now: () => clock, fetcher: async (url, options) => {
  if (url === '/v1/session') {
    bootstraps++;
    return bootstraps === 1 ? issued('first') : renewal.promise;
  }
  calls.push({url, options}); return reply(200, {ok: true}, url);
}});
await access.getToken(); clock = 90_000;
const requests = Array.from({length: 8}, (_, index) => access.request(`/v1/read-${index}`));
await until(() => bootstraps === 2);
assert.equal(calls.length, 0);
renewal.resolve(issued('renewed'));
assert((await Promise.all(requests)).every(response => response.ok));
assert.equal(bootstraps, 2);
assert.equal(calls.length, 8);
assert(calls.every(call => authorization(call.options) === 'Bearer renewed'));
"""
    )


def test_delayed_old_401_does_not_invalidate_a_new_token() -> None:
    run_session_access(
        """
let bootstraps = 0;
const first = deferred(), delayed = deferred(), calls = [];
const access = createSessionAccess({origin, now: () => 0, fetcher: async (url, options) => {
  if (url === '/v1/session') return issued(`token-${++bootstraps}`);
  const bearer = authorization(options); calls.push({url, bearer});
  if (bearer === 'Bearer token-1') return url === '/v1/first' ? first.promise : delayed.promise;
  return reply(200, {ok: true}, url);
}});
await access.getToken();
const quick = access.request('/v1/first'), slow = access.request('/v1/delayed');
await until(() => calls.length === 2);
first.resolve(reply(401, invalid, '/v1/first'));
assert.equal((await quick).status, 200);
assert.equal(bootstraps, 2);
delayed.resolve(reply(401, invalid, '/v1/delayed'));
assert.equal((await slow).status, 200);
assert.equal(bootstraps, 2, 'A stale rejection must not mint a third token');
assert.deepEqual(calls.map(call => call.bearer), [
  'Bearer token-1', 'Bearer token-1', 'Bearer token-2', 'Bearer token-2'
]);
"""
    )


def test_auth_retry_is_once_and_keeps_post_body() -> None:
    run_session_access(
        """
let bootstraps = 0;
const calls = [], body = JSON.stringify({approved: true});
const access = createSessionAccess({origin, now: () => 0, fetcher: async (url, options) => {
  if (url === '/v1/session') return issued(`token-${++bootstraps}`);
  calls.push(options); return reply(401, invalid, url);
}});
const response = await access.request('/v1/tool-proposals/synthetic/approve', {
  method: 'POST', body
});
assert.equal(response.status, 401);
assert.deepEqual(await response.json(), invalid, 'The returned response must remain readable');
assert.equal(bootstraps, 2);
assert.equal(calls.length, 2);
assert(calls.every(call => call.method === 'POST' && call.body === body));
assert.deepEqual(calls.map(authorization), ['Bearer token-1', 'Bearer token-2']);
"""
    )


def test_page_disposal_after_token_lookup_prevents_dispatch() -> None:
    run_session_access(
        """
let sends = 0;
const access = createSessionAccess({origin, fetcher: async url => {
  if (url === '/v1/session') return issued('valid');
  sends++; return reply(200, {});
}});
await access.getToken();
const request = access.request('/v1/tool-proposals/synthetic/approve', {method: 'POST'});
access.dispose();
await assert.rejects(request, /頁面已關閉/);
assert.equal(sends, 0);
"""
    )


@pytest.mark.parametrize(
    ("status", "detail"),
    [
        (401, "session token is required"),
        (401, "session token is invalid or expired "),
        (401, "provider authorization failed"),
        (403, "session token is invalid or expired"),
        (500, "session token is invalid or expired"),
        (502, "tool execution failed"),
    ],
)
def test_other_http_failures_never_replay_an_accepted_effect(status: int, detail: str) -> None:
    run_session_access(
        f"""
let bootstraps = 0, effects = 0;
const access = createSessionAccess({{origin, now: () => 0, fetcher: async (url) => {{
  if (url === '/v1/session') {{ bootstraps++; return issued('valid'); }}
  effects++; return reply({status}, {{detail: {json.dumps(detail)}}}, url);
}}}});
const response = await access.request('/v1/tool-proposals/synthetic/approve', {{
  method: 'POST', body: '{{"approved":true}}'
}});
assert.equal(response.status, {status});
assert.equal(effects, 1);
assert.equal(bootstraps, 1);
assert.deepEqual(await response.json(), {{detail: {json.dumps(detail)}}});
"""
    )


def test_transport_failure_after_acceptance_never_replays() -> None:
    run_session_access(
        """
let effects = 0, bootstraps = 0;
const disconnected = new TypeError('synthetic connection lost after acceptance');
const access = createSessionAccess({origin, now: () => 0, fetcher: async url => {
  if (url === '/v1/session') { bootstraps++; return issued('valid'); }
  effects++; throw disconnected;
}});
await assert.rejects(access.request('/v1/conversations/browser/turns', {
  method: 'POST', body: '{"text":"synthetic"}'
}), error => error === disconnected);
assert.equal(effects, 1); assert.equal(bootstraps, 1);
"""
    )


@pytest.mark.parametrize("refresh_reason", ["expiry", "401"])
def test_abort_while_awaiting_refresh_prevents_dispatch_without_cancelling_shared_refresh(
    refresh_reason: str,
) -> None:
    run_session_access(
        f"""
let clock = 0, bootstraps = 0, speechCalls = 0, bootstrapSignal;
const renewal = deferred(), controller = new AbortController();
const access = createSessionAccess({{origin, now: () => clock, fetcher: async (url, options) => {{
  if (url === '/v1/session') {{
    bootstraps++;
    if (bootstraps === 1) return issued('first');
    bootstrapSignal = options.signal; return renewal.promise;
  }}
  if (url === '/v1/audio/speech') {{ speechCalls++; return reply(401, invalid, url); }}
  return reply(200, {{ok: true}}, url);
}}}});
await access.getToken();
clock = {"90_000" if refresh_reason == "expiry" else "0"};
const speaking = access.request('/v1/audio/speech', {{
  method: 'POST', body: '{{"text":"synthetic"}}', signal: controller.signal
}});
const rejected = assert.rejects(speaking, {{name: 'AbortError'}});
await until(() => bootstraps === 2);
const other = access.request('/v1/runtime');
controller.abort();
assert.notEqual(bootstrapSignal?.aborted, true);
renewal.resolve(issued('renewed'));
await rejected;
assert.equal((await other).status, 200);
assert.equal(speechCalls, {0 if refresh_reason == "expiry" else 1});
assert.equal(bootstraps, 2);
"""
    )


def test_audio_headers_body_and_signal_survive_authorization() -> None:
    run_session_access(
        """
const controller = new AbortController(), body = new Blob(['synthetic wav']);
const originalHeaders = new Headers({
  'Content-Type': 'audio/wav', 'X-Synthetic': 'preserved', 'Authorization': 'Bearer stale'
});
let observed;
const access = createSessionAccess({origin, now: () => 0, fetcher: async (url, options) => {
  if (url === '/v1/session') return issued('current');
  observed = options; return reply(200, {text: 'synthetic'}, url);
}});
const response = await access.request('/v1/audio/transcriptions?language=zh', {
  method: 'POST', headers: originalHeaders, body, signal: controller.signal, redirect: 'follow'
});
assert.equal(response.status, 200);
assert.equal(new Headers(observed.headers).get('Content-Type'), 'audio/wav');
assert.equal(new Headers(observed.headers).get('X-Synthetic'), 'preserved');
assert.equal(authorization(observed), 'Bearer current');
assert.equal(originalHeaders.get('Authorization'), 'Bearer stale');
assert.equal(observed.body, body);
assert.equal(observed.signal, controller.signal);
assert.equal(observed.redirect, 'error');
"""
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.invalid/v1/runtime",
        "//evil.invalid/v1/runtime",
        "http://localhost/v1/runtime",
        "/body",
        "/v10/runtime",
        "/v1",
        "/v1/../body",
    ],
)
def test_unsafe_url_is_rejected_before_any_credential_or_request(url: str) -> None:
    run_session_access(
        f"""
let calls = 0;
const access = createSessionAccess({{origin, now: () => 0, fetcher: async () => {{
  calls++; return issued('must-not-be-issued');
}}}});
await assert.rejects(access.request({json.dumps(url)}));
assert.equal(calls, 0);
"""
    )


@pytest.mark.parametrize("failure", ["http", "transport"])
def test_bootstrap_failure_has_single_flight_and_three_second_cooldown(failure: str) -> None:
    fail_bootstrap = (
        'failed.resolve(reply(403, {detail: "origin is not allowed"}, "/v1/session"));'
        if failure == "http"
        else 'failed.reject(new TypeError("synthetic bootstrap unavailable"));'
    )
    run_session_access(
        f"""
let clock = 0, bootstraps = 0;
const failed = deferred();
const access = createSessionAccess({{origin, now: () => clock, fetcher: async () => {{
  bootstraps++;
  return bootstraps === 1 ? failed.promise : issued('recovered');
}}}});
const first = access.getToken(), second = access.getToken();
const results = Promise.allSettled([first, second]);
await until(() => bootstraps === 1);
{fail_bootstrap}
assert((await results).every(result => result.status === 'rejected'));
assert.equal(bootstraps, 1);
await assert.rejects(access.getToken());
clock = 2999; await assert.rejects(access.getToken());
assert.equal(bootstraps, 1, 'Failed bootstrap must not spin on foreground requests');
clock = 3001;
assert.equal(await access.getToken(), 'recovered');
assert.equal(bootstraps, 2);
"""
    )


def test_bootstrap_timeout_is_bounded_and_can_recover_after_cooldown() -> None:
    run_session_access(
        """
let clock = 0, bootstraps = 0, nextTimer = 0, aborted = false;
const timers = new Map();
globalThis.setTimeout = (callback, delay) => {
  const id = ++nextTimer; timers.set(id, {callback, delay}); return id;
};
globalThis.clearTimeout = id => timers.delete(id);
const access = createSessionAccess({origin, now: () => clock, fetcher: async (url, options) => {
  bootstraps++;
  if (bootstraps > 1) return issued('recovered');
  return new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => {
      aborted = true; reject(options.signal.reason);
    }, {once: true});
  });
}});
const waiting = access.getToken(), rejected = assert.rejects(waiting);
await until(() => [...timers.values()].some(timer => timer.delay === 5000));
clock = 5000;
const timeout = [...timers.values()].find(timer => timer.delay === 5000);
timeout.callback();
await rejected;
assert(aborted);
await assert.rejects(access.getToken());
assert.equal(bootstraps, 1);
clock = 8001;
assert.equal(await access.getToken(), 'recovered');
assert.equal(bootstraps, 2);
assert.equal(timers.size, 0, 'Successful recovery must release its timeout');
"""
    )
