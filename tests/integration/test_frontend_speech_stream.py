# ruff: noqa: E501
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from test_frontend_speech_queue import _SETUP

_EXTRA = r"""
speechStream = true;
const contexts = [], readers = [];
class FakeContext {
 constructor(options) {this.options = options; this.currentTime = 0; this.sources = []; this.closed = false;
  this.destination = {}; contexts.push(this);}
 resume() {return Promise.resolve();}
 createBuffer(channels, length, rate) {
  const data = new Float32Array(length); return {duration: length / rate, getChannelData: () => data};
 }
 createBufferSource() {
  const source = {buffer: null, connect() {}, start(at) {source.at = at;}, stop() {source.stopped = true;}};
  this.sources.push(source); return source;
 }
 close() {this.closed = true; return Promise.resolve();}
}
globalThis.AudioContext = FakeContext;
const streamed = () => calls.filter(call => call.url === '/v1/audio/speech/stream');
const pcm = samples => new Uint8Array(new Int16Array(samples).buffer);
const streamResponse = (chunks, hang = false) => {
 const queue = [...chunks], reader = {cancelled: false, hung: pending()};
 reader.hung.promise.catch(() => {});
 reader.read = () => queue.length ? Promise.resolve({done: false, value: queue.shift()})
  : hang ? reader.hung.promise : Promise.resolve({done: true});
 reader.cancel = () => {reader.cancelled = true; reader.hung.reject(new Error('cancelled')); return Promise.resolve();};
 readers.push(reader);
 return {ok: true, status: 200, headers: {get: () => 'audio/L16;rate=24000;channels=1'},
  body: {getReader: () => reader}};
};
"""

_CHECKS = r"""
(async () => {
 const work = await begin(['甲。', '乙。']);
 assert.equal(streamed().length, 1, 'first segment goes to the streaming endpoint');
 assert.equal(rendered().length, 0);
 if (scenario === 'plays_chunks') {
  streamed()[0].resolve(streamResponse([pcm([1, 2, 3, 4]), pcm([5, 6])]));
  await tick();
  assert.equal(contexts.length, 1);
  assert.equal(contexts[0].options.sampleRate, 24000);
  assert.equal(contexts[0].sources.length, 2, 'every chunk is scheduled');
  assert(contexts[0].sources[1].at > contexts[0].sources[0].at, 'chunks are scheduled back to back');
  assert.match(status.textContent, /正在說話/);
  assert.equal(rendered().length, 1, 'next segment prefetches while the first plays');
  await deliver(0, 'audio-乙');
  await advance(1000);
  assert.equal(audios.length, 1, 'second segment plays after the stream ended');
  audios[0].end();
  await work.promise;
  assert(succeeded(), status.textContent);
  assert.equal(ttsAudio, undefined);
  assert(contexts[0].closed);
 } else if (scenario === 'falls_back') {
  streamed()[0].resolve({ok: false, status: 501, json: async () => ({detail: 'off'})});
  await tick();
  assert.equal(rendered().length, 1, 'a refused stream falls back to the whole sentence');
  await deliver(0);
  assert.equal(audios.length, 1);
  audios[0].end(); await tick();
  await deliver(1); audios[1].end(); await work.promise;
  assert(succeeded(), status.textContent);
 } else if (scenario === 'stop_mid_stream') {
  streamed()[0].resolve(streamResponse([pcm([1, 2, 3, 4])], true));
  await tick();
  assert.equal(contexts[0].sources.length, 1);
  stopTts(); await tick();
  assert(readers[0].cancelled, 'the network read is cancelled');
  assert(contexts[0].closed && contexts[0].sources[0].stopped, 'scheduled audio is silenced');
  await work.promise.catch(() => {});
  assert.equal(ttsAudio, undefined);
  assert(!succeeded());
 } else if (scenario === 'broken_stream') {
  const response = streamResponse([pcm([1, 2])], true);
  streamed()[0].resolve(response);
  await tick();
  readers[0].hung.reject(new Error('connection reset')); await tick();
  await work.promise;
  assert(failed(), status.textContent);
  assert.equal(ttsAudio, undefined);
 }
 assert.equal(unhandled.length, 0);
 console.log('STREAM_OK');
})().catch(error => {console.error(error); process.exitCode = 1;});
"""


@pytest.mark.parametrize(
    "scenario", ["plays_chunks", "falls_back", "stop_mid_stream", "broken_stream"]
)
def test_frontend_streams_the_first_segment(scenario: str) -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text(encoding="utf-8")
    functions = html[
        html.index("function createForegroundControl(") : html.index("function wavFromBuffer(")
    ]
    handler = html[html.index("socket.onmessage =") : html.index("socket.onclose =")]
    result = subprocess.run(
        [
            "node",
            "--unhandled-rejections=strict",
            "-e",
            _SETUP + functions + handler + _EXTRA + _CHECKS,
            scenario,
        ],
        capture_output=True,
        text=True,
        timeout=10,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert "STREAM_OK" in result.stdout
