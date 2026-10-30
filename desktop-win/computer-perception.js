'use strict';
// Read-only screen perception for the backend decision loop: foreground window + a downscaled
// screenshot of the primary display + a coarse fingerprint. Nothing is written to disk.
const crypto = require('node:crypto');

const MAX_WIDTH = 1280;

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

function makeObserver({control, screen, desktopCapturer}) {
  return async function observe() {
    const win = await control.queryWindow();
    if (!win.ok) return {ok: false, error: win.error};
    const display = screen.getPrimaryDisplay(), f = display.scaleFactor;
    const pw = Math.round(display.bounds.width * f), ph = Math.round(display.bounds.height * f);
    const report = {
      title: win.data.title, process: win.data.process, rect: win.data.rect, screen: [pw, ph],
      window_id: win.data.window_id, pid: win.data.pid,
      focus_is_secret: win.data.secret === true, fingerprint: '', image_png_b64: null, image_size: null, image_rect: null,
    };
    if (report.focus_is_secret) return {ok: true, data: report}; // never capture while a password field has focus
    // Only the foreground window is captured and sent, never the rest of the desktop.
    const [wl, wt, ww, wh] = win.data.rect;
    const x = Math.max(0, wl), y = Math.max(0, wt);
    const cw = Math.min(pw, wl + ww) - x, ch = Math.min(ph, wt + wh) - y;
    if (cw < 32 || ch < 32) return {ok: false, error: 'window_not_visible'};
    const sources = await desktopCapturer.getSources({types: ['screen'], thumbnailSize: {width: pw, height: ph}});
    const after = await control.queryWindow();
    if (!after.ok || !sameWindow(win.data, after.data) || after.data.secret || after.data.title !== win.data.title)
      return {ok: false, error: 'window_changed_during_capture'};
    const source = sources.find(s => String(s.display_id) === String(display.id)) || sources[0];
    if (!source || source.thumbnail.isEmpty()) return {ok: false, error: 'capture_failed'};
    let image = source.thumbnail.crop({x, y, width: cw, height: ch});
    if (cw > MAX_WIDTH) image = image.resize({width: MAX_WIDTH, height: Math.round(ch * MAX_WIDTH / cw), quality: 'good'});
    const size = image.getSize();
    report.image_png_b64 = image.toPNG().toString('base64');
    report.image_size = [size.width, size.height];
    report.image_rect = [x, y, cw, ch];
    report.fingerprint = fingerprint(image);
    return {ok: true, data: report};
  };
}

module.exports = {makeObserver, fingerprint, sameWindow};
