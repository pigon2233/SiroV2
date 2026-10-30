'use strict';
// Real Windows helper; every action has an invalid target and must be rejected before input.
const test = require('node:test');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const path = require('node:path');
const readline = require('node:readline');

test('native helper rejects missing and impossible window identities', {timeout: 30000}, async t => {
  const helper = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
    '-File', path.join(__dirname, 'input-helper.ps1')], {windowsHide: true, stdio: ['pipe', 'pipe', 'pipe']});
  let stderr = '';
  helper.stderr.on('data', chunk => { stderr += chunk; });
  const lines = readline.createInterface({input: helper.stdout})[Symbol.asyncIterator]();
  async function next() {
    const line = await lines.next();
    assert.equal(line.done, false, stderr);
    return JSON.parse(line.value);
  }
  try {
    assert.equal((await next()).ready, true);
    helper.stdin.write(JSON.stringify({id: 1, kind: 'key', key: 'z'}) + '\n');
    const missing = await next();
    assert.equal(missing.ok, false);
    assert.equal(missing.error, 'missing_window_identity');
    helper.stdin.write(JSON.stringify({id: 2, kind: 'key', key: 'z',
      expected_window: {window_id: '0', pid: 0, rect: [0, 0, 1, 1]}}) + '\n');
    const mismatch = await next();
    assert.equal(mismatch.ok, false);
    assert.equal(mismatch.error, 'window_changed');
    helper.stdin.write(JSON.stringify({id: 3, kind: 'window'}) + '\n');
    const current = await next();
    assert.equal(current.ok, true);
    assert.match(current.window_id, /^\d+$/);
    assert.ok(current.pid > 0);
    assert.equal(current.rect.length, 4);
    if (!current.secret) {
      // The key name is deliberately invalid. It cannot generate an input even if the target matches.
      helper.stdin.write(JSON.stringify({id: 4, kind: 'key', key: 'invalid-key-name',
        expected_window: {window_id: current.window_id, pid: current.pid, rect: current.rect}}) + '\n');
      const validated = await next();
      t.diagnostic(`live-window check: ${validated.error}`);
      assert.equal(validated.ok, false);
      assert.match(validated.error, /unknown key|window_changed|secret_field_focused/);
    }
  } finally {
    helper.stdin.end();
    helper.kill();
  }
});
