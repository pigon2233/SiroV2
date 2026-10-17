from __future__ import annotations

import pytest
from test_frontend_control import run_control


def test_stop_dispatched_post_cancels_late_turn_once_and_rejects_late_output() -> None:
    run_control(
        """
const owner = await readyControl(), spoken = [], ordering = [];
playTts = text => spoken.push(text);
document.querySelector('#voice').dispatchEvent = event => ordering.push(event.type);
let finishPost;
fetchPlan = (url, options) => {
  assert(!Object.hasOwn(options, 'onDispatch'), 'Client hook must not enter fetch options');
  if (url.endsWith('/turns')) return new Promise(resolve => { finishPost = resolve; });
  if (url.endsWith('/cancel')) {
   ordering.push('cancel'); return response(200, {state:'cancelling'});
  }
  assert.equal(url, '/v1/snapshot');
  return response(200, snapshot({browser:{turn_id:'late-turn', state:'completed'}}));
};
const submission = submitText('synthetic pending accepted request');
await until(() => Boolean(finishPost));
const post = targetCalls()[0];
await document.querySelector('#cancel').onclick();
assert.equal(post.options.signal.aborted, false, 'Keep dispatched result metadata until deadline');
owner.message({type:'turn_started', turn_id:'late-turn'});
owner.message({type:'turn_started', turn_id:'late-turn'});
owner.message({type:'assistant_started', stream_id:'late-stream'});
const before = document.querySelector('#messages').textContent;
owner.message({type:'assistant_delta', stream_id:'late-stream', text:'MUST_NOT_DISPLAY'});
owner.message({type:'assistant_terminal', stream_id:'late-stream', state:'completed'});
await flush();
assert.equal(document.querySelector('#messages').textContent, before);
assert.equal(spoken.length, 0); assert.equal(speechCancelled, true);
assert.equal(targetCalls().filter(call => call.url.endsWith('/cancel')).length, 1);
assert.deepEqual(ordering, ['siro:microphone-stop', 'cancel']);
assert.equal(await submitText('must wait for accepted request result'), false);
finishPost(response(200, {turn_id:'late-turn'})); await submission; await flush();
assert.match(document.querySelector('#service-notice').textContent, /已停止/);
fetchPlan = () => response(200, {turn_id:'new-turn'});
assert.equal(await submitText('explicit new message'), true);
owner.message({type:'turn_started', turn_id:'new-turn'});
owner.message({type:'assistant_started', stream_id:'new-stream'});
owner.message({type:'assistant_delta', stream_id:'new-stream', text:'new answer'});
owner.message({type:'assistant_terminal', stream_id:'new-stream', state:'completed'});
assert.deepEqual(spoken, ['new answer']);
"""
    )


@pytest.mark.parametrize("http_first", [False, True])
def test_stopped_response_and_control_event_orders_do_not_resurrect(http_first: bool) -> None:
    run_control(
        f"const httpFirst = {str(http_first).lower()};\n"
        + """
const owner = await readyControl();
let finishPost;
fetchPlan = url => url.endsWith('/turns')
  ? new Promise(resolve => { finishPost = resolve; })
  : response(200, url === '/v1/snapshot'
    ? snapshot({browser:{turn_id:'stopped-turn',state:'completed'}}) : {state:'cancelling'});
const submission = submitText('synthetic'); await until(() => Boolean(finishPost));
await document.querySelector('#cancel').onclick();
if (httpFirst) {
 finishPost(response(200,{turn_id:'stopped-turn'})); await submission; await flush();
}
owner.message({type:'turn_started',turn_id:'stopped-turn'});
owner.message({type:'assistant_started',stream_id:'stopped-stream'});
owner.message({type:'assistant_delta',stream_id:'stopped-stream',text:'hidden old text'});
owner.message({type:'assistant_terminal',stream_id:'stopped-stream',state:'completed'});
if (!httpFirst) {
  assert.equal(await submitText('too soon'), false);
  finishPost(response(200,{turn_id:'stopped-turn'})); await submission; await flush();
}
assert(!document.querySelector('#messages').textContent.includes('hidden old text'));
assert.equal(currentTurn, undefined); assert.equal(assistantBubble, undefined);
assert.equal(targetCalls().filter(call => call.url.endsWith('/cancel')).length, 1);
fetchPlan = () => response(200,{turn_id:'fresh-turn'});
assert.equal(await submitText('explicit fresh intent'), true);
owner.message({type:'turn_started',turn_id:'fresh-turn'});
owner.message({type:'assistant_started',stream_id:'fresh-stream'});
owner.message({type:'assistant_delta',stream_id:'fresh-stream',text:'fresh text'});
owner.message({type:'assistant_terminal',stream_id:'stopped-stream',state:'cancelled'});
assert.equal(currentTurn,'fresh-turn'); assert.equal(assistantBubble.textContent,'fresh text');
"""
    )


def test_stop_before_token_dispatch_aborts_unsent_and_allows_new_explicit_submit() -> None:
    run_control(
        """
await readyControl(); clock = 285_000;
let finishRenewal;
bootstrapPlan = () => new Promise(resolve => { finishRenewal = resolve; });
const submission = submitText('never dispatched');
await until(() => Boolean(finishRenewal)); await document.querySelector('#cancel').onclick();
finishRenewal(response(200,{token:'renewed',expires_in_seconds:300})); await submission;
assert.equal(targetCalls().length,0);
bootstrapPlan = undefined;
assert.equal(await submitText('explicit new intent'),true);
assert.equal(targetCalls().length,1);
assert(!Object.hasOwn(targetCalls()[0].options,'onDispatch'));
"""
    )


