// Browser harness: real Cubism Core (window.Live2DCubismCore, loaded by <script>) + real Cubism Framework
// (compiled from the licensed SDK sources by tools/build.cjs) + real WebGL drawing.
// Also contains an independent minimal WebGL drawer that reads Core drawable mesh/UV/indices directly,
// used only as a cross-check of the SDK renderer.

import { CubismFramework, Option, LogLevel } from '@sdk/live2dcubismframework';
import { CubismModelSettingJson } from '@sdk/cubismmodelsettingjson';
import { CubismUserModel } from '@sdk/model/cubismusermodel';
import { CubismMatrix44 } from '@sdk/math/cubismmatrix44';
import { CubismMotion } from '@sdk/motion/cubismmotion';
import { CubismMotionJson } from '@sdk/motion/cubismmotionjson';
import { CubismMoc } from '@sdk/model/cubismmoc';
import { CubismShaderManager_WebGL } from '@sdk/rendering/cubismshader_webgl';
import { InvalidMotionQueueEntryHandleValue } from '@sdk/motion/cubismmotionqueuemanager';

declare const Live2DCubismCore: any;

const logs: string[] = [];
let SCALE = 1.6; // model units -> NDC (a 1.0-unit model canvas fills 80% of the viewport); runner passes it in init

class HarnessModel extends CubismUserModel {
  get motionManager() { return this._motionManager; }
}

let gl: WebGLRenderingContext;
let canvas: HTMLCanvasElement;
let model: HarnessModel | null = null;
let glTexture: WebGLTexture[] = [];
let textureUrls: string[] = [];
let clearColor: [number, number, number, number] = [1, 0, 1, 1];

function mvp(): CubismMatrix44 {
  const m = new CubismMatrix44();
  m.loadIdentity();
  m.scale(SCALE * canvas.height / canvas.width, SCALE);
  return m;
}

async function fetchBuf(url: string): Promise<ArrayBuffer> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
  return r.arrayBuffer();
}

// Same upload path as the SDK sample (LAppTextureManager): HTMLImageElement + UNPACK_PREMULTIPLY_ALPHA_WEBGL,
// with renderer.setIsPremultipliedAlpha(true). premultiply=false is ONLY used as a negative control
// (straight-alpha texels fed into the premultiplied pipeline must be caught by the alpha check).
// Note: an ImageBitmap source would silently ignore UNPACK_PREMULTIPLY_ALPHA_WEBGL.
async function loadTexture(url: string, premultiply = true): Promise<WebGLTexture> {
  const img = new Image();
  await new Promise<void>((res, rej) => { img.onload = () => res(); img.onerror = () => rej(new Error('image load failed ' + url)); img.src = url; });
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, premultiply ? 1 : 0);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.generateMipmap(gl.TEXTURE_2D);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 0);
  gl.bindTexture(gl.TEXTURE_2D, null);
  return tex;
}

function coreModel(): any {
  return model!.getModel().getModel();
}

function snapshotCore() {
  const cm = coreModel();
  const D = cm.drawables;
  const ro = cm.getRenderOrders();
  const out: any[] = [];
  for (let i = 0; i < D.count; i++) {
    const pos = D.vertexPositions[i];
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, sx = 0, sy = 0;
    for (let k = 0; k < pos.length; k += 2) {
      x0 = Math.min(x0, pos[k]); x1 = Math.max(x1, pos[k]); y0 = Math.min(y0, pos[k + 1]); y1 = Math.max(y1, pos[k + 1]);
      sx += pos[k]; sy += pos[k + 1];
    }
    out.push({
      index: i, id: D.ids[i], texture: D.textureIndices[i], drawOrder: D.drawOrders[i], renderOrder: ro[i],
      opacity: D.opacities[i], blendMode: D.blendModes ? D.blendModes[i] : null, constantFlags: D.constantFlags[i],
      visible: Live2DCubismCore.Utils.hasIsVisibleBit(D.dynamicFlags[i]), maskCount: D.maskCounts[i],
      vertexCount: D.vertexCounts[i], indexCount: D.indexCounts[i],
      bbox: [x0, y0, x1, y1], meanVertex: [sx / (pos.length / 2), sy / (pos.length / 2)],
      positions: Array.from(pos), uvs: Array.from(D.vertexUvs[i] as Float32Array), indices: Array.from(D.indices[i] as Uint16Array)
    });
  }
  return out;
}

