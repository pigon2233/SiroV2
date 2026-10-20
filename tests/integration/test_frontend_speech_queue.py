from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_SETUP = r"""
const assert = require('node:assert/strict');
const scenario = process.argv[1];
const status = {textContent:'', className:''}, calls = [], audios = [], revoked = [];
const connection = {};
const urls = new Map(), unhandled = [], timers = new Map();
let ttsAudio, ttsController, ttsGeneration = 0, speechCancelled = false, liveSpeech;
let currentTurn, assistantBubble;
const socket = {readyState:1}, owner = socket, epoch = 0, controlEpoch = 0, retired = false;
const log = () => {}, acceptRunEvent = () => true, markAuthenticated = () => {};
let clock = 0, timerSequence = 0, objectSequence = 0, voiceEnabled = true;
const performance = {now: () => clock};
Date.now = () => clock;
const setTimeout = (callback, delay) => {
 const id = ++timerSequence; timers.set(id, {callback, at:clock+delay}); return id;
};
const clearTimeout = id => timers.delete(id);
const document = {querySelector: selector =>
 selector === '#voice-output' ? {checked:voiceEnabled} :
 selector === '#connection' ? connection : status};
const headers = () => ({'Authorization':'Bearer synthetic-session'});
const pending = () => {
 let resolve, reject;
 const promise = new Promise((a,b) => {resolve=a; reject=b;});
 return {promise, resolve, reject};
};
const URL = {
 createObjectURL: blob => {
  const url='blob:synthetic-'+(++objectSequence);urls.set(url,blob);return url;
 },
 revokeObjectURL: url => {revoked.push(url);urls.delete(url);}
};
class Audio {
 constructor(src) {this.src=src;this.pauses=0;this.played=0;audios.push(this);}
 play() {this.played++;this.onplay?.();return this.playWait?.promise ?? Promise.resolve();}
 pause() {this.pauses++;}
 removeAttribute() {}
 load() {}
 end() {this.onended?.();}
 fail() {this.onerror?.(new Error('synthetic playback failure'));}
}
const authorizedFetch = (url, options) => {
 const call = {url, options, body:JSON.parse(options.body), ...pending()};
 calls.push(call); return call.promise;
};
const response = blob => ({ok:true,status:200,blob:() => Promise.resolve(blob)});
const planResponse = (segments=['甲。','乙。','丙。'], extra={}) => ({
 ok:true,status:200,json:async()=>({segments,spoken_text:segments.join(''),
  version:'synthetic-plan-v1',max_chars:80,max_segments:128,max_total_chars:8000,
  deadline_seconds:1200,...extra})
});
const tick = async () => {for(let i=0;i<20;i++)await Promise.resolve();};
const rendered = () => calls.filter(call => call.url === '/v1/audio/speech');
const completed = () => /完成/.test(status.textContent);
const succeeded = () => /全文朗讀完成/.test(status.textContent);
const failed = () => /失敗|未完成|上限|時限/.test(status.textContent) && !succeeded();
const run = text => {
 let settled=false;
 const promise=playTts(text,{rate:1.05,pitch:1.1}).finally(()=>{settled=true;});
 return {promise,settled:()=>settled};
};
const begin = async (segments=['甲。','乙。','丙。']) => {
 const work=run('synthetic canonical answer');
 assert.equal(calls[0]?.url,'/v1/audio/speech/plan',
  'canonical text must be planned before synthesis');
 calls[0].resolve(planResponse(segments));await tick();
 return work;
};
const deliver = async (index, blob='audio-'+index) => {
 const call=rendered()[index];assert(call,'expected segment request '+index);
 call.resolve(response(blob));await tick();return call;
};
const advance = async milliseconds => {
 clock+=milliseconds;
 for(const [id,timer] of [...timers])if(timer.at<=clock){timers.delete(id);timer.callback();}
 await tick();
};
const stopped = () => {
 assert(!succeeded(),'cancelled narration must not report success');
 assert.match(status.textContent,/停止|待命/);
 assert.equal(ttsAudio,undefined);assert.equal(urls.size,0);
};
const failureClean = () => {
 assert(failed(),'unsuccessful narration must report failure or limit: '+status.textContent);
 assert.equal(ttsAudio,undefined);assert.equal(urls.size,0);
};
process.on('unhandledRejection',error=>unhandled.push(error));
"""

