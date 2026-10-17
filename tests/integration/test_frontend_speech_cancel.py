from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "scenario",
    ["pending", "blob", "supersede", "playing", "turn", "terminal", "replay", "disable"],
)
def test_actual_frontend_speech_cancel(scenario: str) -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    functions = html[
        html.index("function createForegroundControl(") : html.index("function wavFromBuffer(")
    ]
    cancel = html[
        html.index('document.querySelector("#cancel").onclick =') : html.index(
            'window.addEventListener("message",'
        )
    ]
    handler = html[html.index("socket.onmessage =") : html.index("socket.onclose =")]
    setup = r"""
const assert = require('node:assert/strict');
const mode = process.argv[1];
const button = {}, status = {}, service = {}, replay = {}, voice = {checked:true};
const calls = [], audios = [], revoked = [];
let currentTurn, ttsAudio, ttsController, ttsGeneration = 0, speechCancelled = false;
let assistantBubble, lastSpeech;
const pageClosing = false, socket = {readyState:1}, log = () => {};
const owner = socket, epoch = 0, controlEpoch = 0, retired = false, markAuthenticated = () => {};
let submissionGeneration = 0, pendingSubmission;
const acceptRunEvent = () => true;
const headers = () => ({});
const document = {querySelector: selector => selector === '#cancel' ? button :
 selector === '#voice-output' ? voice : selector === '#replay-speech' ? replay :
 selector === '#service-notice' ? service : status};
const URL = {createObjectURL: () => 'blob:'+audios.length, revokeObjectURL: s => revoked.push(s)};
const pending = () => {
 let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});
 return {promise,resolve,reject};
};
class Audio {
 constructor(src) {this.src=src;this.pauses=0;this.played=0;audios.push(this);}
 play() {this.played++;this.onplay?.();return this.wait?.promise ?? Promise.resolve();}
 pause() {this.pauses++;}
 end() {this.onended?.();}
}
const plan = () => ({ok:true,json:async()=>({segments:['完整的合成語音。'],
 spoken_text:'完整的合成語音。',version:'synthetic-plan-v1',
 max_chars:80,max_segments:128,max_total_chars:8000,deadline_seconds:1200})});
const authorizedFetch = (url, options) => {
 const call={url,options,...pending()};calls.push(call);
 if(url==='/v1/audio/speech/plan' && !['pending','turn'].includes(mode))
  return Promise.resolve(plan());
 if(url==='/v1/audio/speech'||url==='/v1/audio/speech/plan')return call.promise;
 return Promise.resolve({ok:true,json:async()=>({active_turns:{browser:{state:'cancelled'}}})});
};
const response = blob => ({ok:true,blob:()=>Promise.resolve(blob)});
const tick = async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
const speeches = () => calls.filter(call=>call.url==='/v1/audio/speech');
"""
    checks = r"""
(async()=>{
 if(mode==='pending'||mode==='turn') {
  if(mode==='turn')currentTurn='turn-A';
  const work=playTts('synthetic',{}), call=calls[0];
  assert.equal(call.url,'/v1/audio/speech/plan');
  await button.onclick();await work;
  assert(call.options.signal.aborted);assert.equal(audios.length,0);
  assert.equal(status.textContent,'朗讀已停止');
  call.resolve(plan());await tick();assert.equal(speeches().length,0);
  if(mode==='turn')assert(calls.some(c=>c.url==='/v1/turns/turn-A/cancel'));
 } else if(mode==='terminal') {
  currentTurn='cancelled-turn';await button.onclick();
  assistantBubble={textContent:'late answer'};
  socket.onmessage({data:JSON.stringify({type:'assistant_terminal',state:'completed'})});
  await tick();assert.equal(calls.filter(c=>c.url==='/v1/audio/speech/plan').length,0);
  foregroundControl.begin(new AbortController()); // A new explicit submission owns the next turn.
  socket.onmessage({data:JSON.stringify({type:'turn_started',turn_id:'new-turn'})});
  assistantBubble={textContent:'new answer'};
  socket.onmessage({data:JSON.stringify({type:'assistant_terminal',state:'completed'})});
  await tick();const speech=speeches()[0];assert(speech);
  speech.resolve(response('new'));await tick();
  assert.equal(lastSpeech.text,'new answer');assert.equal(replay.disabled,false);
  assert.equal(audios.length,1);audios[0].end();await tick();
  assert.match(status.textContent,/全文朗讀完成/);
 } else if(mode==='blob') {
  const blob=pending(),work=playTts('old',{});await tick();
  speeches()[0].resolve({ok:true,blob:()=>blob.promise});await tick();
  await button.onclick();await work;
  blob.resolve('late-blob');await tick();assert.equal(audios.length,0);
  assert.equal(status.textContent,'朗讀已停止');
 } else if(mode==='supersede') {
  const old=playTts('old',{});await tick();const oldCall=speeches()[0];
  const newer=playTts('new',{});await tick();
  assert(oldCall.options.signal.aborted);
  speeches()[1].resolve(response('new'));await tick();await old;
  oldCall.reject(new Error('old failed late'));await tick();
  assert.equal(audios.length,1);assert.match(status.textContent,/正在說話/);
  assert(ttsController,'old cleanup must not detach newer owner');
  audios[0].end();await newer;
  assert.match(status.textContent,/全文朗讀完成/);assert.equal(revoked.length,1);
 } else if(mode==='playing') {
  const delayed=pending();
  Audio.prototype.play=function(){this.played++;this.onplay?.();return delayed.promise;};
  const work=playTts('playing',{});await tick();
  speeches()[0].resolve(response('audio'));await tick();
  assert.equal(audios.length,1);await button.onclick();await work;
  assert(audios[0].pauses>=1);assert.equal(ttsAudio,undefined);assert.equal(revoked.length,1);
  delayed.resolve();await tick();
  assert(audios[0].pauses>=2);assert.equal(status.textContent,'朗讀已停止');
 } else if(mode==='replay') {
  voice.checked=false;speechCancelled=true;
  const canonical='前言。\n```sh\nprintf synthetic\n```\n尾句。';
  lastSpeech={text:canonical,prosody:{rate:1.1}};
  const work=replay.onclick();await tick();
  assert(voice.checked,'manual replay visibly enables speech');assert(!speechCancelled);
  assert.deepEqual(JSON.parse(calls[0].options.body),{text:canonical});
  assert.equal(speeches()[0].options.method,'POST');
  assert.equal(JSON.parse(speeches()[0].options.body).rate,1.1);
  speeches()[0].resolve(response('replay'));await tick();
  assert(!/全文朗讀完成/.test(status.textContent));audios[0].end();await work;
  assert.match(status.textContent,/全文朗讀完成/);assert.equal(revoked.length,1);
 } else if(mode==='disable') {
  const work=playTts('playing',{});await tick();
  speeches()[0].resolve(response('audio'));await tick();
  voice.checked=false;voice.onchange({target:voice});await work;
  assert.equal(ttsAudio,undefined);assert.equal(revoked.length,1);
  assert.equal(status.textContent,'朗讀已停止');
 }
 console.log('CANCEL_OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(
        [
            "node",
            "--unhandled-rejections=strict",
            "-e",
            setup + functions + cancel + handler + checks,
            scenario,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "CANCEL_OK" in result.stdout, "cancel assertions must reach completion"
