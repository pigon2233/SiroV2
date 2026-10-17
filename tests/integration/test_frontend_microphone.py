from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "scenario", ["permission", "recording", "transcription", "limit", "start-error"]
)
def test_actual_microphone_stop_and_late_result_fence(scenario: str) -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    code = html[
        html.index("function wavFromBuffer(") : html.index(
            'document.querySelector("#cancel").onclick'
        )
    ]
    setup = r"""
const assert = require('node:assert/strict'), mode = process.argv[1];
const pending = () => {
 let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};
};
const tick=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
const listeners={}, button={textContent:'開始說話',addEventListener:(n,fn)=>listeners[n]=fn,
 dispatchEvent:e=>listeners[e.type]?.(e)}, status={}, text={}, chat={}, toggle={};
const nodes={'#voice':button,'#voice-status':status,'#text':text,'#chat':chat,
 '#microphone-toggle':toggle};
const document={querySelector:s=>nodes[s]};
const window={addEventListener:()=>{}}, timers=[];
const setTimeout=(fn,ms)=>{timers.push({fn,ms});return timers.length;}, clearTimeout=()=>{};
let microphoneEnabled=true,recorder,recordedChunks=[],navigationInitialized=false,pageClosing=false;
let submissions=0,transcriptions=0,started=0,stopped=0;
const permission=pending(), transcription=pending();
const track={stop:()=>stopped++},stream={getTracks:()=>[track]};
const navigator={mediaDevices:{getUserMedia:()=>permission.promise}};
class MediaRecorder {
 static isTypeSupported(){return true;}
 constructor(s){this.state='inactive';}
 start(){
  if(mode==='start-error')throw new Error('synthetic unavailable encoder');
  this.state='recording';started++;
 }
 stop(){
  this.state='inactive';this.ondataavailable?.({data:new Blob(['synthetic'])});this.onstop?.();
 }
}
class AudioContext {
 async decodeAudioData(){return {sampleRate:16000,getChannelData:()=>new Float32Array(160)};}
 async close(){}
}
const submitText=async()=>submissions++;
const authorizedFetch=(url,options)=>{
 if(url.startsWith('/v1/audio/transcriptions')){
  transcriptions++;transcription.options=options;return transcription.promise;
 }
 return Promise.resolve({ok:true,json:async()=>({})});
};
"""
    checks = r"""
(async()=>{
 const starting=button.onclick();
 if(mode==='permission') {
  button.dispatchEvent(new Event('siro:microphone-stop'));
  permission.resolve(stream);await starting;await tick();
  assert.equal(started,0);assert.equal(stopped,1);assert.equal(submissions,0);
 } else {
  permission.resolve(stream);await starting;
  if(mode==='start-error') {
   assert.equal(started,0);assert.equal(stopped,1);assert.equal(transcriptions,0);
  } else if(mode==='recording') {
   assert.equal(started,1);
   button.dispatchEvent(new Event('siro:microphone-stop'));await tick();
   assert.equal(stopped,1);assert.equal(transcriptions,0);assert.equal(submissions,0);
  } else {
   assert.equal(started,1);
   if(mode==='limit') {
    const deadline=timers.find(timer=>timer.ms===30000);
    assert(deadline,'recording needs a finite 30s deadline');deadline.fn();
   } else await button.onclick();
   await tick();assert.equal(transcriptions,1);
   if(mode==='transcription') {
    button.dispatchEvent(new Event('siro:microphone-stop'));
    assert(transcription.options.signal.aborted);
   }
   transcription.resolve({ok:true,json:async()=>({text:'synthetic recognized'})});await tick();
   assert.equal(submissions,mode==='limit'?1:0);assert.equal(stopped,1);
  }
 }
 console.log('MICROPHONE_OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(
        ["node", "--unhandled-rejections=strict", "-e", setup + code + checks, scenario],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "MICROPHONE_OK" in result.stdout
