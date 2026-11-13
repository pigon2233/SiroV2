'use strict';
const {app, BrowserWindow, desktopCapturer, globalShortcut, ipcMain, Menu, nativeImage, screen, session, Tray} = require('electron');
const {execFile, spawn} = require('node:child_process');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {ComputerControl} = require('./computer-control.js');
const {ComputerBridgeClient} = require('./computer-bridge.js');
const {makeObserver} = require('./computer-perception.js');
const {computerToken} = require('./computer-config.js');
const {buildMask, overOpaque, composePageMask, wantsCapture, pointerShouldNotify, CAPTURE_FALLBACK_MS} = require('./click-mask.js');
const {petGpuPlan, appendGpuQuery, applyWindowsGpuPreference} = require('./gpu-preference.js');

if (process.env.SIRO_DEBUG_PORT) app.commandLine.appendSwitch('remote-debugging-port', process.env.SIRO_DEBUG_PORT);
// Keep Chromium/Electron per-monitor DPI aware so display.bounds + dipToScreenPoint match Win32 physical pixels.
app.commandLine.appendSwitch('high-dpi-support', '1');
// Draw the pet on the integrated GPU before the GPU process starts. ANGLE stays
// on the Windows D3D11 default; hardware acceleration and window transparency stay on.
const gpuPlan = petGpuPlan(process.env.SIRO_PET_GPU);
for (const flag of gpuPlan.switches) app.commandLine.appendSwitch(flag);

const origin = process.env.SIRO_DESKTOP_ORIGIN || 'http://127.0.0.1:8000';
const permitted = url => { try { return new URL(url).origin === origin; } catch (_) { return false; } };
const STOP_KEY = 'Control+Alt+Shift+Escape';
let control;
let tray, win, center, captureHost, desktopLayout, wander, mask, dragging = false, walk = null, lastCursor = null, scale = 1, chat = false, controlsHeight = 132, layout, dragTimer = 0;
let pageMaskAt = 0, maskStale = true, lastPointerAt = 0, lastHit = null;
/** DIP bounds to restore after computer-control moves SIRO off the game window (still visible). */
let petHome = null;

/** Tiny always-hidden window parked on the game's display so Electron can capture that monitor. */
function ensureCaptureHost() {
  if (captureHost && !captureHost.isDestroyed()) return captureHost;
  captureHost = new BrowserWindow({
    width: 1, height: 1, x: -10000, y: -10000, show: false, frame: false, transparent: true,
    skipTaskbar: true, focusable: false, resizable: false, movable: false,
    webPreferences: {contextIsolation: true, sandbox: true, nodeIntegration: false},
  });
  captureHost.setMenuBarVisibility(false);
  captureHost.hide();
  return captureHost;
}

function applyLayout() {
  if (!win || !desktopLayout) return;
  haltWalk('layout');
  const [x, y] = win.getPosition();
  const area = screen.getDisplayMatching(win.getBounds()).workArea;
  const roleX = x + (layout?.petX || 0), roleBottom = y + (layout?.petHeight || 640);
  const next = desktopLayout(scale, chat, Math.min(4096, area.width), Math.min(4096, area.height), controlsHeight);
  win.setBounds({
    width: next.width, height: next.height,
    x: Math.round(Math.max(area.x, Math.min(roleX - next.petX, area.x + area.width - next.width))),
    y: Math.round(Math.max(area.y, Math.min(roleBottom - next.petHeight, area.y + area.height - next.height))),
  });
  layout = next;
  win.webContents.executeJavaScript(`window.siroDesktopView?.setLayout(${JSON.stringify(next)})`).catch(() => {});
}

function stopDrag() { clearInterval(dragTimer); dragTimer = 0; dragging = false; }
function startDrag(point) {
  stopDrag(); haltWalk('dragged'); dragging = true;
  const [startX, startY] = win.getPosition(), began = Date.now();
  const fromX = point.screenX, fromY = point.screenY;
  // The page reports CSS pixels; the cursor poll uses the same DIP space as the window.
  const origin0 = screen.getCursorScreenPoint();
  dragTimer = setInterval(() => {
    if (!win || Date.now() - began > 20000) { stopDrag(); return; }
    const now = screen.getCursorScreenPoint();
    win.setPosition(Math.round(startX + now.x - origin0.x), Math.round(startY + now.y - origin0.y));
  }, 16);
  void fromX; void fromY;
}

