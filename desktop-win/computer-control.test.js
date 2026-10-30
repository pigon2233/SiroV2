'use strict';
const test = require('node:test');
const assert = require('node:assert');
const {EventEmitter} = require('node:events');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const {ComputerControl} = require('./computer-control.js');

function fakeHelper(log, {silent = false} = {}) {
  const helper = new EventEmitter();
  helper.stdout = new EventEmitter();
  helper.stdin = {write: line => {
    log.push(JSON.parse(line));
    if (!silent) setImmediate(() => helper.stdout.emit('data', JSON.stringify({id: JSON.parse(line).id, ok: true}) + '\n'));
  }};
  helper.kill = () => { helper.killed = true; };
  setImmediate(() => helper.stdout.emit('data', JSON.stringify({id: 0, ok: true, ready: true}) + '\n'));
  return helper;
}
function make(opts = {}) {
  const log = []; const clock = {t: 1000};
  const cc = new ComputerControl({
    getBounds: () => ({x: 0, y: 0, width: 1920, height: 1080}), now: () => clock.t, env: opts.env || {},
    spawnHelper: () => (cc.last = fakeHelper(log, opts)),
  });
  return {cc, log, clock};
}

test('default off sends nothing', async () => {
  const {cc, log} = make();
  assert.strictEqual((await cc.execute({kind: 'click', x: 1, y: 1})).error, 'control_disabled');
  assert.strictEqual(log.length, 0);
});

test('enabled action reaches helper and resolves', async () => {
  const {cc, log} = make(); cc.enable();
  assert.strictEqual((await cc.execute({kind: 'click', x: 5, y: 6})).ok, true);
  assert.strictEqual(log.length, 1);
});

test('emergency stop latches, kills helper, survives disable until enable', async () => {
  const {cc, log} = make(); cc.enable();
  await cc.execute({kind: 'move', x: 1, y: 1});
  cc.stop();
  assert.ok(cc.last.killed);
  assert.strictEqual((await cc.execute({kind: 'move', x: 1, y: 1})).error, 'emergency_stop');
  cc.disable();
  assert.strictEqual((await cc.execute({kind: 'move', x: 1, y: 1})).error, 'emergency_stop');
  cc.enable();
  assert.strictEqual((await cc.execute({kind: 'move', x: 1, y: 1})).ok, true);
  assert.strictEqual(log.length, 2);
});

test('stop resolves in-flight action as not ok', async () => {
  const {cc} = make({silent: true}); cc.enable();
  const p = cc.execute({kind: 'move', x: 1, y: 1});
  cc.stop();
  assert.strictEqual((await p).error, 'emergency_stop');
});

test('timeout is outcome_unknown, never success', async () => {
  const {cc} = make({silent: true}); cc.enable();
  const realSetTimeout = global.setTimeout;
  global.setTimeout = (fn, ms) => realSetTimeout(fn, ms > 1000 ? 5 : ms);
  try { assert.strictEqual((await cc.execute({kind: 'move', x: 1, y: 1})).error, 'outcome_unknown'); }
  finally { global.setTimeout = realSetTimeout; }
});

test('rejections', async () => {
  const {cc, log} = make({env: {MY_API_TOKEN: 'canary-value-123456'}}); cc.enable();
  const reason = a => cc.execute(a).then(r => r.error);
  assert.strictEqual(await reason({kind: 'drag'}), 'action_not_allowed');
  assert.strictEqual(await reason({kind: 'click', x: 5000, y: 1}), 'out_of_bounds');
  assert.strictEqual(await reason({kind: 'click', x: 1, y: 1, button: 'middle'}), 'button_not_allowed');
  assert.strictEqual(await reason({kind: 'key', key: 'Control+Alt+Del'}), 'key_blocked');
  assert.strictEqual(await reason({kind: 'type', text: 'hi', focus_is_secret: true}), 'secret_field');
  assert.strictEqual(await reason({kind: 'type', text: 'sk-' + 'a'.repeat(24)}), 'secret_text');
  assert.strictEqual(await reason({kind: 'type', text: 'x canary-value-123456'}), 'secret_text');
  assert.strictEqual(await reason({kind: 'type', text: 'a'.repeat(201)}), 'text_length');
  assert.strictEqual(await reason({kind: 'scroll', amount: 99}), 'bad_amount');
  assert.strictEqual(log.length, 0);
});

test('rate limit per second', async () => {
  const {cc} = make(); cc.enable();
  const results = [];
  for (let i = 0; i < 6; i++) results.push((await cc.execute({kind: 'move', x: 1, y: 1})).ok);
  assert.deepStrictEqual(results, [true, true, true, true, true, false]);
});

test('window query only while active and bypasses input rate limit', async () => {
  const {cc} = make();
  assert.strictEqual((await cc.queryWindow()).error, 'control_disabled');
  cc.enable();
  for (let i = 0; i < 8; i++) assert.strictEqual((await cc.queryWindow()).ok, true);
  cc.stop();
  assert.strictEqual((await cc.queryWindow()).error, 'emergency_stop');
});

test('key hold time is bounded', async () => {
  const {cc} = make(); cc.enable();
  assert.strictEqual((await cc.execute({kind: 'key', key: 'left', hold_ms: 500})).ok, true);
  assert.strictEqual((await cc.execute({kind: 'key', key: 'left', hold_ms: 5000})).error, 'bad_hold');
  assert.strictEqual((await cc.execute({kind: 'key', key: 'left', hold_ms: null})).ok, true);
});

test('commands wait for a cold helper to announce ready; a helper that never does is unavailable', async () => {
  const log = [];
  const cc = new ComputerControl({getBounds: () => ({x: 0, y: 0, width: 1920, height: 1080}), env: {},
    spawnHelper: () => {
      const helper = new EventEmitter();
      helper.stdout = new EventEmitter();
      helper.stdin = {write: line => { log.push(JSON.parse(line)); setImmediate(() => helper.stdout.emit('data', JSON.stringify({id: JSON.parse(line).id, ok: true}) + '\n')); }};
      helper.kill = () => {};
      setTimeout(() => helper.stdout.emit('data', JSON.stringify({id: 0, ok: true, ready: true}) + '\n'), 60);
      return helper;
    }});
  cc.enable();
  const pending = cc.execute({kind: 'move', x: 1, y: 1});
  await delay(20);
  assert.strictEqual(log.length, 0); // nothing is written before the helper is ready
  assert.strictEqual((await pending).ok, true);
  assert.strictEqual(log.length, 1);
});

test('focus asks the helper only for plain program names and only while active', async () => {
  const {cc, log} = make();
  assert.strictEqual((await cc.focus('undertale.exe')).error, 'control_disabled');
  cc.enable();
  assert.strictEqual((await cc.focus('undertale.exe')).ok, true);
  assert.deepStrictEqual({kind: log[0].kind, process: log[0].process}, {kind: 'focus', process: 'undertale.exe'});
  for (const bad of ['', 'a b', '../x', 'x;rm', 5, null]) assert.strictEqual((await cc.focus(bad)).error, 'bad_process');
  cc.stop();
  assert.strictEqual((await cc.focus('undertale.exe')).error, 'emergency_stop');
});
