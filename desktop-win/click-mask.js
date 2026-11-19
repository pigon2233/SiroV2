'use strict';

// Click-through hit grid shared by the Electron host. Cells are 4 CSS pixels.
// A cell is opaque when any sample in it has alpha above the same cutoff the
// old full-window scan used. The cursor test still dilates by one cell.

const CELL = 4;
const ALPHA = 16;
const CAPTURE_FALLBACK_MS = 2500;
const POINTER_MOVE_PX = 8;
const POINTER_INTERVAL_MS = 100;
const MAX_EDGE = 4096;
const MAX_CELLS = 1024 * 1024;
const MAX_RECTS = 48;

function buildMask(image) {
  const {width, height} = image.getSize();
  const bitmap = image.toBitmap();
  const columns = Math.ceil(width / CELL);
  const rows = Math.ceil(height / CELL);
  const cells = new Uint8Array(columns * rows);
  let occupied = 0;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (bitmap[(y * width + x) * 4 + 3] <= ALPHA) continue;
      const i = Math.floor(y / CELL) * columns + Math.floor(x / CELL);
      if (!cells[i]) { cells[i] = 1; occupied++; }
    }
  }
  return {width, height, columns, rows, cells, occupied};
}

function overOpaque(mask, point, bounds) {
  if (!mask || mask.occupied === 0) return point.y - bounds.y < 48;
  const px = (point.x - bounds.x) * mask.width / bounds.width;
  const py = (point.y - bounds.y) * mask.height / bounds.height;
  if (px < 0 || py < 0 || px >= mask.width || py >= mask.height) return false;
  const cx = Math.floor(px / CELL);
  const cy = Math.floor(py / CELL);
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      const x = cx + dx;
      const y = cy + dy;
      if (x >= 0 && y >= 0 && x < mask.columns && y < mask.rows && mask.cells[y * mask.columns + x]) return true;
    }
  }
  return false;
}

// Least-significant bit of byte i>>3 holds cell i. Same order as packMaskBits in the VRM renderer.
function unpackBits(bits, count) {
  if (typeof bits !== 'string' || bits.length > 200000 || count < 1 || count > MAX_CELLS) return null;
  let bytes;
  try { bytes = Buffer.from(bits, 'base64'); } catch (_) { return null; }
  if (bytes.length < Math.ceil(count / 8)) return null;
  const cells = new Uint8Array(count);
  for (let i = 0; i < count; i++) cells[i] = (bytes[i >> 3] >> (i & 7)) & 1;
  return cells;
}

function packBits(cells) {
  const bytes = Buffer.alloc(Math.ceil(cells.length / 8));
  for (let i = 0; i < cells.length; i++) if (cells[i]) bytes[i >> 3] |= 1 << (i & 7);
  return bytes.toString('base64');
}

function finite(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function composePageMask(message) {
  if (!message || message.v !== 1) return null;
  const width = message.width;
  const height = message.height;
  if (!Number.isInteger(width) || !Number.isInteger(height)) return null;
  if (width < 1 || height < 1 || width > MAX_EDGE || height > MAX_EDGE) return null;
  const columns = Math.ceil(width / CELL);
  const rows = Math.ceil(height / CELL);
  if (columns * rows > MAX_CELLS) return null;
  const character = message.character;
  if (!character || !Number.isInteger(character.columns) || !Number.isInteger(character.rows)) return null;
  if (character.columns < 1 || character.rows < 1 || character.columns > 1024 || character.rows > 1024) return null;
  if (!finite(character.x) || !finite(character.y) || !finite(character.width) || !finite(character.height)) return null;
  if (character.width <= 0 || character.height <= 0) return null;
  const source = unpackBits(character.bits, character.columns * character.rows);
  if (!source) return null;
  const rects = Array.isArray(message.rects) ? message.rects : null;
  if (!rects || rects.length > MAX_RECTS) return null;
  const cells = new Uint8Array(columns * rows);
  let occupied = 0;
  const mark = (x, y) => {
    if (x < 0 || y < 0 || x >= columns || y >= rows) return;
    const i = y * columns + x;
    if (!cells[i]) { cells[i] = 1; occupied++; }
  };
  const colW = character.width / character.columns;
  const rowH = character.height / character.rows;
  for (let row = 0; row < character.rows; row++) {
    for (let col = 0; col < character.columns; col++) {
      if (!source[row * character.columns + col]) continue;
      const x0 = character.x + col * colW;
      const y0 = character.y + row * rowH;
      const x1 = x0 + colW;
      const y1 = y0 + rowH;
      const cx0 = Math.floor(x0 / CELL);
      const cy0 = Math.floor(y0 / CELL);
      const cx1 = Math.floor((x1 - 1e-3) / CELL);
      const cy1 = Math.floor((y1 - 1e-3) / CELL);
      for (let y = cy0; y <= cy1; y++) for (let x = cx0; x <= cx1; x++) mark(x, y);
    }
  }
  for (const rect of rects) {
    if (!rect || !finite(rect.x) || !finite(rect.y) || !finite(rect.w) || !finite(rect.h)) return null;
    if (rect.w <= 0 || rect.h <= 0) continue;
    const x0 = Math.floor(rect.x / CELL);
    const y0 = Math.floor(rect.y / CELL);
    const x1 = Math.floor((rect.x + rect.w - 1e-3) / CELL);
    const y1 = Math.floor((rect.y + rect.h - 1e-3) / CELL);
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) mark(x, y);
  }
  if (!occupied) return null;
  return {width, height, columns, rows, cells, occupied};
}

// Full-window capture is the loading fallback. Once the page has posted a mask,
// capture again only if a resize goes unanswered for the fallback interval.
function wantsCapture({now, pageMaskAt, maskStale}) {
  if (!pageMaskAt) return true;
  if (!maskStale) return false;
  return now - pageMaskAt >= CAPTURE_FALLBACK_MS;
}

// Gaze still hears movement. Enter/leave of the hit area is immediate; other
// motion is at most 10 Hz and only after the cursor has travelled a few pixels.
function pointerShouldNotify({now, lastAt, movedPx, crossed}) {
  if (crossed) return true;
  if (!(movedPx >= POINTER_MOVE_PX)) return false;
  if (!lastAt) return true;
  return now - lastAt >= POINTER_INTERVAL_MS;
}

module.exports = {
  CELL, ALPHA, CAPTURE_FALLBACK_MS, POINTER_MOVE_PX, POINTER_INTERVAL_MS,
  buildMask, overOpaque, packBits, composePageMask, wantsCapture, pointerShouldNotify,
};