// ---- Walking: the window travels on the same speed curve as her steps, inside the work area.
const clock = () => performance.now() / 1000;
const toPage = (name, payload) => win?.webContents.executeJavaScript(`window.siroDesktopView?.${name}(${payload})`).catch(() => {});
const walkReport = update => toPage('walkUpdate', JSON.stringify(update));
function startWalk(message) {
  haltWalk('replaced');
  if (chat || !layout) return walkReport({id: message.id, state: 'refused', reason: chat ? 'chat' : 'layout'});
  const area = screen.getDisplayMatching(win.getBounds()).workArea, [x, y] = win.getPosition();
  const room = wander.walkRoom(x, layout.petX, layout.petWidth, area, message.direction, message.distance);
  const plan = wander.walkPlan(room.distance, message.speed, message.ramp, message.cycle ?? 0);
  if (!plan) return walkReport({id: message.id, state: 'refused', reason: 'room'});
  walk = {id: message.id, direction: room.direction, startX: x, y, plan, began: clock() + message.delay, stop: null, area};
  walk.timer = setInterval(stepWalk, 16);
  walkReport({id: walk.id, state: 'started', direction: walk.direction, distance: plan.distance, ramp: plan.ramp, cruise: plan.cruise, delay: message.delay});
}
function stepWalk() {
  if (!walk || !win) return;
  const now = clock();
  let offset, done;
  if (walk.stop) { const t = now - walk.stop.since; offset = walk.stop.base + walk.stop.plan.at(t); done = t >= walk.plan.ramp; }
  else { const t = now - walk.began; offset = walk.plan.at(t); done = t >= walk.plan.duration; }
  const {area} = walk;
  let next = walk.startX + walk.direction * offset;
  if (layout) next = Math.max(area.x - layout.petX, Math.min(next, area.x + area.width - layout.petX - layout.petWidth));
  win.setPosition(Math.round(next), walk.y);
  if (done) finishWalk('arrived');
}
function stopWalk(id) {
  if (!walk || walk.id !== id || walk.stop) return;
  const now = clock(), t = now - walk.began;
  if (t <= 0) return haltWalk('cancelled');
  const plan = wander.stopPlan(walk.plan, t);
  walk.stop = {since: now, base: walk.plan.at(t), plan};
  walkReport({id, state: 'stopping', remaining: plan.remaining});
}
function finishWalk(reason) {
  if (!walk) return;
  const id = walk.id;
  clearInterval(walk.timer); walk = null;
  walkReport({id, state: 'ended', reason});
}
function haltWalk(reason) { if (walk) finishWalk(reason); }

// ---- Click-through: transparent pixels pass clicks to whatever is behind her.
// The page posts a downsampled alpha mask (character grid plus opaque controls).
// capturePage is only the loading fallback, and only on a slow interval, so the
// GPU is not read back in full several times a second.
let capturing = false;
async function refreshMask() {
  if (!win || capturing || !win.isVisible()) return;
  const started = Date.now();
  if (!wantsCapture({now: started, pageMaskAt, maskStale})) return;
  capturing = true;
  try {
    const image = await win.webContents.capturePage();
    if (pageMaskAt > started && !maskStale) return;
    mask = buildMask(image);
  } catch (_) { /* keep the last mask */ } finally { capturing = false; }
}
let ignoring = false;
function pollCursor() {
  if (!win || win.isDestroyed()) return;
  const point = screen.getCursorScreenPoint(), bounds = win.getBounds();
  const hit = dragging || overOpaque(mask, point, bounds);
  const wantIgnore = !hit;
  if (wantIgnore !== ignoring) { ignoring = wantIgnore; win.setIgnoreMouseEvents(ignoring); if (process.env.SIRO_DEBUG_LOG) console.log('ignore', ignoring, point.x, point.y, JSON.stringify(bounds), mask && mask.occupied); }
  const rx = point.x - bounds.x, ry = point.y - bounds.y;
  const movedPx = lastCursor ? Math.hypot(rx - lastCursor[0], ry - lastCursor[1]) : Infinity;
  const crossed = lastHit !== null && lastHit !== hit;
  const now = Date.now();
  if (pointerShouldNotify({now, lastAt: lastPointerAt, movedPx, crossed})) {
    lastCursor = [rx, ry]; lastPointerAt = now; toPage('pointerUpdate', `${rx}, ${ry}`);
  }
  lastHit = hit;
}

