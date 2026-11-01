'use strict';
// Read-only screen perception for the backend decision loop: foreground window + a downscaled
// screenshot of the display that contains that window + a coarse fingerprint. Nothing is written to disk.
const crypto = require('node:crypto');

const MAX_WIDTH = 512;

function sameWindow(a, b) {
  return !!a && !!b && typeof a.window_id === 'string' && /^\d+$/.test(a.window_id) &&
    a.window_id !== '0' && Number.isInteger(a.pid) && a.pid > 0 && a.window_id === b.window_id &&
    a.pid === b.pid && Array.isArray(a.rect) && a.rect.length === 4 && a.rect.every(Number.isInteger) &&
    Array.isArray(b.rect) && a.rect.every((v, i) => v === b.rect[i]) && b.rect.length === 4;
}

// Coarse 32x18 luminance hash: equal fingerprints mean "no visible change" for stuck detection.
function fingerprint(image) {
  const small = image.resize({width: 32, height: 18, quality: 'good'}).toBitmap();
  const levels = Buffer.alloc(small.length / 4);
  for (let i = 0; i < levels.length; i++) {
    const b = small[i * 4], g = small[i * 4 + 1], r = small[i * 4 + 2];
    levels[i] = Math.round(0.299 * r + 0.587 * g + 0.114 * b) >> 5;
  }
  return crypto.createHash('sha1').update(levels).digest('hex').slice(0, 16);
}

function physicalBounds(display) {
  const f = display.scaleFactor || 1;
  const b = display.bounds;
  return {
    x: Math.round(b.x * f),
    y: Math.round(b.y * f),
    width: Math.round(b.width * f),
    height: Math.round(b.height * f),
    scaleFactor: f,
    id: display.id,
  };
}

/** Pick the display that contains the window center (supports secondary monitors + mixed DPI). */
function displayForWindow(screen, rect) {
  const [wl, wt, ww, wh] = rect;
  const cx = wl + Math.floor(ww / 2), cy = wt + Math.floor(wh / 2);
  const displays = screen.getAllDisplays();
  for (const display of displays) {
    const b = physicalBounds(display);
    if (cx >= b.x && cy >= b.y && cx < b.x + b.width && cy < b.y + b.height) return display;
  }
  // Nearest display center in physical pixels (do not assume primary DPI).
  let best = null, bestDist = Infinity;
  for (const display of displays) {
    const b = physicalBounds(display);
    const dx = cx - (b.x + b.width / 2), dy = cy - (b.y + b.height / 2);
    const dist = dx * dx + dy * dy;
    if (dist < bestDist) {
      bestDist = dist;
      best = display;
    }
  }
  return best || screen.getPrimaryDisplay();
}

/**
 * Resolve the capturer source for a display. Never silently use another monitor's frame —
 * that is what makes a secondary-monitor game look like "empty primary".
 */
function sourceForDisplay(sources, display, bounds) {
  if (!Array.isArray(sources) || sources.length === 0) return null;
  const byId = sources.find(s => String(s.display_id) === String(display.id));
  if (byId && !byId.thumbnail.isEmpty()) return byId;
  // Some Electron/Windows builds leave display_id blank. Only then match by size —
  // never reuse a source that is explicitly labeled as a different display (same
  // resolution dual-monitor setups would otherwise crop the primary by mistake).
  const unlabeled = sources.filter(s => {
    if (!s || s.thumbnail.isEmpty()) return false;
    const id = s.display_id;
    if (id !== undefined && id !== null && String(id) !== '') return false;
    const size = s.thumbnail.getSize();
    return Math.abs(size.width - bounds.width) <= 2 && Math.abs(size.height - bounds.height) <= 2;
  });
  if (unlabeled.length === 1) return unlabeled[0];
  return null;
}

function makeObserver({control, screen, desktopCapturer}) {
  return async function observe() {
    const win = await control.queryWindow();
    if (!win.ok) return {ok: false, error: win.error};
    const display = displayForWindow(screen, win.data.rect);
    const bounds = physicalBounds(display);
    const pw = bounds.width, ph = bounds.height;
    const report = {
      title: win.data.title, process: win.data.process, rect: win.data.rect, screen: [pw, ph],
      window_id: win.data.window_id, pid: win.data.pid,
      focus_is_secret: win.data.secret === true, fingerprint: '', image_png_b64: null, image_size: null, image_rect: null,
    };
    if (report.focus_is_secret) return {ok: true, data: report}; // never capture while a password field has focus
    // Only the foreground window is captured and sent, never the rest of the desktop.
    const [wl, wt, ww, wh] = win.data.rect;
    const x = Math.max(0, wl - bounds.x), y = Math.max(0, wt - bounds.y);
    const right = Math.min(bounds.x + pw, wl + ww), bottom = Math.min(bounds.y + ph, wt + wh);
    const cw = right - (bounds.x + x), ch = bottom - (bounds.y + y);
    if (cw < 32 || ch < 32) return {ok: false, error: 'window_not_visible'};
    const sources = await desktopCapturer.getSources({types: ['screen'], thumbnailSize: {width: pw, height: ph}});
    const after = await control.queryWindow();
    if (!after.ok || !sameWindow(win.data, after.data) || after.data.secret || after.data.title !== win.data.title)
      return {ok: false, error: 'window_changed_during_capture'};
    const source = sourceForDisplay(sources, display, bounds);
    if (!source) return {ok: false, error: 'capture_wrong_display'};
    if (source.thumbnail.isEmpty()) return {ok: false, error: 'capture_failed'};
    const thumb = source.thumbnail.getSize();
    // Thumbnail must cover the display we intended; otherwise crop would sample the wrong monitor.
    if (thumb.width < pw - 2 || thumb.height < ph - 2) return {ok: false, error: 'capture_wrong_display'};
    // Thumbnail is the chosen display; crop in that display's pixel space.
    let image = source.thumbnail.crop({x, y, width: cw, height: ch});
    if (cw > MAX_WIDTH) image = image.resize({width: MAX_WIDTH, height: Math.round(ch * MAX_WIDTH / cw), quality: 'good'});
    const size = image.getSize();
    // JPEG is much smaller/faster for local vision than PNG; field name kept for API compat.
    report.image_png_b64 = image.toJPEG(72).toString('base64');
    report.image_size = [size.width, size.height];
    report.image_rect = [bounds.x + x, bounds.y + y, cw, ch];
    report.fingerprint = fingerprint(image);
    return {ok: true, data: report};
  };
}

module.exports = {makeObserver, fingerprint, sameWindow, displayForWindow, physicalBounds, sourceForDisplay};