function paramsSnapshot(): Record<string, number> {
  const m = model!.getModel();
  const res: Record<string, number> = {};
  const cm = coreModel();
  for (let i = 0; i < m.getParameterCount(); i++) res[cm.parameters.ids[i]] = m.getParameterValueByIndex(i);
  return res;
}

function resetToDefaults() {
  const m = model!.getModel();
  const cm = coreModel();
  for (let i = 0; i < cm.parameters.count; i++) m.setParameterValueByIndex(i, cm.parameters.defaultValues[i]);
  for (let i = 0; i < cm.parts.count; i++) m.setPartOpacityByIndex(i, 1);
}

function clear() {
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.clearColor(...clearColor);
  gl.clear(gl.COLOR_BUFFER_BIT);
}

function drawSdk() {
  clear();
  const r = model!.getRenderer();
  r.setMvpMatrix(mvp());
  r.setRenderState(null, [0, 0, canvas.width, canvas.height]);
  r.drawModel(SHADER_PATH);
  gl.finish();
}

// ---------- independent minimal drawer (cross-check only) ----------
let rawProg: WebGLProgram | null = null;
function rawProgram(): WebGLProgram {
  if (rawProg) return rawProg;
  const vs = `attribute vec2 p; attribute vec2 uv; uniform mat4 m; varying vec2 v;
    void main(){ gl_Position = m * vec4(p,0.0,1.0); v = vec2(uv.x, 1.0 - uv.y); }`;
  const fs = `precision mediump float; varying vec2 v; uniform sampler2D t; uniform float o;
    void main(){ gl_FragColor = texture2D(t, v) * o; }`;
  const mk = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || 'shader'); return s; };
  const p = gl.createProgram()!;
  gl.attachShader(p, mk(gl.VERTEX_SHADER, vs)); gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error('link');
  rawProg = p; return p;
}
function drawRaw(reverseOrder = false, onlyIds: string[] | null = null) {
  clear();
  const p = rawProgram();
  gl.useProgram(p);
  gl.disable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE); gl.disable(gl.SCISSOR_TEST); gl.disable(gl.STENCIL_TEST);
  gl.enable(gl.BLEND); gl.blendFuncSeparate(gl.ONE, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  gl.uniformMatrix4fv(gl.getUniformLocation(p, 'm'), false, mvp().getArray());
  const cm = coreModel();
  const D = cm.drawables;
  const ro = cm.getRenderOrders();
  const order = Array.from({ length: D.count }, (_, i) => i).sort((a, b) => reverseOrder ? ro[b] - ro[a] : ro[a] - ro[b]);
  const pb = gl.createBuffer(), ub = gl.createBuffer(), ib = gl.createBuffer();
  const lp = gl.getAttribLocation(p, 'p'), lu = gl.getAttribLocation(p, 'uv');
  for (const i of order) {
    if (!Live2DCubismCore.Utils.hasIsVisibleBit(D.dynamicFlags[i]) || D.opacities[i] <= 0) continue;
    if (onlyIds && !onlyIds.includes(D.ids[i])) continue;
    gl.bindBuffer(gl.ARRAY_BUFFER, pb); gl.bufferData(gl.ARRAY_BUFFER, D.vertexPositions[i], gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(lp); gl.vertexAttribPointer(lp, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, ub); gl.bufferData(gl.ARRAY_BUFFER, D.vertexUvs[i], gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(lu); gl.vertexAttribPointer(lu, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, D.indices[i], gl.DYNAMIC_DRAW);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, glTexture[D.textureIndices[i]]);
    gl.uniform1i(gl.getUniformLocation(p, 't'), 0); gl.uniform1f(gl.getUniformLocation(p, 'o'), D.opacities[i]);
    gl.drawElements(gl.TRIANGLES, D.indexCounts[i], gl.UNSIGNED_SHORT, 0);
  }
  gl.deleteBuffer(pb); gl.deleteBuffer(ub); gl.deleteBuffer(ib);
  gl.finish();
}

let SHADER_PATH = '/sdk-shaders/';
let motionState: { began: boolean; finished: boolean; t: number } | null = null;

function lite(ds: any[]) {
  return ds.map(d => ({ id: d.id, bbox: d.bbox, meanVertex: d.meanVertex, opacity: d.opacity, drawOrder: d.drawOrder, renderOrder: d.renderOrder, visible: d.visible }));
}

const api = {
  logs,
  async init(opts: { shaderPath: string; clear?: [number, number, number, number]; scale?: number }) {
    SHADER_PATH = opts.shaderPath;
    if (opts.scale) SCALE = opts.scale;
    if (opts.clear) clearColor = opts.clear;
    canvas = document.getElementById('c') as HTMLCanvasElement;
    const ctx = canvas.getContext('webgl', { alpha: false, premultipliedAlpha: true, preserveDrawingBuffer: true, antialias: false, stencil: true });
    if (!ctx) throw new Error('WebGL unavailable');
    gl = ctx;
    const option = new Option();
    option.logFunction = (m: string) => { logs.push(m); };
    option.loggingLevel = LogLevel.LogLevel_Verbose;
    CubismFramework.startUp(option);
    CubismFramework.initialize();
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    return {
      coreVersion: Live2DCubismCore.Version.csmGetVersion(),
      latestMocVersion: Live2DCubismCore.Version.csmGetLatestMocVersion(),
      glVendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
      glRenderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
      glVersion: gl.getParameter(gl.VERSION),
      canvas: [canvas.width, canvas.height]
    };
  },

  async load(model3Url: string) {
    const dir = model3Url.substring(0, model3Url.lastIndexOf('/') + 1);
    const settingBuf = await fetchBuf(model3Url);
    const setting = new CubismModelSettingJson(settingBuf, settingBuf.byteLength);
    const mocName = setting.getModelFileName();
    const mocBuf = await fetchBuf(dir + mocName);
    const consistencyFramework = CubismMoc.hasMocConsistency(mocBuf);
    const mocVersion = Live2DCubismCore.Version.csmGetMocVersion(mocBuf);
    model = new HarnessModel();
    model.loadModel(mocBuf, true); // shouldCheckMocConsistency = true (SDK refuses inconsistent moc)
    if (!model.getModel()) throw new Error('SDK loadModel failed (inconsistent or unsupported moc)');
    model.createRenderer(canvas.width, canvas.height);
    const textures: string[] = [];
    glTexture = [];
    textureUrls = [];
    for (let i = 0; i < setting.getTextureCount(); i++) {
      const t = setting.getTextureFileName(i);
      textures.push(t);
      textureUrls.push(dir + t);
      glTexture[i] = await loadTexture(dir + t);
      model.getRenderer().bindTexture(i, glTexture[i]);
    }
    model.getRenderer().setIsPremultipliedAlpha(true);
    model.getRenderer().startUp(gl);
    model.getRenderer().loadShaders(SHADER_PATH);
    // wait for the SDK's async shader fetch/compile
    const t0 = performance.now();
    for (;;) {
      const sh: any = CubismShaderManager_WebGL.getInstance().getShader(gl);
      if (sh && sh._isShaderLoaded) break;
      if (performance.now() - t0 > 10000) throw new Error('SDK shaders did not load');
      await new Promise(r => setTimeout(r, 20));
    }
    model.getModel().saveParameters();
    model.getModel().update();
    const cm = coreModel();
    return {
      mocFile: mocName, textures, mocVersion, consistencyFramework,
      canvasInfo: { w: cm.canvasinfo.CanvasWidth, h: cm.canvasinfo.CanvasHeight, ox: cm.canvasinfo.CanvasOriginX, oy: cm.canvasinfo.CanvasOriginY, ppu: cm.canvasinfo.PixelsPerUnit },
      parameters: Array.from({ length: cm.parameters.count }, (_, i) => ({ id: cm.parameters.ids[i], min: cm.parameters.minimumValues[i], max: cm.parameters.maximumValues[i], def: cm.parameters.defaultValues[i] })),
      parts: Array.from({ length: cm.parts.count }, (_, i) => cm.parts.ids[i]),
      motionGroups: Array.from({ length: setting.getMotionGroupCount() }, (_, i) => setting.getMotionGroupName(i))
    };
  },

  setClear(c: [number, number, number, number]) { clearColor = c; },

  /** Re-upload textures; premultiply=false is the straight-alpha negative control. */
  async reloadTextures(premultiply: boolean) {
    for (let i = 0; i < textureUrls.length; i++) {
      gl.deleteTexture(glTexture[i]);
      glTexture[i] = await loadTexture(textureUrls[i], premultiply);
      model!.getRenderer().bindTexture(i, glTexture[i]);
    }
  },

  /** Set parameters (manual pose, NOT motion playback), update Core, draw with the SDK renderer. */
  pose(params: Record<string, number>, mode: 'sdk' | 'raw' | 'raw-reversed' = 'sdk', onlyIds: string[] | null = null) {
    const m = model!.getModel();
    model!.motionManager.stopAllMotions();
    resetToDefaults();
    for (const [id, v] of Object.entries(params)) {
      const idx = m.getParameterIndex(CubismFramework.getIdManager().getId(id));
      if (idx < 0 || idx >= m.getParameterCount()) throw new Error('unknown parameter ' + id);
      m.setParameterValueByIndex(idx, v);
    }
    m.update();
    if (mode === 'sdk') drawSdk(); else drawRaw(mode === 'raw-reversed', onlyIds);
    return { drawables: snapshotCore(), params: paramsSnapshot() };
  },

  /**
   * Parse motion3.json with the SDK (CubismMotionJson consistency check + CubismMotion.create with
   * shouldCheckMotionConsistency=true) and start it on the SDK CubismMotionManager.
   * Parameter values during playback are produced exclusively by CubismMotionManager.updateMotion.
   */
  async motionStart(url: string, loop: boolean | null = null) {
    const buf = await fetchBuf(url);
    const mj = new CubismMotionJson(buf, buf.byteLength);
    const jsonConsistency = mj.hasConsistency();
    const meta = { duration: mj.getMotionDuration(), loop: mj.isMotionLoop(), fps: mj.getMotionFps(), curveCount: mj.getMotionCurveCount(),
      curves: Array.from({ length: mj.getMotionCurveCount() }, (_, i) => ({ target: mj.getMotionCurveTarget(i), id: mj.getMotionCurveId(i).getString() })) };
    mj.release();
    motionState = { began: false, finished: false, t: 0 };
    const st = motionState;
    const motion = CubismMotion.create(buf, buf.byteLength, () => { st.finished = true; }, () => { st.began = true; }, true);
    if (!motion) return { ok: false, jsonConsistency, meta, error: 'CubismMotion.create returned null (parse failure or inconsistent motion3.json)' };
    // SDK CubismMotion.create ignores Meta.Loop (Editor note); apply it via the SDK's own setLoop API.
    const applyLoop = loop === null ? meta.loop : loop;
    motion.setEffectIds([], []); // as LAppModel does; this model3 declares no EyeBlink/LipSync groups
    motion.setLoop(applyLoop);
    motion.setLoopFadeIn(false);
    const m = model!.getModel();
    resetToDefaults();
    m.saveParameters();
    const mm = model!.motionManager;
    mm.stopAllMotions();
    const handle = mm.startMotionPriority(motion, false, 3);
    // frame 0: evaluate at t=0 without advancing time (same loop body as the SDK sample's LAppModel.update)
    m.loadParameters();
    mm.updateMotion(m, 0);
    m.saveParameters();
    m.update();
    return { ok: handle != null && handle !== InvalidMotionQueueEntryHandleValue, handle: handle == null ? null : typeof handle === "number" ? handle : "entry-object", loopApplied: applyLoop, jsonConsistency, meta,
      motionDuration: motion.getDuration(), fadeIn: motion.getFadeInTime(), fadeOut: motion.getFadeOutTime(),
      frame0: { t: 0, params: paramsSnapshot(), drawables: lite(snapshotCore()) } };
  },

  /** Advance SDK motion playback by n fixed steps of dt seconds. Draws with the SDK renderer after the last step if draw. */
  motionAdvance(n: number, dt: number, draw: boolean) {
    const m = model!.getModel();
    const mm = model!.motionManager;
    const frames: any[] = [];
    for (let k = 0; k < n; k++) {
      // Same loop body as the SDK sample's LAppModel.update(): load -> updateMotion -> save -> model.update
      m.loadParameters();
      mm.updateMotion(m, dt);
      m.saveParameters();
      motionState!.t += dt;
      m.update();
      frames.push({ t: motionState!.t, params: paramsSnapshot(), drawables: lite(snapshotCore()), finished: mm.isFinished() });
    }
    if (draw) drawSdk();
    return { frames, began: motionState!.began, finished: motionState!.finished, managerFinished: mm.isFinished() };
  },

  /** SDK stopAllMotions, then keep updating via the manager for n frames (stability check). */
  motionStop(n: number, dt: number) {
    const m = model!.getModel(); const mm = model!.motionManager;
    mm.stopAllMotions();
    const frames: any[] = [];
    for (let k = 0; k < n; k++) { m.loadParameters(); mm.updateMotion(m, dt); m.saveParameters(); m.update();
      frames.push({ params: paramsSnapshot(), drawables: lite(snapshotCore()), finished: mm.isFinished() }); }
    drawSdk();
    return { frames, managerFinished: mm.isFinished() };
  },

  pixels(): string { return canvas.toDataURL('image/png'); }
};

(window as any).siro = api;