// ---- Tray icon: she has no taskbar button, so show/hide, console and quit live here.
function showPet() { if (win.isMinimized()) win.restore(); win.showInactive(); }
function setupTray() {
  tray = new Tray(nativeImage.createFromPath(path.join(__dirname, 'tray.png')));
  const toggle = () => { if (win.isVisible() && !win.isMinimized()) { haltWalk('hidden'); win.hide(); } else showPet(); };
  tray.on('click', toggle);
  const menu = () => Menu.buildFromTemplate([
    {label: '顯示／隱藏桌寵', click: toggle},
    {label: '開啟控制台', click: () => openCenter()},
    {type: 'separator'},
    {label: control.stopped ? `電腦操控：已緊急停止（點此重新啟用，${STOP_KEY} 停止）` : control.enabled ? `電腦操控：開啟中（${STOP_KEY} 緊急停止）` : '電腦操控：關閉（點此開啟）',
      click: () => (control.active ? control.disable() : enableControl())},
    {type: 'separator'},
    {label: '結束桌寵（SIRO 服務繼續）', click: () => app.quit()},
    {label: '結束 SIRO（連同服務）', click: () => {
      spawn('wsl.exe', ['-d', 'Ubuntu', '--', 'bash', '-lc', '~/.local/bin/siro-stop'], {stdio: 'ignore', windowsHide: true, detached: true}).unref();
      app.quit();
    }},
  ]);
  const refresh = () => { tray.setToolTip(control.active ? 'SIRO 桌寵 · 電腦操控開啟' : 'SIRO 桌寵'); tray.setContextMenu(menu()); };
  control.listeners.push(refresh); refresh();
}

function rememberPetHome(bounds) {
  if (!petHome && bounds && Number.isFinite(bounds.x) && Number.isFinite(bounds.y)) petHome = {...bounds};
}

function restorePetHome() {
  if (!petHome || !win || win.isDestroyed()) { petHome = null; return; }
  try { win.setBounds(petHome); } catch (_) { /* keep her wherever she is */ }
  petHome = null;
}

// Owner-only switch. Refuses to enable when the emergency-stop hotkey cannot be registered.
// Keep the pet visible; capture uses a separate hidden helper window on the game's display.
// Observe may slide her off the game HWND (still on-screen) so she is not in the screenshot.
function enableControl() {
  if (!globalShortcut.isRegistered(STOP_KEY) && !globalShortcut.register(STOP_KEY, () => control.stop())) return;
  haltWalk('control');
  ensureCaptureHost();
  control.enable();
}

function openCenter(page) {
  // #/activity is the monitor page's activity section. The console shows chat otherwise.
  const hash = page === 'activity' ? '#/activity' : '';
  if (!center || center.isDestroyed()) {
    center = new BrowserWindow({width: 1080, height: 760, title: 'SIRO · 控制台'});
    center.removeMenu();
  }
  center.loadURL(`${origin}/?view=control${hash}`);
  center.show(); center.focus();
}

function handle(message) {
  switch (message.type) {
    case 'desktop.quit': app.quit(); break;
    case 'desktop.hide': haltWalk('hidden'); win.hide(); break; // the tray icon brings her back
    case 'desktop.console': openCenter(message.page); break;
    case 'desktop.chat':
      if (typeof message.open !== 'boolean') break;
      chat = message.open; win.setFocusable(chat); applyLayout();
      if (chat) win.focus();
      break;
    case 'desktop.scale':
      if (![-1, 0, 1].includes(message.step)) break;
      scale = message.step === 0 ? 1 : Math.max(.6, Math.min(1.5, Math.round((scale + message.step * .1) * 10) / 10));
      applyLayout();
      break;
    case 'desktop.controls':
      if (Number.isInteger(message.height) && message.height >= 64 && message.height <= 320 && message.height !== controlsHeight) { controlsHeight = message.height; applyLayout(); }
      break;
    case 'desktop.move':
      if (message.button === 1 && Number.isFinite(message.screenX) && Number.isFinite(message.screenY)) startDrag(message);
      break;
    case 'desktop.ready': applyLayout(); break;
    case 'desktop.mask': {
      const next = composePageMask(message);
      if (!next) break;
      mask = next; pageMaskAt = Date.now(); maskStale = false;
      break;
    }
    case 'desktop.walk':
      if (typeof message.id === 'string' && message.id.length <= 40 && [-1, 0, 1].includes(message.direction) &&
          [message.distance, message.speed, message.ramp, message.delay].every(Number.isFinite) &&
          message.distance > 0 && message.distance <= 4096 && message.speed >= 10 && message.speed <= 2000 &&
          message.ramp >= .2 && message.ramp <= 5 && message.delay >= 0 && message.delay <= 5 &&
          (message.cycle === undefined || (Number.isFinite(message.cycle) && message.cycle >= 0 && message.cycle <= 5))) startWalk(message);
      break;
    case 'desktop.walk.stop': if (typeof message.id === 'string') stopWalk(message.id); break;
    default: break;
  }
}

