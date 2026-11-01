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
const display = {
  id: 7, scaleFactor: 1.5,
  bounds: {x: 0, y: 0, width: 1280, height: 720},
  workArea: {x: 0, y: 0, width: 1280, height: 700},
};
const secondary = {
  id: 9, scaleFactor: 1,
  bounds: {x: 1920, y: 0, width: 1920, height: 1080},
  workArea: {x: 1920, y: 0, width: 1920, height: 1040},
};
// Realistic mixed-DPI: secondary DIP origin = end of primary DIP (1280), physical origin = 1920.
const mixedPrimary = {
  id: 1, scaleFactor: 1.5,
  bounds: {x: 0, y: 0, width: 1280, height: 720},
  workArea: {x: 0, y: 0, width: 1280, height: 700},
};
const mixedSecondary = {
  id: 2, scaleFactor: 1,
  bounds: {x: 1280, y: 0, width: 1920, height: 1080},
  workArea: {x: 1280, y: 0, width: 1920, height: 1040},
};
function dipToScreenPoint({x, y}, displays = [display, secondary]) {
  // Approximate Electron: each display maps its DIP rect by its own scaleFactor,
  // with physical X origin = sum of prior display physical widths (left→right).
  const ordered = [...displays].sort((a, b) => a.bounds.x - b.bounds.x);
  let physX0 = 0;
  for (let i = 0; i < ordered.length; i++) {
    const d = ordered[i];
    const b = d.bounds;
    const f = d.scaleFactor || 1;
    const atEnd = i === ordered.length - 1 && x === b.x + b.width;
    if ((x >= b.x && x < b.x + b.width) || atEnd || (i === 0 && x <= b.x)) {
      return {
        x: Math.round(physX0 + (x - b.x) * f),
        y: Math.round(b.y * f + (y - b.y) * f),
      };
    }
    physX0 += b.width * f;
  }
  const last = ordered[ordered.length - 1];
  const f = last.scaleFactor || 1;
  return {x: Math.round(physX0 + (x - last.bounds.x - last.bounds.width) * f), y: Math.round(y * f)};
}
const screen = {
  getPrimaryDisplay: () => display,
  getAllDisplays: () => [display, secondary],
  dipToScreenPoint: p => dipToScreenPoint(p, [display, secondary]),
};
const mixedScreen = {
  getPrimaryDisplay: () => mixedPrimary,
  getAllDisplays: () => [mixedPrimary, mixedSecondary],
  dipToScreenPoint: p => dipToScreenPoint(p, [mixedPrimary, mixedSecondary]),
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

test('mixed-DPI secondary: dipToScreenPoint origin, not bounds*scaleFactor', async () => {
  const {physicalBounds} = require('./computer-perception.js');
  // Old bug: secondary.bounds.x(1280)*scale(1)=1280. Correct physical origin is 1920.
  const wrong = Math.round(mixedSecondary.bounds.x * mixedSecondary.scaleFactor);
  const right = physicalBounds(mixedScreen, mixedSecondary);
  assert.strictEqual(wrong, 1280);
  assert.strictEqual(right.x, 1920);
  assert.strictEqual(right.width, 1920);
  const control = makeControl(() => ({
    title: 'Game', process: 'game.exe', rect: [2100, 100, 800, 600], window_id: '101', pid: 1001, secret: false,
  }));
  control.enable();
  let crop = null;
  const capturer = {getSources: async opts => {
    assert.deepStrictEqual(opts.thumbnailSize, {width: 1920, height: 1080});
    const thumb = fakeImage(1920, 1080, 200);
    const orig = thumb.crop;
    thumb.crop = r => { crop = r; return orig.call(thumb, r); };
    return [
      {display_id: '1', thumbnail: fakeImage(1920, 1080, 10)},
      {display_id: '2', thumbnail: thumb},
    ];
  }};
  const result = await makeObserver({control, screen: mixedScreen, desktopCapturer: capturer})();
  assert.strictEqual(result.ok, true);
  assert.deepStrictEqual(result.data.image_rect, [2100, 100, 800, 600]);
  // Crop offset = window.x - physicalOrigin = 2100-1920 = 180 (not 2100-1280=820).
  assert.deepStrictEqual(crop, {x: 180, y: 100, width: 800, height: 600});
});

test('thumbnail smaller than physical still crops with scale', async () => {
  const control = makeControl(() => ({
    title: 'Game', process: 'game.exe', rect: [0, 0, 800, 600], window_id: '101', pid: 1001, secret: false,
  }));
  control.enable();
  let crop = null;
  const capturer = {getSources: async () => {
    // Electron sometimes returns a thumbnail half the requested physical size.
    const thumb = fakeImage(960, 540, 40);
    const orig = thumb.crop;
    thumb.crop = r => { crop = r; return orig.call(thumb, r); };
    return [{display_id: '7', thumbnail: thumb}];
  }};
  const result = await makeObserver({control, screen, desktopCapturer: capturer})();
  assert.strictEqual(result.ok, true);
  assert.deepStrictEqual(crop, {x: 0, y: 0, width: 400, height: 300});
  assert.deepStrictEqual(result.data.image_rect, [0, 0, 800, 600]);
  assert.deepStrictEqual(result.data.image_size, [400, 300]);
  assert.deepStrictEqual(result.data.capture_size, [960, 540]);
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

test('parks hidden helper on game display, not a visible pet window', async () => {
  const {parkHostOnDisplay} = require('./computer-perception.js');
  const moves = [];
  const helper = {
    isDestroyed: () => false,
    isVisible: () => false,
    hide: () => moves.push('hide'),
    setPosition: (x, y) => moves.push(['pos', x, y]),
  };
  parkHostOnDisplay(helper, secondary);
  assert.deepStrictEqual(moves, ['hide', ['pos', 1928, 8]]);
});

test('clearPetFromGame slides visible pet off overlapping game, stays shown', async () => {
  const {clearPetFromGame} = require('./computer-perception.js');
  const moves = [];
  const pet = {
    isDestroyed: () => false,
    isVisible: () => true,
    getBounds: () => ({x: 2200, y: 200, width: 360, height: 640}),
    setPosition: (x, y) => moves.push(['pos', x, y]),
    showInactive: () => moves.push('show'),
  };
  // Game on secondary physical [2100,100,800,600]; pet overlaps it.
  const home = clearPetFromGame(pet, screen, [2100, 100, 800, 600]);
  assert.ok(home);
  assert.strictEqual(home.x, 2200);
  assert.ok(moves.some(m => m === 'show' || (Array.isArray(m) && m[0] === 'pos')));
  // After move, position must not still be inside the game DIP approx on secondary.
  const pos = moves.find(m => Array.isArray(m) && m[0] === 'pos');
  assert.ok(pos[1] + 360 <= 2100 || pos[1] >= 2100 + 800 || pos[2] + 640 <= 100 || pos[2] >= 100 + 600);
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
