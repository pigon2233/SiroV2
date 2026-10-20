from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest


def run_frontend(checks: str) -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    script = html.split("<script>", 1)[1].split("</script>", 1)[0]
    # Keep the actual page functions and bindings, but supply events without a server.
    script = script[: script.rindex("      boot().catch(")]
    handler = html[html.index("socket.onmessage =") : html.index("socket.onclose =")]
    element_ids = json.dumps(re.findall(r'\bid="([^"]+)"', html))
    setup = r"""
const assert = require('node:assert/strict');
const roots = [];
class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this._text = ''; this.ownerDocument = document;
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  set innerHTML(value) { throw new Error('Untrusted message must not enter innerHTML'); }
  replaceChildren(...children) { this.children = []; this._text = ''; this.append(...children); }
  appendChild(child) { child.parent = this; this.children.push(child); return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  querySelector(selector) { return find(this.children, selector); }
  addEventListener() {}
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(c => c !== this); }
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
  querySelector: selector => find(roots, selector),
  querySelectorAll: () => [],
  getElementById: id => find(roots, '#' + id),
  createElement: tag => new Element(tag),
  createTextNode: text => {
    const node = new Element('#text'); node.textContent = text; return node;
  },
};
const window = {addEventListener() {}};
const location = {origin: 'http://localhost', host: 'localhost', protocol: 'http:'};
const pending = () => {
  let resolve; const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
};
const turnResponse = pending(), calls = [];
const fetch = (url, options) => {
  calls.push({url, options});
  if (url === '/v1/session') return Promise.resolve({ok:true,
    json:async()=>({token:'synthetic', expires_in_seconds:300})});
  return url === '/v1/conversations/browser/turns'
    ? turnResponse.promise : Promise.resolve({ok: true, json: async () => ({})});
};
"""
    initialize = f"""
for (const id of {element_ids}) {{
  const node = new Element('div'); node.id = id; roots.push(node);
}}
document.querySelector('#voice-output').checked = false;
"""
    # The page script is passed on stdin: as one argv string it exceeds Linux's 128 KiB limit.
    result = subprocess.run(
        ["node", "-"],
        input=setup
        + initialize
        + script
        + "\nsocket = {readyState:1}; controlAuthenticated = true;\n"
        + "const owner = socket, epoch = controlEpoch, retired = false;\n"
        + "const markAuthenticated = () => {};\n"
        + handler
        + "\nconst emit = data => socket.onmessage({data: JSON.stringify(data)});\n"
        + "(async () => {\n"
        + "await sessionAccess.getToken(); calls.length = 0;\n"
        + checks
        + "\n})().catch(error => { console.error(error); process.exitCode = 1; });",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("terminal_state", ["completed", "failed"])
def test_late_turn_http_response_cannot_resurrect_completed_turn(terminal_state: str) -> None:
    run_frontend(
        f"""
const submission = submitText('synthetic greeting');
emit({{type: 'turn_started', turn_id: 'ended-turn'}});
assert.equal(currentTurn, 'ended-turn');
emit({{type: 'assistant_started', stream_id: 'stream-1'}});
emit({{type: 'assistant_terminal', stream_id: 'stream-1', state: '{terminal_state}'}});
assert.equal(currentTurn, undefined);
turnResponse.resolve({{ok: true, json: async () => ({{turn_id: 'ended-turn'}})}});
await submission;
await document.querySelector('#cancel').onclick();
assert.equal(currentTurn, undefined);
assert.equal(calls.filter(call => call.url.includes('/cancel')).length, 0);
"""
    )


def test_model_terminal_failure_is_visible_in_assistant_message() -> None:
    run_frontend(
        """
emit({type: 'turn_started', turn_id: 'failed-turn'});
emit({type: 'assistant_started', stream_id: 'failed-stream'});
emit({type: 'assistant_terminal', stream_id: 'failed-stream', state: 'failed',
      error: 'provider_unavailable'});
const messages = document.querySelector('#messages').children;
assert.equal(messages.length, 1);
assert(messages[0].textContent.includes('provider_unavailable'));
assert.equal(currentTurn, undefined);
"""
    )


def test_partial_reply_keeps_text_and_displays_incomplete_notice_without_speaking() -> None:
    run_frontend(
        """
const spoken = [];
playTts = text => { spoken.push(text); };
emit({type: 'turn_started', turn_id: 'partial-turn'});
emit({type: 'assistant_started', stream_id: 'partial-stream'});
emit({type: 'assistant_delta', stream_id: 'partial-stream', text: '這段回答尚未'});
emit({type: 'assistant_terminal', stream_id: 'partial-stream', state: 'failed',
      error: 'ProviderOutputTruncated'});
const messages = document.querySelector('#messages').children;
assert.equal(messages.length, 1);
assert(messages[0].textContent.startsWith('這段回答尚未'));
assert(messages[0].textContent.includes('未完成'));
assert.equal(spoken.length, 0);
assert.equal(currentTurn, undefined);
"""
    )


def test_safe_mode_proposals_remain_independently_approvable() -> None:
    run_frontend(
        """
renderSnapshot({authorization_mode: 'safe', kill_switches: {}});
const first = {type: 'tool_proposal', proposal_id: 'first', capability: 'computer.execute',
               scope: 'read', target: 'synthetic first path', risk: 'low'};
const second = {...first, proposal_id: 'second', target: 'synthetic second path'};
emit(first); emit(second); emit(first);
assert.equal(document.querySelector('#computer-panel').open, true);
const cards = document.querySelector('#tool-proposals').children;
assert.equal(cards.length, 2);
assert.deepEqual(cards.map(card => card.id), ['tool-first', 'tool-second']);
const firstButton = cards[0].children.find(child => child.tagName === 'button');
const secondButton = cards[1].children.find(child => child.tagName === 'button');
assert(firstButton); assert(secondButton);
await firstButton.onclick();
assert.equal(firstButton.disabled, true);
assert.notEqual(secondButton.disabled, true);
await secondButton.onclick();
assert.deepEqual(calls.map(call => call.url), [
  '/v1/tool-proposals/first/approve', '/v1/tool-proposals/second/approve'
]);
for (const call of calls) {
  assert.equal(call.options.method, 'POST');
  assert.deepEqual(JSON.parse(call.options.body), {approved: true});
}
"""
    )


def test_completed_assistant_formats_text_without_interpreting_html() -> None:
    run_frontend(
        r"""
const source = '**狀態**\n請看 `cwd`。\n```text\n  hello **keep**\n' +
  '<script>globalThis.compromised = true</script>\n```\n<img src=x onerror=alert(1)>';
const spoken = [];
playTts = text => { spoken.push(text); };
beginLiveSpeech = () => undefined; // live narration is covered by its own tests
emit({type: 'turn_started', turn_id: 'format-turn'});
emit({type: 'assistant_started', stream_id: 'format-stream'});
emit({type: 'assistant_delta', stream_id: 'format-stream', text: source});
const message = document.querySelector('#messages').children[0];
assert.equal(message.textContent, source);
emit({type: 'assistant_terminal', stream_id: 'format-stream', state: 'completed'});
const block = message.children.find(child => child.tagName === 'pre');
assert(block);
assert.equal(block.children[0].tagName, 'code');
assert.equal(block.textContent,
  '  hello **keep**\n<script>globalThis.compromised = true</script>\n');
assert.equal(message.children.find(child => child.tagName === 'strong').textContent, '狀態');
assert.equal(message.children.find(child => child.tagName === 'code').textContent, 'cwd');
assert.equal(message.textContent,
  '狀態\n請看 cwd。\n  hello **keep**\n<script>globalThis.compromised = true</script>\n' +
  '<img src=x onerror=alert(1)>');
assert.deepEqual(spoken, [source]);
const tags = [];
const visit = node => { tags.push(node.tagName); node.children.forEach(visit); };
message.children.forEach(visit);
assert(tags.every(tag => ['#text', 'strong', 'code', 'pre'].includes(tag)));
assert.equal(globalThis.compromised, undefined);
"""
    )