_CHECKS = r"""
(async()=>{
 if(scenario==='canonical_plan') {
  const canonical='開頭。\n```sh\nsecret_synthetic_command\n```\n最後一句。';
  const work=run(canonical);
  assert.equal(calls[0]?.url,'/v1/audio/speech/plan',
   'first request must obtain a bounded speech plan');
  assert.deepEqual(calls[0].body,{text:canonical},'planning must retain fenced-code semantics');
  assert.equal(calls[0].options.method,'POST');
  stopTts();calls[0].resolve(planResponse());await work.promise;
  assert.equal(rendered().length,0);
 } else if(scenario==='ordered_prefetch') {
  const work=await begin();
  assert.equal(rendered().length,1,'only first segment is requested before playback');
  await deliver(0);
  assert.equal(audios.length,1);assert.equal(audios[0].played,1);
  assert.match(status.textContent,/0\/3/,'progress reports actual ended segments');
  assert.equal(rendered().length,2,'one next segment may prefetch while first plays');
  await deliver(1);
  assert.equal(audios.length,1,'prefetched segment must not play over current audio');
  assert.equal(rendered().length,2,'third segment cannot prefetch before first ended');
  assert(!completed());assert(!work.settled(),'play() resolution is not playback completion');
  audios[0].end();await tick();
  assert.equal(audios.length,2);assert.equal(audios[1].played,1);
  assert.match(status.textContent,/1\/3/);
  assert.equal(rendered().length,3);assert(!completed());
  await deliver(2);assert.equal(audios.length,2);
  audios[1].end();await tick();
  assert.equal(audios.length,3);assert.equal(audios[2].played,1);
  assert.match(status.textContent,/2\/3/);
  assert(!completed());assert(!work.settled());
  audios[2].end();await work.promise;
  assert(completed(),'only the last actual ended event completes narration');
  assert.match(status.textContent,/3\/3/);
  assert.deepEqual(rendered().map(call=>call.body.text),['甲。','乙。','丙。']);
  for(const call of rendered()){
   assert.equal(call.body.rate,1.05);assert.equal(call.body.pitch,1.1);
   assert.strictEqual(call.options.signal,calls[0].options.signal,
    'one generation owns plan and segments');
  }
  assert.equal(revoked.length,3);assert.equal(new Set(revoked).size,3);
  assert.equal(urls.size,0);assert.equal(ttsAudio,undefined);
  assert.equal(timers.size,0,'completed narration releases its deadline');
 } else if(scenario==='cancel_plan'||scenario==='cancel_plan_json') {
  const work=run('old synthetic answer');const call=calls[0];
  assert.equal(call.url,'/v1/audio/speech/plan');
  const json=pending();
  if(scenario==='cancel_plan_json'){
   call.resolve({ok:true,status:200,json:()=>json.promise});await tick();
  }
  stopTts();assert(call.options.signal.aborted);stopped();
  await work.promise;
  if(scenario==='cancel_plan')call.reject(new Error('late cancelled plan failure'));
  else json.reject(new Error('late cancelled plan JSON failure'));
  await tick();assert.equal(rendered().length,0);stopped();
  assert.equal(timers.size,0);
 } else if(scenario==='cancel_render'||scenario==='cancel_blob') {
  const work=await begin();const call=rendered()[0], blob=pending();
  if(scenario==='cancel_blob'){
   call.resolve({ok:true,status:200,blob:()=>blob.promise});await tick();
  }
  stopTts();assert(call.options.signal.aborted);stopped();
  await work.promise;
  if(scenario==='cancel_render')call.resolve(response('late-audio'));
  else blob.reject(new Error('late cancelled blob failure'));
  await tick();assert.equal(audios.length,0);assert.equal(rendered().length,1);stopped();
 } else if(['cancel_playing','cancel_prefetch','cancel_play_promise'].includes(scenario)) {
  const play=pending();
  if(scenario==='cancel_play_promise')Audio.prototype.play=function(){
   this.played++;this.onplay?.();return play.promise;
  };
  const work=await begin();await deliver(0);
  assert.equal(audios.length,1);const audio=audios[0], lateEnd=audio.onended;
  const next=rendered()[1], blob=pending();assert(next,'one next segment was prefetched');
  if(scenario==='cancel_prefetch'){
   next.resolve({ok:true,status:200,blob:()=>blob.promise});await tick();
  }
  stopTts();assert(next.options.signal.aborted);assert(audio.pauses>=1);stopped();
  await work.promise;
  lateEnd?.();
  if(scenario==='cancel_prefetch')blob.reject(new Error('late cancelled prefetch blob'));
  else next.reject(new Error('late prefetch failure after cancellation'));
  play.resolve();await tick();
  assert.equal(audios.length,1);assert.equal(rendered().length,2);stopped();
  assert.equal(timers.size,0);
 } else if(scenario==='supersede') {
  const old=await begin();await deliver(0);
  const oldAudio=audios[0], oldEnd=oldAudio.onended, oldPrefetch=rendered()[1];
  const newer=run('new synthetic answer');const newPlan=calls.at(-1);
  assert.equal(newPlan.url,'/v1/audio/speech/plan');
  assert(calls[0].options.signal.aborted);assert(oldAudio.pauses>=1);
  await old.promise;
  oldEnd?.();oldPrefetch.reject(new Error('old prefetch failed late'));
  newPlan.resolve(planResponse(['新的一句。']));await tick();await deliver(2,'new-audio');
  assert.equal(audios.length,2);assert.equal(audios[1].played,1);
  assert.match(status.textContent,/正在說話/,'old finally cannot reset newer playback');
  assert(!succeeded());audios[1].end();await newer.promise;
  assert(succeeded());assert.equal(rendered().length,3);
  assert.deepEqual(rendered().map(call=>call.body.text),['甲。','乙。','新的一句。']);
  assert.equal(urls.size,0);assert.equal(timers.size,0);
 } else if(scenario==='supersede_plan') {
  const old=run('old synthetic answer'), newer=run('new synthetic answer');
  assert(calls[0].options.signal.aborted);
  await old.promise;
  calls[1].resolve(planResponse(['新的一句。']));await tick();await deliver(0,'new-audio');
  calls[0].resolve(planResponse(['過時的一句。']));await tick();
  assert.equal(rendered().length,1);assert.equal(audios.length,1);
  assert.match(status.textContent,/正在說話/);audios[0].end();await newer.promise;
  assert(succeeded());assert.equal(urls.size,0);
 } else if(scenario==='new_turn') {
  const work=await begin();await deliver(0);
  socket.onmessage({data:JSON.stringify({type:'turn_started',turn_id:'new-turn'})});
  assert.equal(currentTurn,'new-turn');assert.equal(speechCancelled,false);
  assert(calls[0].options.signal.aborted);stopped();
  await work.promise;rendered()[1].reject(new Error('old turn prefetch failed late'));await tick();
  assert.equal(audios.length,1);assert.equal(rendered().length,2);stopped();
 } else if(scenario==='failure_plan'||scenario==='failure_plan_rejection') {
  const work=run('synthetic answer');
  if(scenario==='failure_plan')
   calls[0].resolve({ok:false,status:413,json:async()=>({detail:'synthetic plan limit'})});
  else calls[0].reject(new Error('synthetic plan network failure'));
  await work.promise;failureClean();assert.equal(rendered().length,0);
  assert.equal(timers.size,0);
 } else if(scenario==='failure_render') {
  const work=await begin();
  rendered()[0].resolve({ok:false,status:503,json:async()=>({detail:'synthetic worker failure'})});
  await work.promise;failureClean();assert.equal(audios.length,0);
  assert.equal(rendered().length,1,'failed synthesis must not silently retry or skip');
 } else if(scenario==='failure_blob') {
  const work=await begin();
  rendered()[0].resolve({ok:true,status:200,blob:async()=>{
   throw new Error('synthetic body read failure');
  }});
  await work.promise;failureClean();assert.equal(audios.length,0);
  assert.equal(rendered().length,1);
 } else if(scenario==='failure_prefetch') {
  const work=await begin();await deliver(0);
  rendered()[1].reject(new Error('synthetic prefetch failure'));await tick();
  assert(!succeeded());audios[0].end();await work.promise;
  failureClean();assert.equal(audios.length,1);assert.equal(rendered().length,2);
 } else if(scenario==='failure_playback'||scenario==='failure_play_promise') {
  const play=pending();
  if(scenario==='failure_play_promise')Audio.prototype.play=function(){
   this.played++;this.onplay?.();return play.promise;
  };
  const work=await begin();await deliver(0);
  if(scenario==='failure_playback')audios[0].fail();
  else play.reject(new Error('synthetic play promise rejected'));
  await work.promise;
  rendered()[1]?.reject(new Error('late prefetch failure after player failure'));
  await tick();failureClean();assert.equal(audios.length,1);
  assert(rendered().length<=2);assert.equal(timers.size,0);
 } else if(['deadline_render','deadline_blob','deadline_playing'].includes(scenario)) {
  const work=await begin();
  const blob=pending();
  assert([...timers.values()].some(timer=>timer.at<=1200000),'queue must have a total deadline');
  if(scenario==='deadline_playing'){
   await deliver(0);await deliver(1);
  }
  if(scenario==='deadline_blob'){
   rendered()[0].resolve({ok:true,status:200,blob:()=>blob.promise});await tick();
  }
  await advance(1200001);
  assert(calls[0].options.signal.aborted,'deadline cancels this generation');
  await work.promise;
  if(scenario==='deadline_render')rendered()[0].resolve(response('late-audio'));
  if(scenario==='deadline_blob')blob.reject(new Error('late timed-out blob failure'));
  await tick();failureClean();assert.match(status.textContent,/時限|期限|逾時/);
  assert(!succeeded());assert.equal(timers.size,0);
  assert.equal(audios.length,scenario==='deadline_playing'?1:0);
  if(audios.length)assert(audios[0].pauses>=1);
 } else if(scenario==='deadline_plan') {
  const work=run('synthetic answer');await advance(1200001);
  assert(calls[0].options.signal.aborted,'planning is included in the total deadline');
  await work.promise;
  calls[0].reject(Object.assign(new Error('late timed-out plan'),{name:'AbortError'}));
  await tick();failureClean();
  assert.equal(rendered().length,0);assert.equal(timers.size,0);
 } else if(scenario==='shorter_deadline') {
  const work=run('synthetic answer');
  calls[0].resolve(planResponse(['一句。'],{deadline_seconds:2}));await tick();
  await advance(2001);assert(calls[0].options.signal.aborted);
  await work.promise;rendered()[0].resolve(response('late-audio'));await tick();failureClean();
 } else if(scenario==='expired_plan_deadline') {
  const work=run('synthetic answer');await advance(3000);
  calls[0].resolve(planResponse(['一句。'],{deadline_seconds:2}));await tick();
  assert.equal(rendered().length,0,'expired plan must not start a synthesis request');
  await work.promise;failureClean();assert(calls[0].options.signal.aborted);
 } else if(scenario.startsWith('inconsistent_plan_')) {
  const work=run('synthetic answer');
  const variants={missing_tail:['首句。'],reordered:['尾句。','首句。'],
   duplicated:['首句。','首句。']};
  const segments=variants[scenario.slice('inconsistent_plan_'.length)];assert(segments);
  calls[0].resolve(planResponse(segments,{spoken_text:'首句。尾句。'}));await tick();
  assert.equal(rendered().length,0,
   'inconsistent plan must not synthesize an incomplete or changed script');
  await work.promise;failureClean();assert.equal(audios.length,0);
 } else if(scenario==='plan_boundary_separator') {
  const work=await begin(['首句。',' 尾句。']);await deliver(0);await deliver(1);
  audios[0].end();await tick();audios[1].end();await work.promise;
  assert(succeeded(),'exact full coverage retains normalized boundary separators');
  assert.deepEqual(rendered().map(call=>call.body.text),['首句。',' 尾句。']);
 } else if(scenario.startsWith('invalid_plan_')) {
  const work=run('synthetic answer');
  const variants={empty:[],blank:[''],count:Array(129).fill('句。'),
   segment:['字'.repeat(81)],total:Array(101).fill('字'.repeat(80))};
  const segments=variants[scenario.slice('invalid_plan_'.length)];assert(segments);
  calls[0].resolve(planResponse(segments));await work.promise;
  failureClean();assert.equal(rendered().length,0);assert.equal(audios.length,0);
 } else if(scenario==='live_stream') {
  const live=beginLiveSpeech();live.push('第一句。第二');await tick();
  assert.equal(calls[0]?.url,'/v1/audio/speech/plan','first finished sentence is planned at once');
  assert.equal(calls[0].body.text,'第一句。','unfinished sentence is not planned yet');
  calls[0].resolve(planResponse(['第一句。']));await tick();
  assert.equal(rendered().length,1,'a finished first sentence renders before the reply finishes');
  assert.equal(rendered()[0].body.text,'第一句。');
  live.push('句。第三句');await tick();
  assert.equal(calls[2].body.text,'第一句。第二句。');
  calls[2].resolve(planResponse(['第一句。','第二句。']));await tick();
  assert.equal(rendered().length,1,'last segment of a partial plan may still grow');
  await deliver(0);assert.equal(audios.length,1);assert.equal(audios[0].played,1);
  live.finish('第一句。第二句。第三句。尾。',{rate:1.05});await tick();
  const last=calls.filter(call=>call.url==='/v1/audio/speech/plan').at(-1);
  assert.equal(last.body.text,'第一句。第二句。第三句。尾。','completed reply is planned in full');
  last.resolve(planResponse(['第一句。','第二句。第三句。','尾。']));await tick();
  await deliver(1);audios[0].end();await tick();
  assert.equal(audios.length,2);await deliver(2);audios[1].end();await tick();
  assert.equal(audios.length,3);audios[2].end();await tick();
  assert(succeeded(),'live narration completes the whole reply: '+status.textContent);
  assert.match(status.textContent,/3\/3/);
  assert.deepEqual(rendered().map(call=>call.body.text),['第一句。','第二句。第三句。','尾。']);
  assert.equal(rendered()[2].body.rate,1.05,'final prosody applies to later segments');
  assert.equal(urls.size,0);assert.equal(timers.size,0);
 } else if(scenario==='live_realign') {
  const live=beginLiveSpeech();live.push('甲。');await tick();
  calls[0].resolve(planResponse(['甲。']));await tick();await deliver(0);
  live.finish('甲。乙。',{});await tick();
  const plans=()=>calls.filter(call=>call.url==='/v1/audio/speech/plan');
  plans()[1].resolve(planResponse(['甲。乙。']));await tick();
  assert.equal(plans()[2]?.body.text,'乙。','only the unheard rest is planned again');
  plans()[2].resolve(planResponse(['乙。']));await tick();
  await deliver(1);audios[0].end();await tick();audios[1].end();await tick();
  assert(succeeded(),status.textContent);
  assert.deepEqual(rendered().map(call=>call.body.text),['甲。','乙。'],'nothing is read twice');
 } else if(scenario==='live_boundary_moves') {
  const plans=()=>calls.filter(call=>call.url==='/v1/audio/speech/plan');
  const live=beginLiveSpeech();live.push('好。');await tick();
  plans()[0].resolve(planResponse(['好。']));await tick();await deliver(0);
  live.push('我看看。後面還有。再一句');await tick();
  assert.equal(plans()[1].body.text,'好。我看看。後面還有。');
  // The longer text moves the first boundary; reading must not stall until the reply ends.
  plans()[1].resolve(planResponse(['好。我看看。','後面還有。']));await tick();
  assert.equal(plans()[2]?.body.text,'我看看。後面還有。','only the unqueued rest is planned');
  plans()[2].resolve(planResponse(['我看看。','後面還有。']));await tick();
  assert.equal(rendered().length,2,'the next sentence is queued while the reply streams');
  assert.equal(rendered()[1].body.text,'我看看。');
  live.finish('好。我看看。後面還有。再一句。',{});await tick();
  plans()[3].resolve(planResponse(['好。我看看。','後面還有。再一句。']));await tick();
  assert.equal(plans()[4]?.body.text,'後面還有。再一句。');
  plans()[4].resolve(planResponse(['後面還有。再一句。']));await tick();
  await deliver(1);audios[0].end();await tick();await deliver(2);audios[1].end();await tick();
  audios[2].end();await tick();
  assert(succeeded(),status.textContent);
  assert.deepEqual(rendered().map(call=>call.body.text),['好。','我看看。','後面還有。再一句。']);
 } else if(scenario==='live_stop') {
  const live=beginLiveSpeech();live.push('甲。乙。');await tick();
  calls[0].resolve(planResponse(['甲。','乙。']));await tick();
  await deliver(0);assert.equal(audios.length,1);
  stopTts();assert(calls[0].options.signal.aborted);stopped();
  assert.equal(live.current(),false,'a stopped narration is no longer current');
  live.push('丙。');live.finish('甲。乙。丙。',{});await tick();
  assert.equal(calls.length,2,'stopped live narration plans and renders nothing more');
  stopped();assert.equal(timers.size,0);
 } else if(scenario==='live_code_fence') {
  const live=beginLiveSpeech();live.push('看這段\n```sh\necho 1。\n');await tick();
  assert.equal(calls[0]?.body.text,'看這段\n','open code fence is never planned early');
  stopTts();
 } else if(scenario==='voice_disabled') {
  voiceEnabled=false;const work=run('synthetic answer');await work.promise;
  assert.equal(calls.length,0);assert.equal(audios.length,0);assert(!succeeded());
 } else throw new Error('unknown test scenario '+scenario);
 await tick();assert.deepEqual(unhandled,[],'queue must consume stale prefetch rejections');
 console.log('QUEUE_OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""


@pytest.mark.parametrize(
    "scenario",
    [
        "canonical_plan",
        "ordered_prefetch",
        "cancel_plan",
        "cancel_plan_json",
        "cancel_render",
        "cancel_blob",
        "cancel_playing",
        "cancel_prefetch",
        "cancel_play_promise",
        "supersede",
        "supersede_plan",
        "new_turn",
        "failure_plan",
        "failure_plan_rejection",
        "failure_render",
        "failure_blob",
        "failure_prefetch",
        "failure_playback",
        "failure_play_promise",
        "deadline_plan",
        "deadline_render",
        "deadline_blob",
        "deadline_playing",
        "shorter_deadline",
        "expired_plan_deadline",
        "inconsistent_plan_missing_tail",
        "inconsistent_plan_reordered",
        "inconsistent_plan_duplicated",
        "plan_boundary_separator",
        "invalid_plan_empty",
        "invalid_plan_blank",
        "invalid_plan_count",
        "invalid_plan_segment",
        "invalid_plan_total",
        "voice_disabled",
        "live_stream",
        "live_realign",
        "live_boundary_moves",
        "live_stop",
        "live_code_fence",
    ],
)
def test_actual_frontend_speech_queue(scenario: str) -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    functions = html[
        html.index("function createForegroundControl(") : html.index("function wavFromBuffer(")
    ]
    handler = html[html.index("socket.onmessage =") : html.index("socket.onclose =")]
    result = subprocess.run(
        [
            "node",
            "--unhandled-rejections=strict",
            "-e",
            _SETUP + functions + handler + _CHECKS,
            scenario,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "QUEUE_OK" in result.stdout, "queue scenario exited before its assertions completed"
