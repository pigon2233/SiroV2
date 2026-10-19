#!/usr/bin/env node
// CP-V03 renderer verification runner.
// node run.cjs --model <model3.json> [--motion <motion3.json>] [--out <dir>] [--base-id fixture_base] [--marker-id fixture_marker]
// Real Cubism Core + SDK Framework (compiled locally from the licensed SDK) + WebGL in headless Chrome (SwiftShader).
// Exit: 0 all PASS, 1 any FAIL, 2 something MISSING/PENDING.
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const NM = '/home/jasonliao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const { chromium } = require(path.join(NM, 'playwright'));
const { PNG } = require(path.join(NM, 'pngjs'));
const { build, SDK } = require('./tools/build.cjs');
const { start } = require('./tools/serve.cjs');
const { launchArgs } = require('./tools/browser.cjs');
const { probe } = require('./tools/core-probe.cjs');

const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const MODEL = path.resolve(arg('--model', '/home/jasonliao/文件/Siro/SiroV2-companion-plan/assets/companion/siro-original/toolchain-roundtrip/0.1.0/runtime/roundtrip.model3.json'));
const MOTION = arg('--motion', null) ? path.resolve(arg('--motion')) : null;
const OUT = path.resolve(arg('--out', path.join(__dirname, 'out/v1')));
const BASE = arg('--base-id', 'fixture_base');
const MARK = arg('--marker-id', 'fixture_marker');
const PARAM = 'ParamAngleX';
const PEAK = Number(arg('--expected-peak', '30')); // expected ParamAngleX peak of the motion (v1: 30, v2: 15)
const K = PEAK / 30; // motion thresholds that depend on amplitude scale with PEAK/30 (v1 values unchanged)
const PREVIEW = argv.includes('--preview');
const ANGLES = [-30, 0, 30];
const SCALE = 1.6, W = 512, H = 512;
const MAGENTA = [1, 0, 1, 1], GREEN = [0, 1, 0, 1];
const TIMEOUT = 60000;

const checks = [];
const check = (id, status, observed, note) => { checks.push({ id, status, observed, note }); return status === 'PASS'; };
const pass = b => b ? 'PASS' : 'FAIL';
const sha = f => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
const rd = f => PNG.sync.read(fs.readFileSync(f));
const px = (img, x, y) => { const i = (y * img.width + x) * 4; return [img.data[i], img.data[i + 1], img.data[i + 2]]; };
const near = (a, b, t = 3) => Math.abs(a[0] - b[0]) <= t && Math.abs(a[1] - b[1]) <= t && Math.abs(a[2] - b[2]) <= t;
const toPx = (X, Y) => [(0.5 + SCALE / 2 * X) * W, (0.5 - SCALE / 2 * Y) * H];
const c255 = c => c.slice(0, 3).map(v => Math.round(v * 255));

function stats(img, color) {
  let n = 0, sx = 0, sy = 0;
  for (let y = 0; y < img.height; y++) for (let x = 0; x < img.width; x++) if (near(px(img, x, y), color)) { n++; sx += x; sy += y; }
  return { count: n, centroid: n ? [+(sx / n).toFixed(2), +(sy / n).toFixed(2)] : null };
}
function diffCount(a, b, t = 3, mask) {
  let n = 0;
  for (let y = 0; y < a.height; y++) for (let x = 0; x < a.width; x++) {
    if (mask && !mask(x, y)) continue;
    if (!near(px(a, x, y), px(b, x, y), t)) n++;
  }
  return n;
}
function segDist(p, a, b) {
  const d = [b[0] - a[0], b[1] - a[1], b[2] - a[2]]; const L = d[0] ** 2 + d[1] ** 2 + d[2] ** 2;
  let t = L ? ((p[0] - a[0]) * d[0] + (p[1] - a[1]) * d[1] + (p[2] - a[2]) * d[2]) / L : 0; t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - a[0] - t * d[0], p[1] - a[1] - t * d[1], p[2] - a[2] - t * d[2]);
}
function foreign(img, palette, tol = 8) {
  let n = 0;
  for (let y = 0; y < img.height; y++) for (let x = 0; x < img.width; x++) {
    const p = px(img, x, y); let best = Infinity;
    for (let i = 0; i < palette.length; i++) for (let j = i; j < palette.length; j++) best = Math.min(best, segDist(p, palette[i], palette[j]));
    if (best > tol) n++;
  }
  return n;
}
function texColors(texPath, uvb) {
  const t = rd(texPath); const h = new Map();
  const x0 = Math.floor(uvb[0] * t.width), x1 = Math.ceil(uvb[2] * t.width);
  const y0 = Math.floor((1 - uvb[3]) * t.height), y1 = Math.ceil((1 - uvb[1]) * t.height);
  const alpha = {};
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
    const i = (y * t.width + x) * 4; const a = t.data[i + 3]; alpha[a] = (alpha[a] || 0) + 1;
    if (a === 255) { const k = [t.data[i], t.data[i + 1], t.data[i + 2]].join(','); h.set(k, (h.get(k) || 0) + 1); }
  }
  const top = [...h.entries()].sort((a, b) => b[1] - a[1])[0];
  return { color: top ? top[0].split(',').map(Number) : null, alphaHistogram: alpha };
}
const ev = (page, fn, a) => page.evaluate(fn, a);

