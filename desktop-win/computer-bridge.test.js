'use strict';
const test = require('node:test');
const assert = require('node:assert');
const {EventEmitter} = require('node:events');
const {ComputerControl} = require('./computer-control.js');
const {ComputerBridgeClient} = require('./computer-bridge.js');
const {makeObserver, fingerprint} = require('./computer-perception.js');

const TOKEN = 't'.repeat(40);
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

function fakeHelper(reply) {
  const helper = new EventEmitter();
  helper.stdout = new EventEmitter();
  helper.stdin = {write: line => {
    const action = JSON.parse(line);
    setImmediate(() => helper.stdout.emit('data', JSON.stringify({id: action.id, ok: true, ...reply(action)}) + '\n'));
  }};
  helper.kill = () => {};
  setImmediate(() => helper.stdout.emit('data', JSON.stringify({id: 0, ok: true, ready: true}) + '\n'));
  return helper;
}
function makeControl(reply = () => ({})) {
  return new ComputerControl({getBounds: () => ({x: 0, y: 0, width: 1920, height: 1080}), env: {}, spawnHelper: () => fakeHelper(reply)});
}
// Backend stand-in: serves queued commands on /poll and records /result, /state and /stop posts.
function fakeBackend(commands) {
  const posts = [];
  const fetchImpl = async (url, init) => {
    const path = url.replace(/^.*\/v1\/computer/, '');
    assert.strictEqual(init.headers['X-SIRO-Computer-Token'], TOKEN);
    posts.push({path, body: JSON.parse(init.body)});
    if (path === '/poll') {
      const command = commands.shift();
      if (!command) { await delay(10); return {status: 204, ok: true}; }
      return {status: 200, ok: true, json: async () => command};
    }
    return {status: 200, ok: true, json: async () => ({})};
  };
  return {posts, fetchImpl};
}

test('does not poll while control is off, and ignores a missing token', async () => {
  const control = makeControl(), backend = fakeBackend([]);
  const client = new ComputerBridgeClient({origin: 'http://x', token: TOKEN, control, observe: async () => ({ok: true}), fetchImpl: backend.fetchImpl});
  client.start(); await delay(80); client.halt();
  assert.strictEqual(backend.posts.filter(p => p.path === '/poll').length, 0);
  const none = new ComputerBridgeClient({origin: 'http://x', token: '', control, observe: async () => ({}), fetchImpl: backend.fetchImpl});
  none.start(); assert.strictEqual(none.running, false);
});

test('executes polled input and observe commands and posts results', async () => {
  const target = {window_id: '101', pid: 1001, rect: [0, 0, 800, 600], secret: false};
  const control = makeControl(() => target);
  const backend = fakeBackend([
    {id: 'b', op: 'observe', payload: {}},
    {id: 'a', op: 'input', payload: {kind: 'click', x: 5, y: 6, button: 'left', key: '', text: '', amount: 0, focus_is_secret: false}},
    {id: 'd', op: 'observe', payload: {}},
    {id: 'c', op: 'input', payload: {kind: 'key', key: 'alt+f4'}},
  ]);
  const client = new ComputerBridgeClient({origin: 'http://x', token: TOKEN, control, observe: async () => ({ok: true, data: {title: 'g', ...target}}), fetchImpl: backend.fetchImpl});
  control.enable(); client.start();
  await delay(150); client.halt();
  const results = Object.fromEntries(backend.posts.filter(p => p.path === '/result').map(p => [p.body.id, p.body]));
  assert.strictEqual(results.a.ok, true);
  assert.deepStrictEqual(results.b.data, {title: 'g', ...target});
  assert.strictEqual(results.c.ok, false);
  assert.strictEqual(results.c.error, 'key_blocked');
});

test('mirrors tray switch and emergency stop to the backend', async () => {
  const control = makeControl(), backend = fakeBackend([]);
  new ComputerBridgeClient({origin: 'http://x', token: TOKEN, control, observe: async () => ({}), fetchImpl: backend.fetchImpl});
  control.enable(); control.stop(); control.disable();
  await delay(20);
  assert.deepStrictEqual(backend.posts.map(p => [p.path, p.body.enabled]), [['/state', true], ['/stop', undefined], ['/state', false]]);
});

