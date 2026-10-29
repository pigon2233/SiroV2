'use strict';
// Verification harness: the same control/perception/bridge modules as the pet, without the pet.
// Run: electron computer-e2e.js   (env: SIRO_COMPUTER_TOKEN, SIRO_COMPUTER_ORIGIN, optional SIRO_E2E_SHOTS=dir)
// Control starts ENABLED here because the owner asked for hands-on verification; Ctrl+Alt+Shift+Esc stops it.
const {app, desktopCapturer, globalShortcut, screen} = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const {ComputerControl} = require('./computer-control.js');
const {ComputerBridgeClient} = require('./computer-bridge.js');
const {makeObserver} = require('./computer-perception.js');

const STOP_KEY = 'Control+Alt+Shift+Escape';
app.whenReady().then(() => {
  const control = new ComputerControl({getBounds: () => {
    const d = screen.getPrimaryDisplay(), f = d.scaleFactor;
    return {x: 0, y: 0, width: Math.round(d.bounds.width * f), height: Math.round(d.bounds.height * f)};
  }});
  const shots = process.env.SIRO_E2E_SHOTS;
  let n = 0;
  const base = makeObserver({control, screen, desktopCapturer});
  const observe = async () => {
    const result = await base();
    if (shots && result.ok && result.data.image_png_b64) {
      fs.mkdirSync(shots, {recursive: true});
      fs.writeFileSync(path.join(shots, `obs-${String(++n).padStart(3, '0')}.png`), Buffer.from(result.data.image_png_b64, 'base64'));
    }
    return result;
  };
  if (!globalShortcut.register(STOP_KEY, () => { control.stop(); console.log('EMERGENCY STOP'); })) {
    console.log('hotkey registration failed; refusing to enable'); app.quit(); return;
  }
  control.listeners.push(state => console.log('state', state));
  const client = new ComputerBridgeClient({origin: process.env.SIRO_COMPUTER_ORIGIN, token: process.env.SIRO_COMPUTER_TOKEN, control, observe});
  control.enable();
  client.start();
  console.log('e2e ready');
});
app.on('will-quit', () => globalShortcut.unregisterAll());
app.on('window-all-closed', () => {});
