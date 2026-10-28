'use strict';
const {app, BrowserWindow, ipcMain, Menu, nativeImage, screen, session, Tray} = require('electron');
const {spawn} = require('node:child_process');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

if (process.env.SIRO_DEBUG_PORT) app.commandLine.appendSwitch('remote-debugging-port', process.env.SIRO_DEBUG_PORT);
const origin = process.env.SIRO_DESKTOP_ORIGIN || 'http://127.0.0.1:8000';
const permitted = url => { try { return new URL(url).origin === origin; } catch (_) { return false; } };
let tray, win, center, desktopLayout, wander, mask, dragging = false, walk = null, lastCursor = null, scale = 1, chat = false, controlsHeight = 132, layout, dragTimer = 0;

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
  }, 8);
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

// ---- Click-through: transparent pixels pass clicks to whatever is behind her. A snapshot of the
// page gives an opaque-cell mask; the cursor poll flips mouse capture on only over those cells.
const CELL = 4;
function buildMask(image) {
  const {width, height} = image.getSize(), bitmap = image.toBitmap();
  const columns = Math.ceil(width / CELL), rows = Math.ceil(height / CELL), cells = new Uint8Array(columns * rows);
  let occupied = 0;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    if (bitmap[(y * width + x) * 4 + 3] > 16) { const i = Math.floor(y / CELL) * columns + Math.floor(x / CELL); if (!cells[i]) { cells[i] = 1; occupied++; } }
  }
  return {width, height, columns, rows, cells, occupied};
}
let capturing = false;
async function refreshMask() {
  if (!win || capturing || !win.isVisible()) return;
  capturing = true;
  try { mask = buildMask(await win.webContents.capturePage()); } catch (_) { /* keep the last mask */ } finally { capturing = false; }
}
function overOpaque(point, bounds) {
  if (!mask || mask.occupied === 0) return point.y - bounds.y < 48; // rescue strip while the page loads
  const px = (point.x - bounds.x) * mask.width / bounds.width, py = (point.y - bounds.y) * mask.height / bounds.height;
  if (px < 0 || py < 0 || px >= mask.width || py >= mask.height) return false;
  const cx = Math.floor(px / CELL), cy = Math.floor(py / CELL);
  for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
    const x = cx + dx, y = cy + dy;
    if (x >= 0 && y >= 0 && x < mask.columns && y < mask.rows && mask.cells[y * mask.columns + x]) return true;
  }
  return false;
}
let ignoring = false;
function pollCursor() {
  if (!win || win.isDestroyed()) return;
  const point = screen.getCursorScreenPoint(), bounds = win.getBounds();
  const wantIgnore = !dragging && !overOpaque(point, bounds);
  if (wantIgnore !== ignoring) { ignoring = wantIgnore; win.setIgnoreMouseEvents(ignoring); if (process.env.SIRO_DEBUG_LOG) console.log('ignore', ignoring, point.x, point.y, JSON.stringify(bounds), mask && mask.occupied); }
  const rx = point.x - bounds.x, ry = point.y - bounds.y;
  if (!lastCursor || Math.hypot(rx - lastCursor[0], ry - lastCursor[1]) >= 4) { lastCursor = [rx, ry]; toPage('pointerUpdate', `${rx}, ${ry}`); }
}

// ---- Tray icon: she has no taskbar button, so show/hide, console and quit live here.
function showPet() { if (win.isMinimized()) win.restore(); win.showInactive(); }
function setupTray() {
  tray = new Tray(nativeImage.createFromPath(path.join(__dirname, 'tray.png')));
  tray.setToolTip('SIRO 桌寵');
  const toggle = () => { if (win.isVisible() && !win.isMinimized()) { haltWalk('hidden'); win.hide(); } else showPet(); };
  tray.on('click', toggle);
  tray.setContextMenu(Menu.buildFromTemplate([
    {label: '顯示／隱藏桌寵', click: toggle},
    {label: '開啟控制台', click: () => openCenter()},
    {type: 'separator'},
    {label: '結束桌寵（SIRO 服務繼續）', click: () => app.quit()},
    {label: '結束 SIRO（連同服務）', click: () => {
      spawn('wsl.exe', ['-d', 'Ubuntu', '--', 'bash', '-lc', '~/.local/bin/siro-stop'], {stdio: 'ignore', windowsHide: true, detached: true}).unref();
      app.quit();
    }},
  ]));
}

function openCenter(page) {
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

app.whenReady().then(async () => {
  ({desktopLayout} = await import(pathToFileURL(path.join(__dirname, '..', 'desktop', 'layout.mjs')).href));
  wander = await import(pathToFileURL(path.join(__dirname, '..', 'desktop', 'wander.mjs')).href);
  session.defaultSession.setPermissionRequestHandler((contents, permission, callback, details) => {
    callback(permission === 'media' && permitted(details.requestingUrl || contents.getURL()) && !(details.mediaTypes || []).includes('video'));
  });
  win = new BrowserWindow({
    width: 360, height: 640, frame: false, transparent: true, hasShadow: false, resizable: false,
    alwaysOnTop: true, skipTaskbar: false, show: false, focusable: false, title: 'SIRO 桌寵',
    webPreferences: {preload: path.join(__dirname, 'preload.js'), contextIsolation: true, sandbox: true, nodeIntegrationInSubFrames: true},
  });
  win.setAlwaysOnTop(true, 'screen-saver');
  win.setVisibleOnAllWorkspaces(true);
  win.webContents.setWindowOpenHandler(() => ({action: 'deny'}));
  win.webContents.on('will-navigate', event => { if (!permitted(event.url)) event.preventDefault(); });
  ipcMain.on('siro.desktop', (event, text) => {
    if (event.sender !== win.webContents || !permitted(event.senderFrame?.url || '')) return;
    let message; try { message = JSON.parse(text); } catch (_) { return; }
    if (message && typeof message.type === 'string') handle(message);
  });
  ipcMain.on('siro.drag.end', stopDrag);
  // Size the window as soon as the page is up: the renderer's ready message can come late or be
  // missed, and until then the 640 px window crops the controls under her.
  win.webContents.on('did-finish-load', applyLayout);
  win.on('closed', () => app.quit());
  // Keep her on top even after a full-screen app or the taskbar takes the top slot.
  win.on('blur', () => win.setAlwaysOnTop(true, 'screen-saver'));
  win.once('ready-to-show', () => {
    const area = screen.getPrimaryDisplay().workArea;
    win.setPosition(area.x + area.width - 390, area.y + area.height - 670);
    win.showInactive();
  });
  setupTray();
  win.loadURL(`${origin}/desktop`);
  setInterval(pollCursor, 50);
  setInterval(refreshMask, 700);
});
app.on('window-all-closed', () => app.quit());