test('foreground change after observation must not send the stale action', async () => {
  let current = {window_id: '101', pid: 1001, rect: [0, 0, 800, 600], secret: false};
  const sent = [];
  const control = {active: true, listeners: [], queryWindow: async () => ({ok: true, data: current}),
    execute: async action => { sent.push(action); return {ok: true}; }};
  const client = new ComputerBridgeClient({origin: 'http://x', token: TOKEN, control,
    observe: async () => ({ok: true, data: {...current, process: 'game.exe', focus_is_secret: false}}),
    fetchImpl: async () => ({ok: true})});
  await client.handle({op: 'observe'});
  current = {window_id: '202', pid: 2002, rect: [0, 0, 800, 600], secret: false};
  const result = await client.handle({op: 'input', payload: {kind: 'key', key: 'z'}});
  assert.strictEqual(result.ok, false);
  assert.strictEqual(result.error, 'window_changed');
  assert.deepStrictEqual(sent, []);
});

test('newly focused password is rejected even in the same window', async () => {
  let current = {window_id: '101', pid: 1001, rect: [0, 0, 800, 600], secret: false};
  const sent = [];
  const control = {active: true, listeners: [], queryWindow: async () => ({ok: true, data: current}),
    execute: async action => { sent.push(action); return {ok: true}; }};
  const client = new ComputerBridgeClient({origin: 'http://x', token: TOKEN, control,
    observe: async () => ({ok: true, data: {...current, process: 'game.exe', focus_is_secret: false}}),
    fetchImpl: async () => ({ok: true})});
  await client.handle({op: 'observe'});
  current = {...current, secret: true};
  const result = await client.handle({op: 'input', payload: {kind: 'type', text: 'example'}});
  assert.strictEqual(result.ok, false);
  assert.strictEqual(result.error, 'secret_field_focused');
  assert.deepStrictEqual(sent, []);
});

test('identity is required, consumed once and fenced by owner stop', async () => {
  const target = {window_id: '101', pid: 1001, rect: [0, 0, 800, 600], secret: false};
  const sent = [];
  const control = {active: true, listeners: [], queryWindow: async () => ({ok: true, data: target}),
    execute: async action => { sent.push(action); return {ok: true}; }};
  const client = new ComputerBridgeClient({origin: 'http://x', token: TOKEN, control,
    observe: async () => ({ok: true, data: {...target, focus_is_secret: false}}),
    fetchImpl: async () => ({ok: true})});
  const cmd = {op: 'input', payload: {kind: 'key', key: 'z'}};
  assert.strictEqual((await client.handle(cmd)).error, 'missing_window_identity');
  await client.handle({op: 'observe'});
  assert.strictEqual((await client.handle(cmd)).ok, true);
  assert.deepStrictEqual(sent[0].expected_window, {window_id: '101', pid: 1001, rect: [0, 0, 800, 600]});
  assert.strictEqual((await client.handle(cmd)).error, 'missing_window_identity');
  await client.handle({op: 'observe'});
  control.listeners[0]('stopped');
  assert.strictEqual((await client.handle(cmd)).error, 'missing_window_identity');
  assert.strictEqual(sent.length, 1);
});

test('window movement and newly sensitive title reject the pending action', async () => {
  const original = {window_id: '101', pid: 1001, rect: [0, 0, 800, 600], title: 'Game', secret: false};
  let current = original;
  const sent = [];
  const control = {active: true, listeners: [], queryWindow: async () => ({ok: true, data: current}),
    execute: async action => { sent.push(action); return {ok: true}; }};
  const client = new ComputerBridgeClient({origin: 'http://x', token: TOKEN, control,
    observe: async () => ({ok: true, data: {...original, focus_is_secret: false}}),
    fetchImpl: async () => ({ok: true})});
  const cmd = {op: 'input', payload: {kind: 'key', key: 'z'}};
  await client.handle({op: 'observe'});
  current = {...original, rect: [20, 0, 800, 600]};
  assert.strictEqual((await client.handle(cmd)).error, 'window_changed');
  await client.handle({op: 'observe'});
  current = {...original, title: 'Sign in'};
  assert.strictEqual((await client.handle(cmd)).error, 'blocked_title');
  assert.deepStrictEqual(sent, []);
});

test('observation drops pixels if the foreground changes during capture', async () => {
  let query = 0;
  const control = {queryWindow: async () => ({ok: true, data: {title: 'Game', process: 'game.exe',
    window_id: String(++query), pid: 1001, rect: [0, 0, 800, 600], secret: false}})};
  const capturer = {getSources: async () => [{display_id: '7', thumbnail: fakeImage(1920, 1080, 40)}]};
  const result = await makeObserver({control, screen, desktopCapturer: capturer})();
  assert.deepStrictEqual(result, {ok: false, error: 'window_changed_during_capture'});
});

