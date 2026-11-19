'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const {
  buildMask, overOpaque, packBits, composePageMask, wantsCapture, pointerShouldNotify,
  CAPTURE_FALLBACK_MS, POINTER_INTERVAL_MS,
} = require('./click-mask.js');

function image(width, height, paint) {
  const bitmap = Buffer.alloc(width * height * 4);
  paint(bitmap, width, height);
  return {getSize: () => ({width, height}), toBitmap: () => bitmap};
}

test('buildMask keeps the 4px cell and alpha>16 cutoff', () => {
  const mask = buildMask(image(8, 8, (bitmap, width) => {
    const put = (x, y, alpha) => { bitmap[(y * width + x) * 4 + 3] = alpha; };
    put(0, 0, 16);
    put(5, 6, 17);
  }));
  assert.strictEqual(mask.columns, 2);
  assert.strictEqual(mask.rows, 2);
  assert.strictEqual(mask.occupied, 1);
  assert.strictEqual(mask.cells[1 * 2 + 1], 1);
  assert.strictEqual(mask.cells[0], 0);
});

test('overOpaque dilates one cell and keeps the loading rescue strip', () => {
  const mask = buildMask(image(16, 16, (bitmap, width) => {
    bitmap[(14 * width + 14) * 4 + 3] = 255;
  }));
  const bounds = {x: 100, y: 200, width: 16, height: 16};
  assert.strictEqual(overOpaque(mask, {x: 114, y: 214}, bounds), true);
  assert.strictEqual(overOpaque(mask, {x: 110, y: 210}, bounds), true);
  assert.strictEqual(overOpaque(mask, {x: 100, y: 200}, bounds), false);
  assert.strictEqual(overOpaque({occupied: 0}, {x: 100, y: 210}, bounds), true);
  assert.strictEqual(overOpaque({occupied: 0}, {x: 100, y: 260}, bounds), false);
});

test('page mask stamps the character grid and opaque UI rects', () => {
  const character = new Uint8Array(4);
  character[0] = 1;
  const mask = composePageMask({
    v: 1, width: 8, height: 8,
    character: {x: 0, y: 0, width: 8, height: 8, columns: 2, rows: 2, bits: packBits(character)},
    rects: [{x: 4, y: 4, w: 4, h: 4}],
  });
  assert.strictEqual(mask.occupied, 2);
  assert.strictEqual(mask.cells[0], 1);
  assert.strictEqual(mask.cells[1 * 2 + 1], 1);
  assert.strictEqual(overOpaque(mask, {x: 1, y: 1}, {x: 0, y: 0, width: 8, height: 8}), true);
});

test('page mask rejects a missing character, a bad payload, and an empty grid', () => {
  assert.strictEqual(composePageMask({v: 1, width: 8, height: 8, rects: []}), null);
  assert.strictEqual(composePageMask({
    v: 1, width: 8, height: 8,
    character: {x: 0, y: 0, width: 8, height: 8, columns: 1, rows: 1, bits: '@@@'},
    rects: [],
  }), null);
  assert.strictEqual(composePageMask({
    v: 1, width: 8, height: 8,
    character: {x: 0, y: 0, width: 8, height: 8, columns: 1, rows: 1, bits: packBits(new Uint8Array(1))},
    rects: [],
  }), null);
  assert.strictEqual(composePageMask({
    v: 1, width: 8, height: 8,
    character: {x: 0, y: 0, width: 8, height: 8, columns: 1, rows: 1, bits: packBits(Uint8Array.of(1))},
    rects: [{x: 0, y: 0, w: 1, h: Number.NaN}],
  }), null);
});

test('capturePage stays off while a page mask is current', () => {
  assert.strictEqual(wantsCapture({now: 1000, pageMaskAt: 0, maskStale: true}), true);
  assert.strictEqual(wantsCapture({now: 5000, pageMaskAt: 1000, maskStale: false}), false);
  assert.strictEqual(wantsCapture({now: 1000 + CAPTURE_FALLBACK_MS - 1, pageMaskAt: 1000, maskStale: true}), false);
  assert.strictEqual(wantsCapture({now: 1000 + CAPTURE_FALLBACK_MS, pageMaskAt: 1000, maskStale: true}), true);
});

test('pointer notices are immediate on enter/leave and otherwise throttled', () => {
  assert.strictEqual(pointerShouldNotify({now: 50, lastAt: 0, movedPx: Infinity, crossed: false}), true);
  assert.strictEqual(pointerShouldNotify({now: 80, lastAt: 50, movedPx: 7, crossed: false}), false);
  assert.strictEqual(pointerShouldNotify({now: 50 + POINTER_INTERVAL_MS - 1, lastAt: 50, movedPx: 40, crossed: false}), false);
  assert.strictEqual(pointerShouldNotify({now: 50 + POINTER_INTERVAL_MS, lastAt: 50, movedPx: 8, crossed: false}), true);
  assert.strictEqual(pointerShouldNotify({now: 60, lastAt: 50, movedPx: 0, crossed: true}), true);
});

test('the renderer bit pack matches the host decoder', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'renderers', 'vrm', 'src', 'main.js'), 'utf8');
  const start = source.indexOf('function packMaskBits');
  const end = source.indexOf('\nfunction ', start + 10);
  assert.ok(start > 0 && end > start);
  const packMaskBits = new Function(`${source.slice(start, end)}; return packMaskBits;`)();
  const cells = Uint8Array.from([1, 0, 0, 0, 0, 0, 0, 0, 1]);
  const mask = composePageMask({
    v: 1, width: 12, height: 12,
    character: {x: 0, y: 0, width: 12, height: 12, columns: 3, rows: 3, bits: packMaskBits(cells)},
    rects: [],
  });
  assert.strictEqual(mask.cells[0], 1);
  assert.strictEqual(mask.cells[2 * mask.columns + 2], 1);
  assert.strictEqual(mask.occupied, 2);
});