def test_verified_401_renewal_cannot_dispatch_stopped_post_again() -> None:
    run_control(
        """
await readyControl(); let finishPost, finishRenewal;
fetchPlan = () => new Promise(resolve => { finishPost = resolve; });
const submission = submitText('synthetic rejected-before-accept request');
await until(() => Boolean(finishPost));
bootstrapPlan = () => new Promise(resolve => { finishRenewal = resolve; });
finishPost(response(401,{detail:'session token is invalid or expired'}));
await until(() => Boolean(finishRenewal));
await document.querySelector('#cancel').onclick();
finishRenewal(response(200,{token:'renewed',expires_in_seconds:300})); await submission;
assert.equal(targetCalls().filter(call => call.url.endsWith('/turns')).length,1);
fetchPlan = () => response(200,{turn_id:'new-turn'}); bootstrapPlan = undefined;
assert.equal(await submitText('explicit next request'),true);
assert.equal(targetCalls().filter(call => call.url.endsWith('/turns')).length,2);
"""
    )


def test_cancelling_ack_and_active_snapshot_do_not_claim_stopped() -> None:
    run_control(
        """
const owner = await readyControl(); let active = true;
fetchPlan = url => response(200,url === '/v1/snapshot'
  ? snapshot({browser:{turn_id:'active-turn',state:active?'responding':'completed'}})
  : {state:'cancelling'});
owner.message({type:'turn_started',turn_id:'active-turn'});
owner.message({type:'assistant_started',stream_id:'active-stream'});
await document.querySelector('#cancel').onclick(); await flush();
assert.equal(await submitText('too early'),false);
assert.match(document.querySelector('#service-notice').textContent,/正在停止/);
assert(!/已停止這次回覆/.test(document.querySelector('#service-notice').textContent));
active = false;
owner.message({type:'assistant_terminal',stream_id:'active-stream',state:'cancelled'});
await flush();
assert.match(document.querySelector('#service-notice').textContent,/已停止/);
fetchPlan = () => response(200,{turn_id:'new'});
assert.equal(await submitText('explicit after confirmed stop'),true);
"""
    )


@pytest.mark.parametrize("failure", ["status", "network"])
def test_cancel_failure_is_visible_and_does_not_resend(failure: str) -> None:
    run_control(
        f"const failure = '{failure}';\n"
        + """
const owner = await readyControl();
fetchPlan = () => failure === 'status' ? response(503,{detail:'synthetic failure'})
  : Promise.reject(new TypeError('PRIVATE_FREE_TEST_CANARY'));
owner.message({type:'turn_started',turn_id:'failed-stop'});
owner.message({type:'assistant_started',stream_id:'failed-stream'});
await document.querySelector('#cancel').onclick(); await flush();
await document.querySelector('#cancel').onclick(); await flush();
assert.match(document.querySelector('#service-notice').textContent,/停止尚未確認|停止未確認/);
assert(!document.querySelector('#service-notice').textContent.includes('PRIVATE_FREE_TEST_CANARY'));
assert.equal(await submitText('must stay blocked'),false);
assert.equal(targetCalls().filter(call => call.url.endsWith('/cancel')).length,1);
"""
    )


def test_stop_deadline_aborts_owned_waits_and_late_events_stay_fenced() -> None:
    run_control(
        """
const owner = await readyControl(); const pending = [];
fetchPlan = (url, options) => new Promise((resolve,reject) => {
  pending.push({url,options,resolve});
  options.signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')));
});
const submission = submitText('synthetic indefinitely pending accepted request');
await until(() => pending.length === 1);
await document.querySelector('#cancel').onclick();
assert.equal(await submitText('blocked while stopping'),false);
fireTimer(timer => timer.delay === 5000); await flush(); await submission;
assert(pending[0].options.signal.aborted);
assert.match(document.querySelector('#service-notice').textContent,/停止尚未確認|停止未確認/);
owner.message({type:'turn_started',turn_id:'arrived-after-deadline'});
owner.message({type:'assistant_started',stream_id:'arrived-after-deadline-stream'});
owner.message({type:'assistant_delta',stream_id:'arrived-after-deadline-stream',
 text:'late canary'});
owner.message({type:'assistant_terminal',stream_id:'arrived-after-deadline-stream',state:'completed'});
await flush();
assert.equal(targetCalls().filter(call => call.url.endsWith('/cancel')).length,1);
assert(!document.querySelector('#messages').textContent.includes('late canary'));
assert.equal(await submitText('no automatic resurrection after deadline'),false);
assert.equal(targetCalls().filter(call => call.url.endsWith('/turns')).length,1);
dispatchWindow('beforeunload'); await flush();
assert(pending.every(call => call.options.signal.aborted)); assert.equal(timers.size,0);
"""
    )


def test_known_superseded_stream_terminal_cannot_clear_new_turn_or_partial() -> None:
    run_control(
        """
const owner = await readyControl();
owner.message({type:'turn_started',turn_id:'old-turn'});
owner.message({type:'assistant_started',stream_id:'old-stream'});
owner.message({type:'assistant_delta',stream_id:'old-stream',text:'old partial'});
owner.message({type:'turn_started',turn_id:'new-turn'});
owner.message({type:'assistant_started',stream_id:'new-stream'});
owner.message({type:'assistant_delta',stream_id:'new-stream',text:'new partial'});
owner.message({type:'assistant_terminal',stream_id:'old-stream',state:'cancelled'});
assert.equal(currentTurn,'new-turn'); assert.equal(assistantBubble.textContent,'new partial');
owner.message({type:'assistant_terminal',stream_id:'new-stream',state:'completed'});
assert.equal(currentTurn,undefined);
owner.message({type:'assistant_delta',stream_id:'new-stream',text:'terminal resurrection'});
assert(!document.querySelector('#messages').textContent.includes('terminal resurrection'));
"""
    )
