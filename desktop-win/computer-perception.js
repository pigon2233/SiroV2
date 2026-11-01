'use strict';
// Read-only screen perception for the backend decision loop: foreground window + a downscaled
// screenshot of the display that contains that window + a coarse fingerprint. Nothing is written to disk.
const crypto = require('node:crypto');

// Trial starting point for readable UI text; still downscales huge windows for vision latency.
// 960 keeps UI readable for local VLM while cutting image tokens vs 1280 (fewer decide timeouts).
const MAX_WIDTH = 960;

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

/**
 * Convert Electron DIP display.bounds → Win32-style physical pixels.
 * Multiplying bounds by this display's scaleFactor alone is wrong on mixed-DPI
 * multi-monitor layouts (secondary origin drifts). Prefer screen.dipToScreenPoint.
 */
function physicalBounds(screenApi, display) {
  const b = display.bounds;
  const f = display.scaleFactor || 1;
  // Size always comes from this display's own scale. Origin must use dipToScreenPoint:
  // bounds.x * scaleFactor is wrong on mixed-DPI layouts (secondary origin drifts).
  // Do not convert bottom-right via dipToScreenPoint — shared DIP edges can land on
  // the neighboring display and shrink height/width.
  let ox = Math.round(b.x * f), oy = Math.round(b.y * f);
  if (screenApi && typeof screenApi.dipToScreenPoint === 'function') {
    const tl = screenApi.dipToScreenPoint({x: b.x, y: b.y});
    ox = Math.round(tl.x);
    oy = Math.round(tl.y);
  }
  return {
    x: ox,
    y: oy,
    width: Math.max(1, Math.round(b.width * f)),
    height: Math.max(1, Math.round(b.height * f)),
    scaleFactor: f,
    id: display.id,
  };
}

/** Pick the display that contains the window center (supports secondary monitors + mixed DPI). */
function displayForWindow(screenApi, rect) {
  const [wl, wt, ww, wh] = rect;
  const cx = wl + Math.floor(ww / 2), cy = wt + Math.floor(wh / 2);
  const displays = screenApi.getAllDisplays();
  for (const display of displays) {
    const b = physicalBounds(screenApi, display);
    if (cx >= b.x && cy >= b.y && cx < b.x + b.width && cy < b.y + b.height) return display;
  }
  let best = null, bestDist = Infinity;
  for (const display of displays) {
    const b = physicalBounds(screenApi, display);
    const dx = cx - (b.x + b.width / 2), dy = cy - (b.y + b.height / 2);
    const dist = dx * dx + dy * dy;
    if (dist < bestDist) {
      bestDist = dist;
      best = display;
    }
  }
  return best || screenApi.getPrimaryDisplay();
}

/**
 * Resolve the capturer source for a display. Never silently use another monitor's frame.
 */
