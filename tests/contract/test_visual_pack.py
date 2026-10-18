"""CP-P01: activity pack validation and the renderer-local activity controller."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from siro.adapters.body.visual_pack import BODY_IDS, VisualPackError, load_visual_pack

PACK = Path("assets/companion/haru-upperbody/0.1.0")
CONTROLLER = Path("scripts/companion_renderer/siroactivity.ts").resolve()
REAL_DIST = Path("models/live2d-sdk-5-r.5/CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo/dist")


def make_pack(tmp_path: Path) -> tuple[Path, Path]:
    """Copy the committed pack and bind it to synthetic model files (no licensed assets)."""
    pack_dir = tmp_path / "pack"
    shutil.copytree(PACK, pack_dir)
    model_root = tmp_path / "dist"
    pack = json.loads((pack_dir / "pack.json").read_text())
    compatibility = {}
    for relative in pack["compatibility"]:
        data = f"synthetic {relative}".encode()
        target = model_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        compatibility[relative] = hashlib.sha256(data).hexdigest()
    pack["compatibility"] = compatibility
    (pack_dir / "pack.json").write_text(json.dumps(pack))
    return pack_dir, model_root


def edit_pack(pack_dir: Path, change: object) -> None:
    path = pack_dir / "pack.json"
    pack = json.loads(path.read_text())
    assert callable(change)
    change(pack)
    path.write_text(json.dumps(pack))


def rewrite_motion(pack_dir: Path, kind: str, change: object) -> None:
    """Change a motion file and re-sign it, so only the semantic check can reject it."""
    assert callable(change)
    pack = json.loads((pack_dir / "pack.json").read_text())
    entry = next(item for item in pack["activities"] if item["activity"] == kind)
    path = pack_dir / entry["file"]
    motion = json.loads(path.read_text())
    change(motion)
    data = json.dumps(motion).encode()
    path.write_bytes(data)
    entry["sha256"] = hashlib.sha256(data).hexdigest()
    (pack_dir / "pack.json").write_text(json.dumps(pack))


def test_committed_pack_validates_and_exposes_only_body_curves(tmp_path: Path) -> None:
    pack = load_visual_pack(*make_pack(tmp_path))
    assert (pack.pack_id, pack.version) == ("siro.haru.upperbody", "0.1.0")
    assert set(pack.activities) == {
        "idle",
        "attention",
        "nod",
        "thinking",
        "reading_pose",
        "speaking_pose",
    }
    assert not pack.activities["nod"].loop and pack.activities["nod"].duration == 1.2
    payload = pack.renderer_payload()
    assert payload["body_ids"] == list(BODY_IDS) and payload["gaze"] == "unsupported"
    activities = payload["activities"]
    assert isinstance(activities, dict)
    for clip in activities.values():
        assert set(clip["curves"]) == set(BODY_IDS)
        assert (clip["entry"], clip["exit"], clip["resume"]) == (0.35, 0.4, 0.4)


@pytest.mark.skipif(not REAL_DIST.is_dir(), reason="licensed Haru renderer is local-only")
def test_committed_pack_matches_the_local_haru_renderer() -> None:
    assert load_visual_pack(PACK, REAL_DIST).version == "0.1.0"


def _mouth_curve(motion: dict[str, list[dict[str, object]]]) -> None:
    motion["Curves"][0]["Id"] = "ParamMouthOpenY"


def _nan_segment(motion: dict[str, list[dict[str, list[float]]]]) -> None:
    motion["Curves"][0]["Segments"][1] = float("nan")


def _bad_order(motion: dict[str, list[dict[str, list[float]]]]) -> None:
    motion["Curves"][0]["Segments"][3] = 99.0


def _bad_meta(motion: dict[str, dict[str, object]]) -> None:
    motion["Meta"]["Duration"] = 2.5


@pytest.mark.parametrize(
    ("label", "change", "reason"),
    [
        ("mouth", _mouth_curve, "outside the body mask"),
        ("nan", _nan_segment, "non-finite"),
        ("order", _bad_order, "out of order"),
        ("meta", _bad_meta, "metadata disagrees"),
    ],
)
def test_resigned_motion_with_bad_content_is_rejected(
    tmp_path: Path, label: str, change: object, reason: str
) -> None:
    del label
    pack_dir, model_root = make_pack(tmp_path)
    rewrite_motion(pack_dir, "nod", change)
    with pytest.raises(VisualPackError, match=reason):
        load_visual_pack(pack_dir, model_root)


def test_pack_rejects_digest_model_and_path_problems(tmp_path: Path) -> None:
    pack_dir, model_root = make_pack(tmp_path)
    nod = pack_dir / "nod.motion3.json"
    original = nod.read_bytes()
    nod.write_bytes(original.replace(b"1.2", b"1.3", 1))
    with pytest.raises(VisualPackError, match="nod motion digest"):
        load_visual_pack(pack_dir, model_root)
    nod.write_bytes(original)

    moc = next(model_root.rglob("*.moc3"))
    moc.write_bytes(b"different model")
    with pytest.raises(VisualPackError, match="does not match the pack"):
        load_visual_pack(pack_dir, model_root)

    pack_dir, model_root = make_pack(tmp_path / "again")
    edit_pack(
        pack_dir,
        lambda pack: pack["activities"][0].update(file="../idle.motion3.json"),
    )
    with pytest.raises(VisualPackError, match="plain motion3 file name"):
        load_visual_pack(pack_dir, model_root)

    pack_dir, model_root = make_pack(tmp_path / "escape")
    edit_pack(pack_dir, lambda pack: pack.update(compatibility={"../outside.moc3": "0" * 64}))
    with pytest.raises(VisualPackError, match="escapes"):
        load_visual_pack(pack_dir, model_root)

    pack_dir, model_root = make_pack(tmp_path / "noidle")
    edit_pack(
        pack_dir,
        lambda pack: pack.update(
            activities=[item for item in pack["activities"] if item["activity"] != "idle"]
        ),
    )
    with pytest.raises(VisualPackError, match="idle resting activity"):
        load_visual_pack(pack_dir, model_root)


def test_symlinked_motion_is_not_followed(tmp_path: Path) -> None:
    pack_dir, model_root = make_pack(tmp_path)
    nod = pack_dir / "nod.motion3.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(nod.read_bytes())
    nod.unlink()
    nod.symlink_to(outside)
    with pytest.raises(VisualPackError, match="nod motion is missing"):
        load_visual_pack(pack_dir, model_root)


def run_controller(tmp_path: Path, checks: str) -> None:
    pack = load_visual_pack(*make_pack(tmp_path)).renderer_payload()
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps(pack))
    script = tmp_path / "controller_check.mjs"
    script.write_text(
        f"""
