'use strict';
const {app, BrowserWindow, ipcMain, screen, session} = require('electron');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

if (process.env.SIRO_DEBUG_PORT) app.commandLine.appendSwitch('remote-debugging-port', process.env.SIRO_DEBUG_PORT);
const origin = process.env.SIRO_DESKTOP_ORIGIN || 'http://127.0.0.1:8000';
const permitted = url => { try { return new URL(url).origin === origin; } catch (_) { return false; } };
let win, center, desktopLayout, scale = 1, chat = false, controlsHeight = 132, layout, dragTimer = 0;

function applyLayout() {
  if (!win || !desktopLayout) return;
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

function stopDrag() { clearInterval(dragTimer); dragTimer = 0; }
function startDrag(point) {
  stopDrag();
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
    case 'desktop.hide': win.minimize(); break;
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
    default: break; // walking, shaping and the like come in stage 2
  }
}

app.whenReady().then(async () => {
  ({desktopLayout} = await import(pathToFileURL(path.join(__dirname, '..', 'desktop', 'layout.mjs')).href));
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
  win.on('closed', () => app.quit());
  // Keep her on top even after a full-screen app or the taskbar takes the top slot.
  win.on('blur', () => win.setAlwaysOnTop(true, 'screen-saver'));
  win.once('ready-to-show', () => {
    const area = screen.getPrimaryDisplay().workArea;
    win.setPosition(area.x + area.width - 390, area.y + area.height - 670);
    win.showInactive();
  });
  win.loadURL(`${origin}/desktop`);
});
app.on('window-all-closed', () => app.quit());