function installDesktopGpuQuery(ses) {
  if (!gpuPlan.powerPreference) return;
  const urls = [`${origin}/vrm/*`, `${origin}/vrm/?*`];
  ses.webRequest.onBeforeRequest({urls}, (details, callback) => {
    try {
      const next = appendGpuQuery(details.url, gpuPlan.powerPreference);
      callback(next === details.url ? {} : {redirectURL: next});
    } catch (_) { callback({}); }
  });
}

app.whenReady().then(async () => {
  installDesktopGpuQuery(session.defaultSession);
  applyWindowsGpuPreference({
    platform: process.platform, envValue: process.env.SIRO_PET_GPU, exePath: process.execPath, execFile,
  });
  ({desktopLayout} = await import(pathToFileURL(path.join(__dirname, '..', 'desktop', 'layout.mjs')).href));
  wander = await import(pathToFileURL(path.join(__dirname, '..', 'desktop', 'wander.mjs')).href);
  session.defaultSession.setPermissionRequestHandler((contents, permission, callback, details) => {
    callback(permission === 'media' && permitted(details.requestingUrl || contents.getURL()) && !(details.mediaTypes || []).includes('video'));
  });
  win = new BrowserWindow({
    width: 360, height: 640, frame: false, transparent: true, hasShadow: false, resizable: false,
    alwaysOnTop: true, skipTaskbar: true, show: false, focusable: false, title: 'SIRO 桌寵',
    webPreferences: {preload: path.join(__dirname, 'preload.js'), contextIsolation: true, sandbox: true, nodeIntegrationInSubFrames: true},
  });
  win.setAlwaysOnTop(true, 'screen-saver');
  win.setVisibleOnAllWorkspaces(true);
  win.webContents.setWindowOpenHandler(() => ({action: 'deny'}));
  win.webContents.on('will-navigate', event => { if (!permitted(event.url)) event.preventDefault(); });
  ipcMain.on('siro.desktop', (event, text) => {
    if (event.sender !== win.webContents || typeof text !== 'string' || text.length > 400000 || !permitted(event.senderFrame?.url || '')) return;
    let message; try { message = JSON.parse(text); } catch (_) { return; }
    if (message && typeof message.type === 'string') handle(message);
  });
  ipcMain.on('siro.drag.end', stopDrag);
  // Size the window as soon as the page is up: the renderer's ready message can come late or be
  // missed, and until then the 640 px window crops the controls under her.
  win.webContents.on('did-finish-load', () => { applyLayout(); refreshMask(); });
  win.on('resize', () => { maskStale = true; });
  win.on('closed', () => app.quit());
  // Keep her on top even after a full-screen app or the taskbar takes the top slot.
  win.on('blur', () => win.setAlwaysOnTop(true, 'screen-saver'));
  win.once('ready-to-show', () => {
    const area = screen.getPrimaryDisplay().workArea;
    win.setPosition(area.x + area.width - 390, area.y + area.height - 670);
    win.showInactive();
  });
  control = new ComputerControl({getBounds: () => {
    const {physicalBounds} = require('./computer-perception.js');
    const b = physicalBounds(screen, screen.getPrimaryDisplay());
    return {x: b.x, y: b.y, width: b.width, height: b.height};
  }});
  control.listeners.push(state => {
    if (state === 'disabled' || state === 'stopped') restorePetHome();
  });
  setupTray();
  ensureCaptureHost();
  // Backend link: only active with SIRO_COMPUTER_TOKEN; polls solely while control is enabled.
  new ComputerBridgeClient({
    origin, token: computerToken(), control,
    // Helper parked on the game's display for Electron capture. Visible pet is slid off the
    // game HWND during observe (still shown) so she is not painted over menu buttons.
    observe: makeObserver({
      control, screen, desktopCapturer,
      hostWindow: () => ensureCaptureHost(),
      petWindow: () => win,
      onPetCleared: rememberPetHome,
    }),
  }).start();
  // Dedicated pet page. The console opens only from the tray or desktop.console.
  win.loadURL(`${origin}/desktop`);
  setInterval(pollCursor, 50);
  setInterval(() => { if (wantsCapture({now: Date.now(), pageMaskAt, maskStale})) refreshMask(); }, CAPTURE_FALLBACK_MS);
});
app.on('will-quit', () => {
  if (control) control.disable();
  globalShortcut.unregisterAll();
  if (captureHost && !captureHost.isDestroyed()) captureHost.destroy();
});
app.on('window-all-closed', () => app.quit());