import assert from 'node:assert/strict';
import {{ readFileSync }} from 'node:fs';
import {{ SiroActivityController, BODY_IDS, evaluateCurve }} from {json.dumps(str(CONTROLLER))};
const pack = JSON.parse(readFileSync({json.dumps(str(payload))}, 'utf8'));
const DT = 1 / 60;
let events = [];
function make(has = () => true) {{
  const c = new SiroActivityController();
  c.onEvent = event => events.push(event);
  assert.equal(c.load(pack), null);
  c.bindModel(has);
  return c;
}}
// Stock motion rewrites every ID each frame before the overlay runs, like the SDK update.
function stage(stock = () => 3) {{
  const values = {{}}, writes = [];
  let time = 0;
  return {{
    values, writes,
    frame(c, dt = DT) {{
      time += dt;
      for (const id of [...BODY_IDS, 'ParamMouthOpenY']) values[id] = stock(id, time);
      c.tick(dt, id => values[id], (id, value) => {{ writes.push(id); values[id] = value; }});
      return {{...values}};
    }},
    run(c, seconds) {{
      const out = [];
      for (let i = 0; i < Math.round(seconds / DT); i++) out.push(this.frame(c));
      return out;
    }}
  }};
}}
const start = (activity, instance = 'i1', generation = 'g1', extra = {{}}) => ({{
  instance_id: instance, generation_id: generation, activity, pack_version: pack.version,
  op: 'start', ...extra
}});
const stop = (instance, generation) => ({{
  instance_id: instance, generation_id: generation, pack_version: pack.version, op: 'stop'
}});
const types = () => events.map(event => event.type);
{checks}
"""
    )
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_controller_transitions_start_from_the_current_pose_without_jumps(tmp_path: Path) -> None:
    run_controller(
        tmp_path,
        """
const c = make(), s = stage();
let frames = [s.frame(c)];
const steps = [['reading_pose', 1], ['attention', 1], ['nod', 2], ['speaking_pose', 1],
  ['reading_pose', 1]];
let n = 0;
for (const [activity, seconds] of steps) {
  const before = frames[frames.length - 1];
  c.request(start(activity, 'i' + (++n)));
  const after = s.frame(c);
  for (const id of BODY_IDS) {
    // First blended frame stays at the captured pose instead of snapping to clip(0) or default.
    assert.ok(Math.abs(after[id] - before[id]) < 0.15, `${activity} ${id} jumped`);
  }
  frames.push(after, ...s.run(c, seconds));
}
for (const id of BODY_IDS) {
  let worst = 0;
  for (let i = 1; i < frames.length; i++) {
    worst = Math.max(worst, Math.abs(frames[i][id] - frames[i - 1][id]));
  }
  assert.ok(worst < 1.0, `${id} per-frame delta ${worst}`);
}
assert.ok(new Set(s.writes).size === 6 && s.writes.every(id => BODY_IDS.includes(id)));
""",
    )


def test_controller_dedups_repeats_and_keeps_phase_for_new_owner(tmp_path: Path) -> None:
    run_controller(
        tmp_path,
        """