function sourceForDisplay(sources, display, bounds) {
  if (!Array.isArray(sources) || sources.length === 0) return null;
  const byId = sources.find(s => String(s.display_id) === String(display.id));
  if (byId && !byId.thumbnail.isEmpty()) return byId;
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

/**
 * Park a dedicated always-hidden helper on the game's display before getSources.
 * Do NOT hide the visible pet — clearPetFromGame moves her aside instead.
 */
function parkHostOnDisplay(hostWindow, display) {
  if (!hostWindow || typeof hostWindow.isDestroyed !== 'function' || hostWindow.isDestroyed()) return;
  const b = display.bounds;
  try {
    if (typeof hostWindow.hide === 'function') hostWindow.hide();
    hostWindow.setPosition(Math.round(b.x + 8), Math.round(b.y + 8));
  } catch (_) { /* never block observe on park failures */ }
}

function rectsOverlap(a, b) {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

function windowPhysicalBounds(screenApi, browserWindow) {
  const dip = browserWindow.getBounds();
  if (typeof screenApi.dipToScreenRect === 'function') {
    const r = screenApi.dipToScreenRect(browserWindow, dip);
    return {
      x: Math.round(r.x), y: Math.round(r.y),
      width: Math.max(1, Math.round(r.width)), height: Math.max(1, Math.round(r.height)),
    };
  }
  const tl = screenApi.dipToScreenPoint({x: dip.x, y: dip.y});
  const br = screenApi.dipToScreenPoint({x: dip.x + dip.width, y: dip.y + dip.height});
  return {
    x: Math.round(tl.x), y: Math.round(tl.y),
    width: Math.max(1, Math.round(br.x - tl.x)), height: Math.max(1, Math.round(br.y - tl.y)),
  };
}

/**
 * Keep SIRO visible but outside the game HWND so capture/clicks are not blocked by her body.
 * Returns previous DIP bounds when moved; null when already clear / unavailable.
 */
function clearPetFromGame(petWindow, screenApi, gameRect) {
  if (!petWindow || typeof petWindow.isDestroyed !== 'function' || petWindow.isDestroyed()) return null;
  if (typeof petWindow.isVisible === 'function' && !petWindow.isVisible()) return null;
  const game = {x: gameRect[0], y: gameRect[1], width: gameRect[2], height: gameRect[3]};
  if (game.width < 32 || game.height < 32) return null;
  let petPhys;
  try { petPhys = windowPhysicalBounds(screenApi, petWindow); } catch (_) { return null; }
  if (!rectsOverlap(petPhys, game)) return null;
  const home = petWindow.getBounds();
  const gameDisplay = displayForWindow(screenApi, gameRect);
  for (const d of screenApi.getAllDisplays()) {
    if (d.id === gameDisplay.id) continue;
    const wa = d.workArea;
    const x = Math.round(wa.x + Math.max(0, wa.width - home.width - 16));
    const y = Math.round(wa.y + Math.max(0, wa.height - home.height - 16));
    try {
      petWindow.setPosition(x, y);
      if (typeof petWindow.showInactive === 'function') petWindow.showInactive();
      return home;
    } catch (_) { /* try next display */ }
  }
  const wa = gameDisplay.workArea;
  let gameDip = {x: game.x, y: game.y, width: game.width, height: game.height};
  if (typeof screenApi.screenToDipRect === 'function') {
    try { gameDip = screenApi.screenToDipRect(petWindow, game); } catch (_) { /* keep approx */ }
  }
  const leftRoom = gameDip.x - wa.x;
  const rightRoom = (wa.x + wa.width) - (gameDip.x + gameDip.width);
  let x, y;
  if (rightRoom >= leftRoom && rightRoom >= home.width + 8) {
    x = Math.round(gameDip.x + gameDip.width + 8);
    y = Math.round(Math.min(Math.max(wa.y, gameDip.y), wa.y + wa.height - home.height));
  } else if (leftRoom >= home.width + 8) {
    x = Math.round(gameDip.x - home.width - 8);
    y = Math.round(Math.min(Math.max(wa.y, gameDip.y), wa.y + wa.height - home.height));
  } else {
    x = Math.round(wa.x + 8);
    y = Math.round(wa.y + 8);
  }
  x = Math.max(wa.x, Math.min(x, wa.x + wa.width - home.width));
  y = Math.max(wa.y, Math.min(y, wa.y + wa.height - home.height));
  try {
    petWindow.setPosition(x, y);
    if (typeof petWindow.showInactive === 'function') petWindow.showInactive();
    return home;
  } catch (_) {
    return null;
  }
}

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

function makeObserver({control, screen, desktopCapturer, hostWindow, petWindow, onPetCleared}) {
  return async function observe() {
    const win = await control.queryWindow();
    if (!win.ok) return {ok: false, error: win.error};
    const display = displayForWindow(screen, win.data.rect);
    const bounds = physicalBounds(screen, display);
    const pw = bounds.width, ph = bounds.height;
    const report = {
      title: win.data.title, process: win.data.process, rect: win.data.rect, screen: [pw, ph],
      window_id: win.data.window_id, pid: win.data.pid,
      focus_is_secret: win.data.secret === true, fingerprint: '', image_png_b64: null, image_size: null, image_rect: null,
      display_id: display.id,
      scale_factor: bounds.scaleFactor,
    };
    if (report.focus_is_secret) return {ok: true, data: report};
    const [wl, wt, ww, wh] = win.data.rect;
    const x = Math.max(0, wl - bounds.x), y = Math.max(0, wt - bounds.y);
    const right = Math.min(bounds.x + pw, wl + ww), bottom = Math.min(bounds.y + ph, wt + wh);
    const cw = right - (bounds.x + x), ch = bottom - (bounds.y + y);
    if (cw < 32 || ch < 32) return {ok: false, error: 'window_not_visible'};
    const pet = typeof petWindow === 'function' ? petWindow() : petWindow;
    const home = clearPetFromGame(pet, screen, win.data.rect);
    if (home && typeof onPetCleared === 'function') onPetCleared(home);
    if (home) await delay(60); // let compositor settle so she is not in the crop
    parkHostOnDisplay(typeof hostWindow === 'function' ? hostWindow() : hostWindow, display);
    const sources = await desktopCapturer.getSources({types: ['screen'], thumbnailSize: {width: pw, height: ph}});
    const after = await control.queryWindow();
    if (!after.ok || !sameWindow(win.data, after.data) || after.data.secret || after.data.title !== win.data.title)
      return {ok: false, error: 'window_changed_during_capture'};
    const source = sourceForDisplay(sources, display, bounds);
    if (!source) return {ok: false, error: 'capture_wrong_display'};
    if (source.thumbnail.isEmpty()) return {ok: false, error: 'capture_failed'};
    const thumb = source.thumbnail.getSize();
    if (thumb.width < 32 || thumb.height < 32) return {ok: false, error: 'capture_failed'};
    // Thumbnail pixels may not equal physical pixels (DPI / Electron quirks). Scale the crop.
    const scaleX = thumb.width / pw, scaleY = thumb.height / ph;
    const cx = Math.max(0, Math.min(thumb.width - 1, Math.round(x * scaleX)));
    const cy = Math.max(0, Math.min(thumb.height - 1, Math.round(y * scaleY)));
    const ccw = Math.max(1, Math.min(thumb.width - cx, Math.round(cw * scaleX)));
    const cch = Math.max(1, Math.min(thumb.height - cy, Math.round(ch * scaleY)));
    let image = source.thumbnail.crop({x: cx, y: cy, width: ccw, height: cch});
    if (ccw > MAX_WIDTH) {
      image = image.resize({
        width: MAX_WIDTH,
        height: Math.max(1, Math.round(cch * MAX_WIDTH / ccw)),
        quality: 'good',
      });
    }
    const size = image.getSize();
    report.image_png_b64 = image.toJPEG(72).toString('base64');
    report.image_size = [size.width, size.height];
    // image_rect is always physical desktop pixels (matches SetCursorPos / GetWindowRect).
    report.image_rect = [bounds.x + x, bounds.y + y, cw, ch];
    report.capture_size = [thumb.width, thumb.height];
    report.fingerprint = fingerprint(image);
    return {ok: true, data: report};
  };
}

module.exports = {
  makeObserver, fingerprint, sameWindow, displayForWindow, physicalBounds, sourceForDisplay,
  parkHostOnDisplay, clearPetFromGame, rectsOverlap, windowPhysicalBounds,
};
