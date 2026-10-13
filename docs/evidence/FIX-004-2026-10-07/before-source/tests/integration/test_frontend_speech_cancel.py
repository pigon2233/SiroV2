from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "scenario", ["pending", "blob", "supersede", "playing", "turn", "terminal"]
)
def test_actual_frontend_speech_cancel(scenario: str) -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    functions = html[
        html.index("function formatAssistantMessage(") : html.index("function wavFromBuffer(")
    ]
    cancel = next(
        line.strip()
        for line in html.splitlines()
        if 'document.querySelector("#cancel").onclick =' in line
    )
    handler = html[html.index("socket.onmessage =") : html.index("socket.onclose =")]
    setup = """
const assert = require('node:assert/strict');
const mode = process.argv[1];
const button = {}, status = {}, calls = [], audios = [], revoked = [];
let currentTurn, ttsAudio, ttsController, ttsGeneration = 0, speechCancelled = false;
let assistantBubble;
const socket = {}, log = () => {};
const acceptRunEvent = () => true;
const headers = () => ({});
const document = {querySelector: s => s === '#cancel' ? button : status};
const URL = {createObjectURL: () => 'blob:'+audios.length, revokeObjectURL: s => revoked.push(s)};
const pending = () => {
 let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});
 return {promise,resolve,reject};
};
class Audio {
 constructor(src) {this.src=src;this.pauses=0;this.played=0;audios.push(this);}
 play() {this.played++;this.onplay?.();return this.wait?.promise ?? Promise.resolve();}
 pause() {this.pauses++;}
}
const fetch = (url, options) => {
 const call={url,options,...pending()};calls.push(call);
 if(url!='/v1/audio/speech')return Promise.resolve({ok:true});
 return call.promise;
};
const response = blob => ({ok:true,blob:()=>Promise.resolve(blob)});
const tick = async()=>{await Promise.resolve();await Promise.resolve();await Promise.resolve();};
"""
    checks = """
(async()=>{
 if(mode==='pending'||mode==='turn') {
  if(mode==='turn')currentTurn='turn-A';
  const work=playTts('synthetic',{});
  const call=calls[0];
  call.options.signal.addEventListener('abort',()=>
    call.reject(Object.assign(new Error('abort'),{name:'AbortError'})));
  await button.onclick();await work;
  assert(call.options.signal.aborted);
  assert.equal(audios.length,0);
  assert.equal(status.textContent,'TTS 待命');
  if(mode==='turn')assert(calls.some(c=>c.url==='/v1/turns/turn-A/cancel'));
 } else if(mode==='terminal') {
  currentTurn='cancelled-turn';await button.onclick();
  assistantBubble={textContent:'late answer'};
  socket.onmessage({data:JSON.stringify({type:'assistant_terminal',state:'completed'})});
  assert.equal(calls.filter(c=>c.url==='/v1/audio/speech').length,0);
  socket.onmessage({data:JSON.stringify({type:'turn_started',turn_id:'new-turn'})});
  assistantBubble={textContent:'new answer'};
  socket.onmessage({data:JSON.stringify({type:'assistant_terminal',state:'completed'})});
  const speech=calls.find(c=>c.url==='/v1/audio/speech');assert(speech);
  speech.resolve(response('new'));await tick();
 } else if(mode==='blob') {
  const blob=pending();const work=playTts('old',{});
  calls[0].resolve({ok:true,blob:()=>blob.promise});await tick();
  await button.onclick();blob.resolve('late-blob');await work;
  assert.equal(audios.length,0);assert.equal(status.textContent,'TTS 待命');
 } else if(mode==='supersede') {
  const old=playTts('old',{});const newer=playTts('new',{});
  assert(calls[0].options.signal.aborted);
  calls[1].resolve(response('new'));await newer;
  calls[0].reject(new Error('old failed late'));await old;
  assert.equal(audios.length,1);assert.equal(status.textContent,'SIRO 正在說話');
  await button.onclick();assert(audios[0].pauses>=1);assert.equal(revoked.length,1);
 } else if(mode==='playing') {
  const delayed=pending();
  Audio.prototype.play=function(){this.played++;this.onplay?.();return delayed.promise;};
  const work=playTts('playing',{});calls[0].resolve(response('audio'));await tick();
  assert.equal(audios.length,1);await button.onclick();
  assert(audios[0].pauses>=1);assert.equal(ttsAudio,undefined);
  delayed.resolve();await work;
  assert(audios[0].pauses>=2);assert.equal(status.textContent,'TTS 待命');
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(
        ["node", "-e", setup + functions + cancel + handler + checks, scenario],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