const c = make(), s = stage();
c.request(start('thinking'));
s.run(c, 0.5);
const phase = c.snapshot().phase;
events = [];
for (let i = 0; i < 20; i++) c.request(start('thinking'));
assert.deepEqual(types(), Array(20).fill('duplicate'));
assert.equal(c.snapshot().phase, phase);
events = [];
c.request(start('thinking', 'i2', 'g2'));
assert.equal(c.snapshot().phase, phase);
assert.deepEqual(events[0], {type: 'interrupted', instance_id: 'i1', generation_id: 'g1',
  activity: 'thinking', reason: 'superseded'});
events = [];
c.request(stop('i1', 'g1'));
assert.deepEqual(types(), ['ignored']);
assert.equal(c.snapshot().instance, 'i2');
""",
    )


def test_one_shot_nod_finishes_without_callbacks_and_resumes_saved_phase(tmp_path: Path) -> None:
    run_controller(
        tmp_path,
        """
const c = make(), s = stage();
c.request(start('thinking'));
s.run(c, 1.0);
const saved = c.snapshot().phase;
c.request(start('nod', 'n1'));
assert.equal(c.snapshot().activity, 'nod');
s.run(c, 1.2 + 2 * DT);
const finished = events.find(event => event.type === 'finished');
assert.equal(finished.activity, 'nod');
const now = c.snapshot();
assert.equal(now.activity, 'thinking');
assert.equal(now.instance, 'i1');
assert.ok(Math.abs(now.phase - saved) < 3 * DT, `resumed at ${now.phase}, saved ${saved}`);
""",
    )


def test_stop_rests_in_idle_then_releases_to_stock_motion(tmp_path: Path) -> None:
    run_controller(
        tmp_path,
        """
const c = make(), s = stage((id, time) => id === 'ParamAngleX' ? 5 * Math.sin(time) : 3);
c.request(start('reading_pose'));
s.run(c, 1);
c.request(stop('i1', 'g1'));
assert.equal(c.snapshot().activity, 'idle');
assert.equal(c.snapshot().instance, 'rest');
s.run(c, 1);
c.request(stop('rest', 'g1'));
assert.equal(c.snapshot().activity, null);
s.run(c, 0.4 + 2 * DT);
const writes = s.writes.length;
const frame = s.frame(c);
assert.equal(s.writes.length, writes);
assert.equal(c.snapshot().activity, null);
""",
    )


def test_unsupported_requests_keep_the_current_activity(tmp_path: Path) -> None:
    run_controller(
        tmp_path,
        """
const c = make(), s = stage();
c.request(start('thinking'));
s.run(c, 0.2);
events = [];
c.request(start('thinking', 'x', 'g', {pack_version: '9.9.9'}));
c.request(start('walk', 'x'));
assert.deepEqual(events.map(e => [e.type, e.reason]),
  [['unsupported', 'pack_version'], ['unsupported', 'activity']]);
assert.equal(c.snapshot().instance, 'i1');

events = [];
const missing = make(id => id !== 'ParamBodyAngleZ');
missing.request(start('idle'));
assert.deepEqual(events.map(e => [e.type, e.reason]), [['unsupported', 'parameters']]);
assert.equal(missing.snapshot().activity, null);

const broken = new SiroActivityController();
assert.equal(broken.load({...pack, schema: 'other'}), 'schema');
assert.equal(broken.request(start('idle')).reason, 'schema');
const absent = new SiroActivityController();
assert.equal(absent.load(null), 'no_pack');
assert.equal(absent.request(start('idle')).type, 'unsupported');
""",
    )


def test_speech_cancel_ends_only_the_speaking_pose(tmp_path: Path) -> None:
    run_controller(
        tmp_path,
        """
const c = make(), s = stage();
c.request(start('thinking'));
s.run(c, 0.3);
c.cancelSpeech();
assert.equal(c.snapshot().activity, 'thinking');
c.request(start('speaking_pose', 's1'));
s.run(c, 0.3);
c.cancelSpeech();
assert.equal(c.snapshot().activity, 'idle');
assert.equal(events.at(-1).reason, 'speech_cancelled');
c.request(start('speaking_pose', 's2'));
c.request(start('nod', 'n1'));
c.cancelSpeech();
assert.equal(c.snapshot().activity, 'nod');
s.run(c, 1.4);
assert.equal(c.snapshot().activity, 'idle');
""",
    )


def test_intents_wait_for_pack_and_model_and_ttl_expires(tmp_path: Path) -> None:
    run_controller(
        tmp_path,
        """
