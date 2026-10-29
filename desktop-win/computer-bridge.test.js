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
  const control = makeControl();
  const backend = fakeBackend([
    {id: 'a', op: 'input', payload: {kind: 'click', x: 5, y: 6, button: 'left', key: '', text: '', amount: 0, focus_is_secret: false}},
    {id: 'b', op: 'observe', payload: {}},
    {id: 'c', op: 'input', payload: {kind: 'key', key: 'alt+f4'}},
  ]);
  const client = new ComputerBridgeClient({origin: 'http://x', token: TOKEN, control, observe: async () => ({ok: true, data: {title: 'g'}}), fetchImpl: backend.fetchImpl});
  control.enable(); client.start();
  await delay(150); client.halt();
  const results = Object.fromEntries(backend.posts.filter(p => p.path === '/result').map(p => [p.body.id, p.body]));
  assert.strictEqual(results.a.ok, true);
  assert.deepStrictEqual(results.b.data, {title: 'g'});
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

function fakeImage(width, height, luma) {
  const bitmap = Buffer.alloc(32 * 18 * 4, luma);
  return {
    isEmpty: () => false, getSize: () => ({width, height}), toPNG: () => Buffer.from('png'),
    resize: opts => (opts.width === 32 ? {toBitmap: () => bitmap} : fakeImage(opts.width, opts.height, luma)),
    crop: r => fakeImage(r.width, r.height, luma),
  };
}
const display = {id: 7, scaleFactor: 1.5, bounds: {x: 0, y: 0, width: 1280, height: 720}};
const screen = {getPrimaryDisplay: () => display};

test('observation reports physical screen, scaled image, fingerprint', async () => {
  const control = makeControl(() => ({title: 'Game', process: 'game.exe', rect: [0, 0, 800, 600], secret: false}));
  control.enable();
  const capturer = {getSources: async opts => {
    assert.deepStrictEqual(opts.thumbnailSize, {width: 1920, height: 1080});
    return [{display_id: '7', thumbnail: fakeImage(1920, 1080, 40)}];
  }};
  const result = await makeObserver({control, screen, desktopCapturer: capturer})();
  assert.strictEqual(result.ok, true);
  assert.deepStrictEqual(result.data.screen, [1920, 1080]);
  // Window rect [0,0,800,600] is all that is captured: 800x600 fits under the width cap.
  assert.deepStrictEqual(result.data.image_rect, [0, 0, 800, 600]);
  assert.deepStrictEqual(result.data.image_size, [800, 600]);
  assert.strictEqual(result.data.image_png_b64, Buffer.from('png').toString('base64'));
  assert.notStrictEqual(fingerprint(fakeImage(1, 1, 40)), fingerprint(fakeImage(1, 1, 200)));
  assert.strictEqual(fingerprint(fakeImage(1, 1, 40)), fingerprint(fakeImage(9, 9, 40)));
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
