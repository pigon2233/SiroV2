'use strict';
// Read-only screen perception for the backend decision loop: foreground window + a downscaled
// screenshot of the primary display + a coarse fingerprint. Nothing is written to disk.
const crypto = require('node:crypto');

const MAX_WIDTH = 1280;

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
      focus_is_secret: win.data.secret === true, fingerprint: '', image_png_b64: null, image_size: null,
    };
    if (report.focus_is_secret) return {ok: true, data: report}; // never capture while a password field has focus
    const width = Math.min(MAX_WIDTH, pw), height = Math.round(width * ph / pw);
    const sources = await desktopCapturer.getSources({types: ['screen'], thumbnailSize: {width, height}});
    const source = sources.find(s => String(s.display_id) === String(display.id)) || sources[0];
    if (!source || source.thumbnail.isEmpty()) return {ok: false, error: 'capture_failed'};
    const size = source.thumbnail.getSize();
    report.image_png_b64 = source.thumbnail.toPNG().toString('base64');
    report.image_size = [size.width, size.height];
    report.fingerprint = fingerprint(source.thumbnail);
    return {ok: true, data: report};
  };
}

module.exports = {makeObserver, fingerprint};