const c = new SiroActivityController();
c.onEvent = event => events.push(event);
c.request(start('thinking', 'a'));
c.request(start('attention', 'b'));
assert.deepEqual(events.map(e => [e.type, e.instance_id, e.reason]),
  [['accepted', 'a', 'not_ready'], ['interrupted', 'a', 'superseded'],
   ['accepted', 'b', 'not_ready']]);
assert.equal(c.load(pack), null);
assert.equal(c.snapshot().activity, null);
c.bindModel(() => true);
assert.equal(c.snapshot().activity, 'attention');

const t = make(), s = stage();
t.request(start('speaking_pose', 'sp', 'g', {ttl_s: 0.5}));
s.run(t, 0.4);
assert.equal(t.snapshot().activity, 'speaking_pose');
s.run(t, 0.2);
assert.equal(t.snapshot().activity, 'idle');
assert.ok(events.some(e => e.type === 'interrupted' && e.reason === 'expired'));
""",
    )


def test_curve_evaluation_matches_motion3_segment_types(tmp_path: Path) -> None:
    run_controller(
        tmp_path,
        """
assert.equal(evaluateCurve([0, 0, 0, 1, 10], 0.5), 5);
assert.equal(evaluateCurve([0, 0, 2, 1, 10], 0.5), 0);
assert.equal(evaluateCurve([0, 0, 3, 1, 10], 0.5), 10);
assert.equal(evaluateCurve([0, 0, 1, 1/3, 0, 2/3, 6, 1, 6], 0.5), 3);
assert.equal(evaluateCurve([0, 0, 0, 1, 10], 2), 10);
for (const clip of Object.values(pack.activities)) {
  if (!clip.loop) continue;
  for (const id of BODY_IDS) {
    const curve = clip.curves[id];
    assert.ok(Math.abs(evaluateCurve(curve, 0) - evaluateCurve(curve, clip.duration)) < 1e-9);
  }
}
""",
    )


def load_repair() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "p01_repair", "scripts/repair_companion_renderer.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bridge_releases_the_mouth_after_cancel_and_on_new_speech(tmp_path: Path) -> None:
    """V01-D01: cancel used to pin ParamMouthOpenY at 0 for every later speech."""
    bridge = re.search(
        r"// SIRO activity bridge v1.*?// End SIRO activity bridge v1\n",
        load_repair().ACTIVITY_BRIDGE,
        flags=re.S,
    )
    assert bridge
    script = tmp_path / "bridge_check.ts"
    script.write_text(
        """
import assert from 'node:assert/strict';
type ActivityIntent = Record<string, unknown>;
const mouth: (number | null)[] = [], posted: unknown[] = [], looks: number[][] = [];
const timers = new Map<number, () => void>();
let sequence = 0, desiredEmotion = 'neutral';
const manager = {setSiroMouthOpen: (value: number | null) => { mouth.push(value); },
  onDrag: (x: number, y: number) => { looks.push([x, y]); }};
const LAppDelegate = {getInstance: () => ({getSiroManager: () => manager})};
const window = {
  setTimeout: (fn: () => void) => { timers.set(++sequence, fn); return sequence; },
  clearTimeout: (id: number) => { timers.delete(id); },
  parent: {postMessage: (message: unknown) => { posted.push(message); }}
};
const location = {origin: 'http://localhost'};
const document = {documentElement: {dataset: {} as Record<string, string>}};
const fetch = async () => ({ok: false, json: async () => null});
const siroActivity = {
  cancelled: 0, requests: [] as unknown[], onEvent: (_event: unknown) => {},
  cancelSpeech() { this.cancelled++; }, request(message: unknown) { this.requests.push(message); },
  snapshot: () => ({activity: null}), load: (pack: unknown) => (pack ? null : 'no_pack')
};
"""
        + bridge.group(0)
        + """
renderSiro({v: 1, type: 'body.cancel', generation_id: 'active'});
assert.deepEqual(mouth, [null]);
assert.equal(siroActivity.cancelled, 1);
renderSiro({v: 1, type: 'body.speech', generation_id: 'g2', text: 'hi'});
assert.deepEqual(mouth, [null, null]);
assert.equal(timers.size, 0);
renderSiro({v: 1, type: 'body.activity', op: 'start', activity: 'nod'});
renderSiro({v: 2, type: 'body.activity', op: 'start', activity: 'nod'});
assert.equal(siroActivity.requests.length, 1);
renderSiro({v: 1, type: 'body.emotion', name: 'angry'});
assert.equal(desiredEmotion, 'angry');
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
assert.equal(document.documentElement.dataset.siroPack, 'unsupported:no_pack');
"""
    )
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stderr + result.stdout
