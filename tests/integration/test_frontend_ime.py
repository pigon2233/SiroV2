from __future__ import annotations

import subprocess
from pathlib import Path


def test_ime_candidate_enter_does_not_submit_chat() -> None:
    html = Path("src/siro/services/presentation/static/index.html").read_text()
    start = html.index("      let chatInputComposing = false;")
    end = html.index("      boot().catch(", start)
    listeners = html[start:end]
    harness = r"""
const assert = require('node:assert/strict');
const inputListeners = new Map();
let submissions = 0;
const input = {addEventListener(name, callback) { inputListeners.set(name, callback); }};
const chat = {requestSubmit() { submissions++; }};
const document = {querySelector(selector) { return selector === '#text' ? input : chat; }};
const send = (name, event = {}) => inputListeners.get(name)(event);
"""
    checks = r"""
const key = (overrides = {}) => ({
  key:'Enter', shiftKey:false, isComposing:false, keyCode:13, which:13,
  prevented:false, preventDefault() { this.prevented = true; }, ...overrides,
});

send('compositionstart');
const composingEnter = key(); send('keydown', composingEnter);
assert.equal(submissions, 0, 'Enter during IME composition must not submit');
assert.equal(composingEnter.prevented, false, 'IME must keep control of its Enter key');
send('compositionend');

const legacyImeEnter = key({keyCode:229, which:229}); send('keydown', legacyImeEnter);
assert.equal(submissions, 0, 'legacy IME keyCode 229 must not submit');
assert.equal(legacyImeEnter.prevented, false);

const composingFlagEnter = key({isComposing:true}); send('keydown', composingFlagEnter);
assert.equal(submissions, 0, 'isComposing must prevent submission even without composition events');
assert.equal(composingFlagEnter.prevented, false);

const legacyWhichEnter = key({which:229}); send('keydown', legacyWhichEnter);
assert.equal(submissions, 0, 'legacy event.which 229 must not submit');
assert.equal(legacyWhichEnter.prevented, false);

const ordinaryEnter = key(); send('keydown', ordinaryEnter);
assert.equal(submissions, 1, 'Enter after composition must submit once');
assert.equal(ordinaryEnter.prevented, true);

const shiftedEnter = key({shiftKey:true}); send('keydown', shiftedEnter);
assert.equal(submissions, 1, 'Shift+Enter must remain a newline');
assert.equal(shiftedEnter.prevented, false);
"""
    result = subprocess.run(
        ["node"],
        input=harness + listeners + checks,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