async function main() {
  fs.rmSync(OUT, { recursive: true, force: true }); // never let stale screenshots count
  fs.mkdirSync(OUT, { recursive: true });
  const report = { expectedPeak: PEAK, tool: 'siro-v03-renderer/run.cjs', started: new Date().toISOString(), model: MODEL, motion: MOTION, out: OUT, sdk: SDK, checks };

  // ---- input presence ----
  if (!fs.existsSync(MODEL)) { check('input.model3', 'MISSING', MODEL); return finish(report); }
  const dir = path.dirname(MODEL);
  const m3 = JSON.parse(fs.readFileSync(MODEL, 'utf8'));
  const refs = [m3.FileReferences.Moc, ...(m3.FileReferences.Textures || []), m3.FileReferences.DisplayInfo].filter(Boolean);
  const missing = refs.filter(r => !fs.existsSync(path.join(dir, r)));
  report.inputs = Object.fromEntries([path.basename(MODEL), ...refs, ...(MOTION ? [MOTION] : [])].map(r => { const f = path.resolve(dir, r); return [r, fs.existsSync(f) ? sha(f) : 'MISSING']; }));
  check('input.references', missing.length ? 'MISSING' : 'PASS', { refs, missing });
  if (missing.length) return finish(report);
  const texPath = path.join(dir, m3.FileReferences.Textures[0]);

  // ---- Node-side Core (independent instance) ----
  const nodeCore = {};
  for (const a of [...new Set([...ANGLES, PEAK])]) nodeCore[a] = await probe(MODEL, { [PARAM]: a });
  const n0 = nodeCore[0];
  report.core = { coreVersion: n0.coreVersion, mocVersion: n0.mocVersion, latestMocVersion: n0.latestMocVersion, canvas: n0.canvas,
    drawables: n0.drawables.map(d => ({ id: d.id, drawOrder: d.drawOrder, renderOrder: d.renderOrder, opacity: d.opacity, blendMode: d.blendMode, vertexCount: d.vertexCount, indexCount: d.indexCount, bbox: d.bbox, uvBbox: d.uvBbox })) };
  check('core.node.mocConsistency', pass(n0.mocConsistency), n0.mocConsistency);
  check('core.mocVersion', pass(n0.mocVersion > 0 && n0.mocVersion <= n0.latestMocVersion), { moc: n0.mocVersion, latest: n0.latestMocVersion });
  const dIdx = id => n0.drawables.findIndex(d => d.id === id);
  if (dIdx(BASE) < 0 || dIdx(MARK) < 0) { check('core.fixtureIds', 'FAIL', n0.drawables.map(d => d.id)); return finish(report); }
  const meshOk = n0.drawables.every(d => d.indices.every(i => i < d.vertexCount) && d.texture < m3.FileReferences.Textures.length);
  check('core.meshIndicesInRange', pass(meshOk), meshOk);
  if (m3.FileReferences.DisplayInfo) {
    const cdi = JSON.parse(fs.readFileSync(path.join(dir, m3.FileReferences.DisplayInfo), 'utf8'));
    const ids = new Set(n0.parameters.map(p => p.id)); const bad = (cdi.Parameters || []).map(p => p.Id).filter(i => !ids.has(i));
    check('core.cdi3ParamsInMoc', pass(!bad.length), { cdiParams: (cdi.Parameters || []).length, notInMoc: bad });
  }

  // ---- browser ----
  build && await build();
  const srv = await start();
  const browser = await chromium.launch({ ...launchArgs(), timeout: TIMEOUT });
  try {
    const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
    page.setDefaultTimeout(TIMEOUT);
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error' && !/favicon|404/.test(m.text())) errors.push(m.text()); });
    await page.goto(srv.origin + '/');
    report.browser = { version: browser.version(), ...(await ev(page, o => window.siro.init(o), { shaderPath: '/sdk-shaders/', scale: SCALE, clear: MAGENTA })) };
    const base = srv.addFolder('m', dir);
    const info = await ev(page, u => window.siro.load(u), base + path.basename(MODEL));
    report.load = { ...info, parameters: info.parameters.length };
    check('core.browser.frameworkMocConsistency', pass(info.consistencyFramework), info.consistencyFramework, 'CubismMoc.hasMocConsistency + loadModel(buf, true) succeeded');

    const shot = async (name) => { const f = path.join(OUT, name + '.png'); await page.locator('#c').screenshot({ path: f }); return f; };
    const pose = async (a, mode = 'sdk', only = null, name) => {
      const r = await ev(page, ([p, m, o]) => window.siro.pose(p, m, o), [{ [PARAM]: a }, mode, only]);
      return { core: r, file: await shot(name) };
    };

    // Core node vs browser consistency at the three angles
    const sdkShots = {}; let maxPosDiff = 0, structEq = true;
    for (const a of ANGLES) {
      const r = await pose(a, 'sdk', null, `sdk_${PARAM}_${a}`);
      sdkShots[a] = r;
      for (const bd of r.core.drawables) {
        const nd = nodeCore[a].drawables.find(d => d.id === bd.id);
        if (!nd) { structEq = false; continue; }
        for (let k = 0; k < bd.positions.length; k++) maxPosDiff = Math.max(maxPosDiff, Math.abs(bd.positions[k] - nd.positions[k]));
        structEq = structEq && bd.drawOrder === nd.drawOrder && bd.renderOrder === nd.renderOrder && bd.opacity === nd.opacity &&
          JSON.stringify(bd.indices) === JSON.stringify(nd.indices) && bd.uvs.every((u, k) => Math.abs(u - nd.uvs[k]) < 1e-7);
      }
    }
    check('core.nodeVsBrowserIdentical', pass(structEq && maxPosDiff <= 1e-6), { maxPosDiff, structuralEqual: structEq });

    const B = id => sdkShots[0].core.drawables.find(d => d.id === id);
    const baseCol = texColors(texPath, n0.drawables[dIdx(BASE)].uvBbox), markCol = texColors(texPath, n0.drawables[dIdx(MARK)].uvBbox);
    report.colors = { base: baseCol, marker: markCol, clear: c255(MAGENTA) };

    // ---- base static ----
    const baseOnly = {};
    for (const a of ANGLES) baseOnly[a] = rd((await pose(a, 'raw', [BASE], `rawonly_base_${PARAM}_${a}`)).file);
    const baseCoreMax = Math.max(...ANGLES.map(a => Math.max(...nodeCore[a].drawables[dIdx(BASE)].positions.map((v, k) => Math.abs(v - n0.drawables[dIdx(BASE)].positions[k])))));
    const sdkImg = Object.fromEntries(ANGLES.map(a => [a, rd(sdkShots[a].file)]));
    const mb = ANGLES.map(a => nodeCore[a].drawables[dIdx(MARK)].bbox.map((v, k) => v)).map(b => [toPx(b[0], b[3]), toPx(b[2], b[1])]);
    const mx0 = Math.min(...mb.map(b => b[0][0])) - 4, mx1 = Math.max(...mb.map(b => b[1][0])) + 4, my0 = Math.min(...mb.map(b => b[0][1])) - 4, my1 = Math.max(...mb.map(b => b[1][1])) + 4;
    const outside = (x, y) => !(x >= mx0 && x <= mx1 && y >= my0 && y <= my1);
    const bs = {
      coreBaseVertexMaxDelta: baseCoreMax,
      baseOnlyRenderDiffPx: { '-30vs0': diffCount(baseOnly[-30], baseOnly[0], 0), '30vs0': diffCount(baseOnly[30], baseOnly[0], 0) },
      sdkOutsideMarkerAreaDiffPx: { '-30vs0': diffCount(sdkImg[-30], sdkImg[0], 0, outside), '30vs0': diffCount(sdkImg[30], sdkImg[0], 0, outside) },
      baseColorPx: ANGLES.map(a => stats(baseOnly[a], baseCol.color).count)
    };
    check('render.baseStatic', pass(bs.coreBaseVertexMaxDelta === 0 && !bs.baseOnlyRenderDiffPx['-30vs0'] && !bs.baseOnlyRenderDiffPx['30vs0'] &&
      !bs.sdkOutsideMarkerAreaDiffPx['-30vs0'] && !bs.sdkOutsideMarkerAreaDiffPx['30vs0'] && bs.baseColorPx[1] > 1000), bs);

    // ---- marker moves ----
    const markOnly = {};
    for (const a of ANGLES) markOnly[a] = stats(rd((await pose(a, 'raw', [MARK], `rawonly_marker_${PARAM}_${a}`)).file), markCol.color);
    const sdkMark = Object.fromEntries(ANGLES.map(a => [a, stats(sdkImg[a], markCol.color)]));
    const coreMx = Object.fromEntries([...new Set([...ANGLES, PEAK])].map(a => [a, nodeCore[a].drawables[dIdx(MARK)].positions.filter((_, k) => k % 2 === 0).reduce((s, v, _, arr) => s + v / arr.length, 0)]));
    const predShift = a => (coreMx[a] - coreMx[0]) * SCALE / 2 * W;
    const mm = { coreMeanX: coreMx, predictedShiftPx: { '-30': predShift(-30), '30': predShift(30) },
      markerOnlyCentroid: Object.fromEntries(ANGLES.map(a => [a, markOnly[a].centroid])), markerOnlyCount: ANGLES.map(a => markOnly[a].count),
      sdkVisibleMarkerCentroid: Object.fromEntries(ANGLES.map(a => [a, sdkMark[a].centroid])) };
    mm.measuredShiftPx = { '-30': markOnly[-30].centroid[0] - markOnly[0].centroid[0], '30': markOnly[30].centroid[0] - markOnly[0].centroid[0] };
    mm.measuredYShiftPx = { '-30': markOnly[-30].centroid[1] - markOnly[0].centroid[1], '30': markOnly[30].centroid[1] - markOnly[0].centroid[1] };
    check('render.markerMoves', pass(Math.abs(predShift(30)) > 10 && ['-30', '30'].every(k => Math.abs(mm.measuredShiftPx[k] - mm.predictedShiftPx[k]) <= 1.5 && Math.abs(mm.measuredYShiftPx[k]) <= 1) &&
      Math.max(...mm.markerOnlyCount) / Math.min(...mm.markerOnlyCount) < 1.05), mm);

    // ---- alpha ----
    await ev(page, c => window.siro.setClear(c), GREEN);
    const green = rd((await pose(0, 'sdk', null, `sdk_${PARAM}_0_clearGreen`)).file);
    await ev(page, c => window.siro.setClear(c), MAGENTA);
    const mag = sdkImg[0];
    const bb = B(BASE).bbox; const [qx0, qy0] = toPx(bb[0], bb[3]), [qx1, qy1] = toPx(bb[2], bb[1]);
    let inQuad = 0, inQuadBg = 0, bgFollow = 0, bgMag = 0;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const isMag = near(px(mag, x, y), c255(MAGENTA), 0);
      if (isMag) { bgMag++; if (near(px(green, x, y), c255(GREEN), 0)) bgFollow++; }
      if (x > qx0 + 2 && x < qx1 - 2 && y > qy0 + 2 && y < qy1 - 2) { inQuad++; if (isMag) inQuadBg++; }
    }
    const palette = [c255(MAGENTA), baseCol.color, markCol.color];
    const opaqueChanged = diffCount(mag, green, 0, (x, y) => !near(px(mag, x, y), c255(MAGENTA), 0) && !near(px(green, x, y), c255(GREEN), 0) && (near(px(mag, x, y), baseCol.color, 0) || near(px(mag, x, y), markCol.color, 0)));
    const al = { textureAlphaInBaseUv: baseCol.alphaHistogram, textureAlphaInMarkerUv: markCol.alphaHistogram,
      coreOpacity: { [BASE]: B(BASE).opacity, [MARK]: B(MARK).opacity },
      baseQuadPx: inQuad, baseQuadPxShowingBackground: inQuadBg, bgPixelsFollowClearColor: `${bgFollow}/${bgMag}`, opaquePixelsChangedWithClear: opaqueChanged,
      foreignPx: foreign(mag, palette) };
    // straight-alpha negative control
    await ev(page, () => window.siro.reloadTextures(false));
    const straight = rd((await pose(0, 'sdk', null, `negctl_straightAlpha_${PARAM}_0`)).file);
    al.negativeControl_straightAlpha_foreignPx = foreign(straight, palette);
    al.negativeControl_straightAlpha_baseQuadBgPx = (() => { let n = 0; for (let y = Math.ceil(qy0 + 3); y < qy1 - 3; y++) for (let x = Math.ceil(qx0 + 3); x < qx1 - 3; x++) if (near(px(straight, x, y), c255(MAGENTA), 0)) n++; return n; })();
    await ev(page, () => window.siro.reloadTextures(true));
    check('render.alpha', pass(inQuadBg > 1000 && bgFollow === bgMag && opaqueChanged === 0 && al.foreignPx <= W * H * 0.002), al);
    check('negctl.straightAlphaDetected', pass(al.negativeControl_straightAlpha_foreignPx > W * H * 0.01), al.negativeControl_straightAlpha_foreignPx, 'straight-alpha upload into premultiplied pipeline must be flagged');

    // ---- draw order ----
    const bOnly = baseOnly[0], mOnlyImg = rd(path.join(OUT, `rawonly_marker_${PARAM}_0.png`));
    const rev = rd((await pose(0, 'raw-reversed', null, `negctl_reversedOrder_${PARAM}_0`)).file);
    const raw = rd((await pose(0, 'raw', null, `raw_${PARAM}_0`)).file);
    let ov = 0, ovMarkerSdk = 0, ovBaseRev = 0;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (near(px(bOnly, x, y), baseCol.color, 0) && near(px(mOnlyImg, x, y), markCol.color, 0)) {
      ov++; if (near(px(mag, x, y), markCol.color, 0)) ovMarkerSdk++; if (near(px(rev, x, y), baseCol.color, 0)) ovBaseRev++;
    }
    const dor = { core: { [BASE]: { drawOrder: B(BASE).drawOrder, renderOrder: B(BASE).renderOrder }, [MARK]: { drawOrder: B(MARK).drawOrder, renderOrder: B(MARK).renderOrder } },
      overlapPx: ov, overlapShowingMarkerInSdk: ovMarkerSdk, negativeControl_reversed_overlapShowingBase: ovBaseRev, sdkVsIndependentRawDiffPx: diffCount(mag, raw, 3) };
    check('render.drawOrder', pass(B(BASE).renderOrder < B(MARK).renderOrder && ov > 500 && ovMarkerSdk / ov >= 0.995 && dor.sdkVsIndependentRawDiffPx <= W * H * 0.005), dor);
    check('negctl.reversedOrderDetected', pass(ov > 0 && ovBaseRev / ov >= 0.995), { overlapPx: ov, reversedShowsBase: ovBaseRev });

    // ---- motion via SDK CubismMotionManager ----
    if (!MOTION) check('motion', 'PENDING', null, 'no --motion given');
    else if (!fs.existsSync(MOTION)) check('motion', 'MISSING', MOTION);
    else {
      const mj = JSON.parse(fs.readFileSync(MOTION, 'utf8'));
      const murl = srv.addFile('motion.motion3.json', MOTION);
      const st = await ev(page, u => window.siro.motionStart(u), murl);
      const mot = { start: { ok: st.ok, handle: st.handle, jsonConsistency: st.jsonConsistency, meta: st.meta, loopApplied: st.loopApplied, sdkDuration: st.motionDuration, fadeIn: st.fadeIn, fadeOut: st.fadeOut } };
      check('motion.sdkParse', pass(st.ok && st.jsonConsistency), mot.start);
      const dt = 1 / 60, times = [0, 0.5, 1, 1.5, 2, 2.5];
      const timeline = []; const all = [{ t: 0, a: st.frame0.params[PARAM] }];
      let frame = 0;
      const rec = async (t, params, drawables) => {
        const f = await shot(`motion_t${t.toFixed(1)}s`);
        const img = rd(f); const ms = stats(img, markCol.color);
        const md = drawables.find(d => d.id === MARK);
        timeline.push({ t, [PARAM]: +params[PARAM].toFixed(4), coreMarkerMeanX: +md.meanVertex[0].toFixed(5), sdkVisibleMarkerCentroid: ms.centroid, markerPx: ms.count,
          baseOnlyDiffOutsideMarkerPx: diffCount(img, sdkImg[0], 0, outside), screenshot: path.basename(f) });
      };
      await ev(page, () => window.siro.motionAdvance(0, 1 / 60, true));
      await rec(0, st.frame0.params, st.frame0.drawables);
      for (const t of times.slice(1)) {
        const target = Math.round(t / dt);
        const r = await ev(page, ([n, d]) => window.siro.motionAdvance(n, d, true), [target - frame, dt]);
        frame = target;
        r.frames.forEach(fr => all.push({ t: +fr.t.toFixed(4), a: fr.params[PARAM] }));
        const last = r.frames[r.frames.length - 1];
        await rec(t, last.params, last.drawables);
        mot.began = r.began; mot.finishedCallback = r.finished; mot.managerFinished = r.managerFinished;
      }
      mot.timeline = timeline;
      const at = t => timeline.find(e => e.t === t);
      const expected = { 0: 0, 1: PEAK, 2: 0, note: 'curve 0->PEAK->0 over 2s loop; 0.5/1.5/2.5 are mid-ramp (range-checked only)', expectedPeak: PEAK, predictedPeakShiftPx: predShift(PEAK) };
      mot.expectedFromCurveApprox = expected;
      // loop continuity: max per-frame jump of ParamAngleX vs typical; across 2.0s wrap
      const jumps = all.slice(1).map((e, i) => ({ t: e.t, d: Math.abs(e.a - all[i].a) }));
      const maxJump = jumps.reduce((m, j) => j.d > m.d ? j : m, { d: 0 });
      const wrap = jumps.filter(j => j.t > 1.95 && j.t < 2.05);
      mot.loop = { maxPerFrameDelta: maxJump, aroundWrapMaxDelta: Math.max(...wrap.map(j => j.d)), valuesNearWrap: all.filter(e => e.t > 1.95 && e.t < 2.05).map(e => [e.t, +e.a.toFixed(4)]) };
      const pxPerUnit = SCALE / 2 * W;
      const trackOk = timeline.every(e => e.baseOnlyDiffOutsideMarkerPx === 0);
      const coreLinear = timeline.every(e => Math.abs((e.coreMarkerMeanX - coreMx[0]) - (coreMx[PEAK] - coreMx[0]) * e[PARAM] / PEAK) < 2e-3);
      check('motion.playbackValues', pass(Math.abs(at(0)[PARAM]) < 0.5 && Math.abs(at(1)[PARAM] - PEAK) < 0.5 && Math.abs(at(2)[PARAM]) < 0.5 && [0.5, 1.5, 2.5].every(t => at(t)[PARAM] > PEAK / 6 && at(t)[PARAM] < PEAK * 5 / 6) && Math.abs(at(1.5)[PARAM] - at(0.5)[PARAM]) < 1 * K),
        timeline.map(e => [e.t, e[PARAM]]), 'values produced only by CubismMotionManager.updateMotion');
      check('motion.markerFollowsAndBaseStatic', pass(trackOk && coreLinear && Math.abs((at(1).sdkVisibleMarkerCentroid[0] - at(0).sdkVisibleMarkerCentroid[0]) - predShift(PEAK)) <= 1.5 && Math.abs(at(2).sdkVisibleMarkerCentroid[0] - at(0).sdkVisibleMarkerCentroid[0]) <= 1),
        timeline.map(e => ({ t: e.t, centroid: e.sdkVisibleMarkerCentroid, baseDiff: e.baseOnlyDiffOutsideMarkerPx })));
      check('motion.loopContinuity', pass(st.loopApplied && mot.loop.aroundWrapMaxDelta <= maxJump.d && maxJump.d < 1.5 * K && at(2.5)[PARAM] > PEAK / 6), mot.loop,
        `continuity only. Observed: t=0.5 ${at(0.5)[PARAM]} (1s SDK fade-in active) vs t=2.5 ${at(2.5)[PARAM]} (2nd cycle; symmetric bezier ideal ${PEAK / 2} => ~${(PEAK / 2 - at(2.5)[PARAM]).toFixed(2)} lag after loop wrap, finding not asserted)`);
      // stopAllMotions stability
      const stop = await ev(page, ([n, d]) => window.siro.motionStop(n, d), [30, dt]);
      const sv = stop.frames.map(f => f.params[PARAM]);
      const stopImg = rd(await shot('motion_afterStopAllMotions'));
      mot.stop = { managerFinished: stop.managerFinished, angleXFirst: sv[0], angleXLast: sv[sv.length - 1], spread: Math.max(...sv) - Math.min(...sv), allFinite: sv.every(Number.isFinite), baseDiffOutsideMarker: diffCount(stopImg, sdkImg[0], 0, outside) };
      check('motion.stopAllMotionsStable', pass(stop.managerFinished && mot.stop.spread === 0 && mot.stop.allFinite && mot.stop.baseDiffOutsideMarker === 0), mot.stop, 'after stop, params hold last value (SDK does not reset) and stay constant');
      if (PREVIEW) { // fresh SDK motion start; dt=1/60, SDK screenshot every 6 steps (0.1 s) up to 2.2 s
        const pdir = path.join(OUT, 'preview'); fs.mkdirSync(pdir);
        const s2 = await ev(page, u => window.siro.motionStart(u), murl);
        const prev = [];
        for (let i = 0; i <= 22; i++) {
          const r = i ? await ev(page, ([n, d]) => window.siro.motionAdvance(n, d, true), [6, dt]) : await ev(page, () => window.siro.motionAdvance(0, 1 / 60, true));
          const p = i ? r.frames[r.frames.length - 1].params : s2.frame0.params;
          const f = path.join(pdir, `frame_${String(i).padStart(3, '0')}.png`);
          await page.locator('#c').screenshot({ path: f });
          prev.push({ i, t: +(i * 0.1).toFixed(1), [PARAM]: +p[PARAM].toFixed(4), centroid: stats(rd(f), markCol.color).centroid, file: 'preview/' + path.basename(f) });
        }
        mot.preview = prev;
      }
      report.motion = mot;
    }
    report.pageErrors = errors;
    check('browser.noPageErrors', pass(!errors.length), errors);
    report.serverRequests = srv.log.length;
  } finally {
    await browser.close().catch(() => {});
    await srv.close();
  }
  return finish(report);
}

