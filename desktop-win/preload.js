'use strict';
// Gives the page the same native bridge the GTK host exposes, and reports where a drag ends.
const {contextBridge, ipcRenderer} = require('electron');
contextBridge.exposeInMainWorld('webkit', {
  messageHandlers: {siroDesktop: {postMessage: text => ipcRenderer.send('siro.desktop', String(text))}},
});
// Transparent in every frame, like the GTK host's injected user stylesheet.
document.addEventListener('DOMContentLoaded', () => {
  const style = document.createElement('style');
  style.textContent = ':root{color-scheme:light!important;}html,body{background:transparent!important;}';
  document.documentElement.appendChild(style);
}, {once: true});
const endDrag = () => ipcRenderer.send('siro.drag.end');
const watch = target => {
  for (const name of ['pointerup', 'pointercancel']) target.addEventListener(name, endDrag, true);
};
window.addEventListener('DOMContentLoaded', () => {
  watch(window);
  const attach = () => { try { const doc = document.querySelector('#companion')?.contentDocument; if (doc) watch(doc); } catch (_) { /* cross-origin */ } };
  document.querySelector('#companion')?.addEventListener('load', attach);
  attach();
});
