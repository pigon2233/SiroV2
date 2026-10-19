// Node-side probe of a moc3 using the real Live2D Cubism Core (licensed SDK, read in place, not copied).
// Usage: node core-probe.cjs <model3.json> [ParamId=value ...]
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SDK = process.env.CUBISM_SDK ||
  '/home/jasonliao/文件/Siro/SiroV2/models/live2d-sdk-5-r.5/CubismSdkForWeb-5-r.5';

function loadCore() {
  const src = fs.readFileSync(path.join(SDK, 'Core/live2dcubismcore.js'), 'utf8');
  const ctx = { console, setTimeout, clearTimeout, WebAssembly, TextDecoder, TextEncoder, Uint8Array, performance, atob, btoa };
  // No window/document/process: Emscripten then takes its plain "shell" path, which works with embedded wasm.
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(src + '\n;globalThis.Live2DCubismCore = Live2DCubismCore;', ctx, { filename: 'live2dcubismcore.js' });
  return ctx.Live2DCubismCore;
}

function toArrayBuffer(buf) {
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
}

function bbox(pos) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < pos.length; i += 2) {
    x0 = Math.min(x0, pos[i]); x1 = Math.max(x1, pos[i]);
    y0 = Math.min(y0, pos[i + 1]); y1 = Math.max(y1, pos[i + 1]);
  }
  return [x0, y0, x1, y1];
}

async function probe(model3Path, overrides) {
  const Core = loadCore();
  // Emscripten runtime may need a tick to initialise.
  for (let i = 0; i < 100 && !(Core.Moc && Core.Version && safe(() => Core.Version.csmGetVersion())); i++) {
    await new Promise(r => setTimeout(r, 20));
  }
  const dir = path.dirname(model3Path);
  const setting = JSON.parse(fs.readFileSync(model3Path, 'utf8'));
  const mocBytes = toArrayBuffer(fs.readFileSync(path.join(dir, setting.FileReferences.Moc)));
  const out = {};
  out.coreVersion = Core.Version.csmGetVersion();
  out.latestMocVersion = Core.Version.csmGetLatestMocVersion();
  out.mocVersion = Core.Version.csmGetMocVersion(mocBytes);
  out.mocConsistency = !!Core.Moc.prototype.hasMocConsistency.call(null, mocBytes);
  const moc = Core.Moc.fromArrayBuffer(mocBytes);
  if (!moc) throw new Error('Core.Moc.fromArrayBuffer failed');
  const model = Core.Model.fromMoc(moc);
  out.canvas = { size: Array.from(model.canvasinfo.CanvasWidth != null ? [model.canvasinfo.CanvasWidth, model.canvasinfo.CanvasHeight] : []),
    origin: [model.canvasinfo.CanvasOriginX, model.canvasinfo.CanvasOriginY], ppu: model.canvasinfo.PixelsPerUnit };
  const P = model.parameters;
  out.parameters = [];
  for (let i = 0; i < P.count; i++) {
    out.parameters.push({ id: P.ids[i], min: P.minimumValues[i], max: P.maximumValues[i], def: P.defaultValues[i], keys: P.keyCounts ? P.keyCounts[i] : undefined });
  }
  out.parts = [];
  for (let i = 0; i < model.parts.count; i++) out.parts.push({ id: model.parts.ids[i], opacity: model.parts.opacities[i], parent: model.parts.parentIndices[i] });
  for (const [id, v] of Object.entries(overrides)) {
    const idx = Array.from(P.ids).indexOf(id);
    if (idx < 0) throw new Error('no parameter ' + id);
    P.values[idx] = v;
  }
  model.update();
  const D = model.drawables;
  const renderOrders = model.getRenderOrders();
  out.renderOrdersRaw = Array.from(renderOrders);
  out.offscreenCount = model.offscreens ? model.offscreens.count : 0;
  out.drawables = [];
  for (let i = 0; i < D.count; i++) {
    out.drawables.push({
      id: D.ids[i], texture: D.textureIndices[i], drawOrder: D.drawOrders[i], renderOrder: renderOrders[i],
      opacity: D.opacities[i], constantFlags: D.constantFlags[i], dynamicFlags: D.dynamicFlags[i],
      blendMode: D.blendModes ? D.blendModes[i] : undefined,
      visible: Core.Utils.hasIsVisibleBit(D.dynamicFlags[i]),
      vertexCount: D.vertexCounts[i], indexCount: D.indexCounts[i], maskCount: D.maskCounts[i],
      parentPart: D.parentPartIndices[i],
      bbox: bbox(D.vertexPositions[i]), uvBbox: bbox(D.vertexUvs[i]),
      positions: Array.from(D.vertexPositions[i]), uvs: Array.from(D.vertexUvs[i]), indices: Array.from(D.indices[i]),
      multiplyColor: Array.from(D.multiplyColors.slice(i * 4, i * 4 + 4)), screenColor: Array.from(D.screenColors.slice(i * 4, i * 4 + 4))
    });
  }
  model.release(); moc._release && moc._release();
  return out;
}
function safe(f) { try { return f(); } catch { return undefined; } }

module.exports = { probe, loadCore };

if (require.main === module) {
  const [model3, ...rest] = process.argv.slice(2);
  const ov = Object.fromEntries(rest.map(a => { const [k, v] = a.split('='); return [k, Number(v)]; }));
  process.on('uncaughtException', e => { console.error('uncaught:', String(e && e.stack || e).slice(0, 800)); process.exit(1); });
  Promise.resolve().then(() => probe(model3, ov)).then(r => {
    for (const d of r.drawables) { delete d.positions; delete d.uvs; delete d.indices; }
    console.log(JSON.stringify(r, null, 1));
  }).catch(e => { console.error('error:', e && e.name, String(e && e.message || e).slice(0, 400)); process.exit(1); });
}