function finish(report) {
  report.finished = new Date().toISOString();
  const st = checks.map(c => c.status);
  report.overall = st.includes('FAIL') ? 'FAIL' : (st.includes('MISSING') || st.includes('PENDING')) ? 'INCOMPLETE' : 'PASS';
  report.screenshots = fs.existsSync(OUT) ? fs.readdirSync(OUT).filter(f => f.endsWith('.png')).sort() : [];
  report.limitations = [
    'Headless Chrome with SwiftShader (software WebGL via ANGLE); GPU drivers not exercised.',
    'Framework compiled locally from licensed SDK with SDK-bundled rolldown; build/ must not be redistributed.',
    'Meta.Loop is applied with SDK ACubismMotion.setLoop(true) because CubismMotion.create ignores Meta.Loop by design.',
    'Loop phase: ~1.5 ParamAngleX lag observed at t=2.5 (v1); continuity is gated, perfect phase is not claimed.', 'Scope: basic SDK playback (CP-V03), not motion naturalness.'
  ];
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 1));
  for (const c of checks) console.log(c.status.padEnd(8), c.id);
  console.log('OVERALL', report.overall, '->', path.join(OUT, 'report.json'));
  process.exitCode = report.overall === 'PASS' ? 0 : report.overall === 'FAIL' ? 1 : 2;
}

const killer = setTimeout(() => { console.error('global timeout'); process.exit(3); }, 300000); killer.unref();
main().catch(e => { check('runner.exception', 'FAIL', String(e && e.stack || e).slice(0, 1500)); finish({ model: MODEL, motion: MOTION, checks }); });