function fakeImage(width, height, luma) {
  const bitmap = Buffer.alloc(32 * 18 * 4, luma);
  return {
    isEmpty: () => false, getSize: () => ({width, height}),
    toPNG: () => Buffer.from('png'), toJPEG: () => Buffer.from('png'),
    resize: opts => (opts.width === 32 ? {toBitmap: () => bitmap} : fakeImage(opts.width, opts.height, luma)),
    crop: r => fakeImage(r.width, r.height, luma),
  };
}
const display = {id: 7, scaleFactor: 1.5, bounds: {x: 0, y: 0, width: 1280, height: 720}};
const secondary = {id: 9, scaleFactor: 1, bounds: {x: 1920, y: 0, width: 1920, height: 1080}};
const screen = {
  getPrimaryDisplay: () => display,
  getAllDisplays: () => [display, secondary],
};

test('observation reports physical screen, scaled image, fingerprint', async () => {
  const control = makeControl(() => ({title: 'Game', process: 'game.exe', rect: [0, 0, 800, 600], window_id: '101', pid: 1001, secret: false}));
  control.enable();
  const capturer = {getSources: async opts => {
    assert.deepStrictEqual(opts.thumbnailSize, {width: 1920, height: 1080});
    return [{display_id: '7', thumbnail: fakeImage(1920, 1080, 40)}];
  }};
  const result = await makeObserver({control, screen, desktopCapturer: capturer})();
  assert.strictEqual(result.ok, true);
  assert.deepStrictEqual(result.data.screen, [1920, 1080]);
  // Window rect [0,0,800,600] fits under MAX_WIDTH=1280 — no downscale.
  assert.deepStrictEqual(result.data.image_rect, [0, 0, 800, 600]);
  assert.deepStrictEqual(result.data.image_size, [800, 600]);
  assert.strictEqual(result.data.image_png_b64, Buffer.from('png').toString('base64'));
  assert.notStrictEqual(fingerprint(fakeImage(1, 1, 40)), fingerprint(fakeImage(1, 1, 200)));
  assert.strictEqual(fingerprint(fakeImage(1, 1, 40)), fingerprint(fakeImage(9, 9, 40)));
});

test('secondary-monitor window captures that display, not primary', async () => {
  const control = makeControl(() => ({
    title: 'Game', process: 'game.exe', rect: [2100, 100, 800, 600], window_id: '101', pid: 1001, secret: false,
  }));
  control.enable();
  const capturer = {getSources: async opts => {
    assert.deepStrictEqual(opts.thumbnailSize, {width: 1920, height: 1080});
    return [
      {display_id: '7', thumbnail: fakeImage(1920, 1080, 10)},
      {display_id: '9', thumbnail: fakeImage(1920, 1080, 200)},
    ];
  }};
  const result = await makeObserver({control, screen, desktopCapturer: capturer})();
  assert.strictEqual(result.ok, true);
  assert.deepStrictEqual(result.data.screen, [1920, 1080]);
  assert.deepStrictEqual(result.data.image_rect, [2100, 100, 800, 600]);
});

test('refuses to crop primary when the game is on a missing secondary source', async () => {
  const control = makeControl(() => ({
    title: 'Game', process: 'game.exe', rect: [2100, 100, 800, 600], window_id: '101', pid: 1001, secret: false,
  }));
  control.enable();
  const capturer = {getSources: async () => [{display_id: '7', thumbnail: fakeImage(1920, 1080, 10)}]};
  const result = await makeObserver({control, screen, desktopCapturer: capturer})();
  assert.deepStrictEqual(result, {ok: false, error: 'capture_wrong_display'});
});

test('no screenshot is taken while a password field has focus; off means no observation', async () => {
  const control = makeControl(() => ({title: 'Login', process: 'x.exe', rect: [0, 0, 10, 10], secret: true}));
  let captured = false;
  const capturer = {getSources: async () => { captured = true; return []; }};
  const observe = makeObserver({control, screen, desktopCapturer: capturer});
  assert.strictEqual((await observe()).error, 'control_disabled');
  control.enable();
  const result = await observe();
  assert.strictEqual(result.data.focus_is_secret, true);
  assert.strictEqual(result.data.image_png_b64, null);
  assert.strictEqual(captured, false);
});
