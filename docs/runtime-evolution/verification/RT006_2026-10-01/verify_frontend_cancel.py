"""Execute actual frontend functions with a pending synthetic fetch; no network/audio."""
from pathlib import Path
import subprocess

html = Path('src/siro/services/presentation/static/index.html').read_text()
play = html[html.index('async function playTts('):html.index('function wavFromBuffer(')]
cancel = next(line.strip() for line in html.splitlines() if 'document.querySelector("#cancel").onclick =' in line)
script = '''
const assert = require('node:assert/strict');
const button = {}, status = {}, calls = [];
let currentTurn = 'synthetic-turn', ttsAudio;
const headers = () => ({});
const document = {querySelector: selector => selector === '#cancel' ? button : status};
const fetch = (url, options) => {
  calls.push({url, options});
  if (url === '/v1/audio/speech') return new Promise(() => {});
  return Promise.resolve({ok: true});
};
''' + play + '\n' + cancel + '''
(async () => {
  playTts('synthetic text', {});
  await button.onclick();
  const speech = calls.find(c => c.url === '/v1/audio/speech');
  console.log(JSON.stringify({called_urls: calls.map(c => c.url),
    speech_has_abort_signal: Boolean(speech.options.signal),
    speech_aborted: Boolean(speech.options.signal?.aborted)}));
  assert(speech.options.signal?.aborted,
    'User cancel does not abort the outstanding TTS HTTP request');
})().catch(error => { console.error(error.message); process.exitCode = 1; });
'''
result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
print(result.stdout, end='')
print(result.stderr, end='')
raise SystemExit(result.returncode)
