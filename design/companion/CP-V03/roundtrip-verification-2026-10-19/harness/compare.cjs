#!/usr/bin/env node
// Independent v1 vs v2 comparison from run.cjs reports + fresh SHA-256 of the actual input files.
// node compare.cjs [--v1 out/v1-final] [--v2 out/v2-final] [--v1dir <runtime>] [--v2dir <runtime>] [--out out/comparison.json]
'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const RT = '/home/jasonliao/文件/Siro/SiroV2-companion-plan/assets/companion/siro-original/toolchain-roundtrip';
const V1 = path.resolve(__dirname, arg('--v1', 'out/v1-final')), V2 = path.resolve(__dirname, arg('--v2', 'out/v2-final'));
const D1 = arg('--v1dir', RT + '/0.1.0/runtime'), D2 = arg('--v2dir', RT + '/0.2.0/runtime');
const OUT = path.resolve(__dirname, arg('--out', 'out/comparison.json'));
const checks = [];
const check = (id, ok, observed) => checks.push({ id, status: ok ? 'PASS' : 'FAIL', observed });
const sha = f => fs.existsSync(f) ? crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex') : 'MISSING';
const load = d => { const f = path.join(d, 'report.json'); return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : null; };
const r1 = load(V1), r2 = load(V2);
check('reports.presentAndPass', r1 && r2 && r1.overall === 'PASS' && r2.overall === 'PASS', { v1: r1 && r1.overall, v2: r2 && r2.overall });
if (r1 && r2) {
  const files = ['roundtrip.moc3', 'roundtrip.1024/texture_00.png', 'roundtrip.model3.json', 'roundtrip.cdi3.json', 'roundtrip.motion3.json'];
  const h = Object.fromEntries(files.map(f => [f, { v1: sha(path.join(D1, f)), v2: sha(path.join(D2, f)) }]));
  const same = f => h[f].v1 !== 'MISSING' && h[f].v1 === h[f].v2;
  check('inputs.reportShaMatchesDisk', ['roundtrip.moc3', 'roundtrip.1024/texture_00.png'].every(f => r1.inputs[f] === h[f].v1 && r2.inputs[f] === h[f].v2) &&
    Object.entries(r1.inputs).find(([k]) => k.endsWith('roundtrip.motion3.json'))[1] === h['roundtrip.motion3.json'].v1 && Object.entries(r2.inputs).find(([k]) => k.endsWith('roundtrip.motion3.json'))[1] === h['roundtrip.motion3.json'].v2, h);
  check('inputs.sameMocAndTexture', same('roundtrip.moc3') && same('roundtrip.1024/texture_00.png'), { moc: h['roundtrip.moc3'], texture: h['roundtrip.1024/texture_00.png'] });
  check('inputs.motionDiffers', h['roundtrip.motion3.json'].v1 !== h['roundtrip.motion3.json'].v2 && !h['roundtrip.motion3.json'].v2.startsWith('MISSING'), h['roundtrip.motion3.json']);
  const curvePeak = d => { const m = JSON.parse(fs.readFileSync(path.join(d, 'roundtrip.motion3.json'), 'utf8'));
    const c = m.Curves.find(c => c.Id === 'ParamAngleX'); return { max: Math.max(...c.Segments.filter((_, i) => i % 2 === 1 || i === 1)), duration: m.Meta.Duration, loop: m.Meta.Loop, segments: c.Segments }; };
  // value positions: Segments = [t0,v0, type, ...]; use explicit parse to take only values
  const vals = segs => { const v = [segs[1]]; let i = 2; while (i < segs.length) { const t = segs[i]; const n = t === 1 ? 3 : 1; for (let k = 0; k < n; k++) v.push(segs[i + 2 + 2 * k]); i += 1 + 2 * n; } return v; };
  const c1 = curvePeak(D1), c2 = curvePeak(D2);
  const p1 = Math.max(...vals(c1.segments)), p2 = Math.max(...vals(c2.segments));
  check('source.curvePeak30vs15', p1 === 30 && p2 === 15 && c1.duration === c2.duration && c1.duration === 2, { v1: { peak: p1, duration: c1.duration, loop: c1.loop }, v2: { peak: p2, duration: c2.duration, loop: c2.loop } });
  const at = (r, t) => r.motion.timeline.find(e => e.t === t);
  const s1 = at(r1, 1).ParamAngleX, s2 = at(r2, 1).ParamAngleX;
  check('sdk.observedAt1s30vs15', Math.abs(s1 - 30) < 0.5 && Math.abs(s2 - 15) < 0.5, { v1: s1, v2: s2 });
  const base = r => r.checks.find(c => c.id === 'render.baseStatic').observed;
  const mb = r => r.motion.timeline.map(e => e.baseOnlyDiffOutsideMarkerPx);
  check('render.baseUnchanged', [r1, r2].every(r => base(r).coreBaseVertexMaxDelta === 0 && mb(r).every(v => v === 0)) &&
    JSON.stringify(base(r1).baseColorPx) === JSON.stringify(base(r2).baseColorPx), { v1: { pose: base(r1), motion: mb(r1) }, v2: { pose: base(r2), motion: mb(r2) } });
  const cx = (r, t) => at(r, t).sdkVisibleMarkerCentroid[0];
  const o = { v1: { t0: cx(r1, 0), t1: cx(r1, 1), shift: cx(r1, 1) - cx(r1, 0) }, v2: { t0: cx(r2, 0), t1: cx(r2, 1), shift: cx(r2, 1) - cx(r2, 0) } };
  check('render.centroid332vs300_shift64vs32', o.v1.t0 === 268 && o.v2.t0 === 268 && Math.abs(o.v1.t1 - 332) <= 1 && Math.abs(o.v2.t1 - 300) <= 1 &&
    Math.abs(o.v1.shift - 64) <= 1 && Math.abs(o.v2.shift - 32) <= 1 && Math.abs(o.v1.shift / o.v2.shift - 2) <= 0.05, o);
  var observed = { hashes: h, timelines: { v1: r1.motion.timeline.map(e => [e.t, e.ParamAngleX, e.sdkVisibleMarkerCentroid]), v2: r2.motion.timeline.map(e => [e.t, e.ParamAngleX, e.sdkVisibleMarkerCentroid]) },
    loop: { v1: r1.motion.loop, v2: r2.motion.loop } };
}
const overall = checks.every(c => c.status === 'PASS') ? 'PASS' : 'FAIL';
fs.writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), v1Report: V1, v2Report: V2, v1Dir: D1, v2Dir: D2, overall, checks, observed }, null, 1));
for (const c of checks) console.log(c.status.padEnd(5), c.id);
console.log('OVERALL', overall, '->', OUT);
process.exitCode = overall === 'PASS' ? 0 : 1;
