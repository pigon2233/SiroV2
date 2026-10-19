// SIRO VRM renderer: presentation only. It follows the same body.v1 boundary and
// renderer-ownership rules as the Live2D renderer and never owns speech audio.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import {
  VRMAnimationLoaderPlugin,
  VRMLookAtQuaternionProxy,
  createVRMAnimationClip,
} from '@pixiv/three-vrm-animation';

const MODEL_URL = '/vrm-model/model.vrm';
const PACK_URL = './motions/pack.json';
const CROSSFADE = 0.35;
// A new emotion gets one body reaction as it arrives, scaled by how strongly it is felt: tiers of
// [minimum intensity, clips to try]. Core maps plain interest to surprised as well, so only a
// strong one startles her; anger shows in the face and the idle loop, not a one-shot.
const EMOTION_GESTURES = {
  happy: [[0.6, ['clap', 'nod']], [0.35, ['nod']]],
  surprised: [[0.6, ['attention']]],
  sad: [[0.3, ['sigh']]],
};
// While an emotion holds at least this strongly, its idle_EMOTION loop replaces the idle. Core
// never sends relaxed: that loop is hers when it has been calm for a while or late in the evening.
const MOOD_IDLE_INTENSITY = 0.45;
const CALM_SECONDS = 180;
// With no word from Core for this long, an emotion fades back to neutral.
const EMOTION_FADE_SECONDS = 120;
// How each emotion carries the head, the chest and the eyes, blended by how strongly it shows.
// pitch: head down (+) or up (-), tilt: head roll, chest: slump (+), gaze: eyes lowered (+), all
// in degrees; away: chance a glance leaves the viewer; pace: speed and size of idle motion;
// blink: blink rate.
const STYLE = {
  neutral: { pitch: 0, tilt: 0, chest: 0, gaze: 0, away: 0.6, pace: 1, blink: 1 },
  happy: { pitch: -2, tilt: 4, chest: -1, gaze: -1, away: 0.45, pace: 1.35, blink: 1.1 },
  sad: { pitch: 9, tilt: 3, chest: 4, gaze: 10, away: 0.85, pace: 0.55, blink: 0.7 },
  angry: { pitch: 4, tilt: -1, chest: -1, gaze: -2, away: 0.2, pace: 0.8, blink: 0.6 },
  surprised: { pitch: -4, tilt: 0, chest: -2, gaze: -2, away: 0.1, pace: 1.2, blink: 0.35 },
  relaxed: { pitch: -1, tilt: 5, chest: 0, gaze: 1, away: 0.5, pace: 0.65, blink: 0.75 },
};
// VRoid exports map a 90-degree look onto the eyes' whole range, so glances and saccades of a few
// degrees barely move them and the stare looks fixed. Reach the full range much sooner.
const EYE_RANGE = { horizontal: 28, vertical: 22 };
// Bones whose highest reach in any clip the camera keeps in frame, so a raised hand is not cut off.
const REACH_BONES = [
  'head', 'leftHand', 'rightHand', 'leftMiddleDistal', 'rightMiddleDistal', 'leftIndexDistal',
  'rightIndexDistal', 'leftLittleDistal', 'rightLittleDistal', 'leftThumbDistal', 'rightThumbDistal',
];
const REACH_MARGIN = 0.045; // metres past the last finger joint: the fingertip and its skin
// Left alone for this long, she finds something to do now and then (fixes her hair, hums, looks
// around, reads her notebook, stretches, yawns at night); after a long quiet she sits down.
const BORED_SECONDS = 20;
const SETTLE_SECONDS = 240;
// Held states: an entry clip, a loop held for a while, and an exit clip back to the idle.
const HOLDS = {
  sit: ['sit_down', 'sit_loop', 'stand_up'],
  notebook: ['notebook_out', 'notebook_read', 'notebook_away'],
};
const NOTEBOOK_SECONDS = 25;
// Hand gestures she makes now and then while talking, never the same twice in a row.
const TALK_GESTURES = ['talk_offer', 'talk_both', 'talk_explain', 'talk_self'];
// Faces that belong to some clips, as [from, to, weight] in seconds into the clip.
const GESTURE_FACES = {
  yawn: { aa: [0.5, 2.4, 0.7], blink: [0.6, 2.3, 1] },
  stretch: { blink: [0.9, 2.1, 0.85], aa: [1.0, 2.0, 0.2] },
  sigh: { relaxed: [0.2, 2.8, 0.6], blink: [1.2, 2.4, 0.6] },
  clap: { happy: [0, 2.2, 0.8] },
  pat: { happy: [0, 2.4, 1], blink: [0.3, 2.2, 0.9] },
  poke: { surprised: [0, 0.7, 0.8] },
  land: { surprised: [0, 0.35, 0.5], relaxed: [0.4, 1.3, 0.5] },
  hum: { happy: [0.4, 3.8, 0.45], blink: [0.7, 3.6, 0.75] },
  fix_hair: { happy: [0.3, 2.4, 0.25] },
};
// Speech cues for a body gesture. Greetings and answers count only at the start of a reply,
// farewells and thanks also at the end. One gesture per reply, and only from the idle loop.
const SPEECH_GESTURES = [
  ['bye', /(再見|掰掰|拜拜|晚安|下次見|明天見|\bbye\b|see you|good ?night)/i, 'both'],
  ['wave', /^(你好|您好|嗨|哈囉|早安|午安|早啊|hello|hi\b|hey\b|good morning)/i, 'head'],
  ['bow', /(謝謝|感謝|多謝|抱歉|對不起|不好意思|請多指教|thank|sorry)/i, 'both'],
  ['shake', /^(不是|不對|不行|不可以|不會吧|才不|no\b|nope)/i, 'head'],
  ['think', /^(嗯+|讓我想想|我想想|想一下|這個嘛|hmm+|let me think)/i, 'head'],
  ['nod', /^(對|是的|沒錯|好啊|好的|當然|可以|yes\b|sure\b|ok\b|okay\b)/i, 'head'],
];
// Manual menu (right click on the character); sit holds for a while, then stands up.
const MENU_GESTURES = [
  ['wave', '揮手'], ['bow', '鞠躬'], ['bye', '掰掰'], ['nod', '點頭'],
  ['shake', '搖頭'], ['think', '思考'], ['attention', '注意'], ['sit', '坐下'],
  ['clap', '拍手'], ['stretch', '伸懶腰'], ['hum', '哼歌'], ['notebook', '看筆記'],
];
const SIT_SECONDS = 8;
const desktop = new URLSearchParams(location.search).get('presentation') === 'desktop';
const statusLine = document.querySelector('#status');
const EMOTIONS = ['happy', 'sad', 'angry', 'surprised', 'relaxed'];
const LOOK_HOLD_SECONDS = 4;

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
// Supersample at least 2x: the character is small in the stage card and blurs at 1x.
renderer.setPixelRatio(Math.min(Math.max(window.devicePixelRatio || 1, 2), 3));
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(24, 1, 0.05, 30);
const keyLight = new THREE.DirectionalLight(0xffffff, Math.PI * 0.9);
keyLight.position.set(1, 1.6, 2.2);
scene.add(keyLight, new THREE.AmbientLight(0xffffff, 0.7));
const lookTarget = new THREE.Object3D();
scene.add(lookTarget);

let vrm;
let modelBox;
let desiredEmotion = 'neutral';
let desiredIntensity = 1;
let lastAnnounced = '';
let lookUntil = 0;
let gestureStart = -1;
let speechGeneration;
let hold = null; // the held state she is in: { kind, until, auto }
let nextBlink = 2;
let blinkStart = -1;
let elapsed = 0;
let frames = 0;
let mixer;
let idleAction;
let currentAction;
const actions = {};
const looping = new Set();
const emotionWeights = Object.fromEntries(EMOTIONS.map(name => [name, 0]));
// The same blend for the body, kept even when the model lacks that expression.
const moodWeights = Object.fromEntries(EMOTIONS.map(name => [name, 0]));
// A short-lived expression from an interaction (a pat, a poke) laid over the emotion from Core.
let reaction = null;
// The face of the clip playing now, if it has one (a yawn opens the mouth and shuts the eyes).
let gestureFace = null;
// A point she is interested in (the pointer, the chat box) and until when; Core's body.look wins.
const interest = { point: new THREE.Vector3(), until: -1 };
let reach; // world-space box every clip's hands reach, for framing
const view = { centerY: 1, height: 2, width: 1 };
let lastActive = 0;
let lastEmotionAt = 0;
let nextIdleBehaviour = 90;
let nextTalkGesture = Infinity;
let lastTalkGesture = '';
// Mouth: the parent page owns speech audio and sends its loudness and tone on the playback clock
// (siro.speech.mouth). Nothing here invents mouth motion without heard audio.
const mouth = { level: 0, tone: 0.5, target: 0, targetTone: 0.5, at: -1, slow: 0, beat: 0, lastBeat: -1, voiced: -1, talk: 0 };
window.addEventListener('message', event => {
  if (event.origin !== location.origin || event.source !== window.parent) return;
  const data = event.data;
  if (data?.v !== 1) return;
  if (data.type === 'siro.speech.mouth') {
    const level = Number(data.level);
    const tone = Number(data.tone);
    mouth.target = Number.isFinite(level) ? Math.max(0, Math.min(1, level)) : 0;
    mouth.targetTone = Number.isFinite(tone) ? Math.max(0, Math.min(1, tone)) : 0.5;
    mouth.at = elapsed;
    if (mouth.target > 0.1) {
      // Starting to speak, she looks back at the person she is talking to.
      if (elapsed - mouth.voiced > 1.5) {
        life.glanceYaw = 0;
        life.glancePitch = 0;
        life.nextGlance = elapsed + 2;
        interest.until = -1;
      }
      mouth.voiced = elapsed;
      engage();
    }
  } else if (data.type === 'siro.view.focus') {
    // Something on the page worth a look (the chat box while you type), as an offset from the
    // centre of this frame in frame widths and heights.
    const x = Number(data.x);
    const y = Number(data.y);
    if (!Number.isFinite(x) || !Number.isFinite(y) || !vrm) return;
    const head = bone('head')?.getWorldPosition(new THREE.Vector3()) ?? new THREE.Vector3(0, 1.4, 0);
    interest.point.set(
      THREE.MathUtils.clamp(x, -3, 3) * view.width,
      view.centerY - THREE.MathUtils.clamp(y, -3, 3) * view.height,
      head.z + 0.8,
    );
    interest.until = elapsed + 1.6;
    engage();
  }
});

// Anything that engages her (Core, speech, the pointer) postpones her idle pastimes.
function engage() {
  lastActive = elapsed;
  if (nextIdleBehaviour < elapsed + 20) nextIdleBehaviour = elapsed + 20;
  // If she sat down or got her notebook out on her own, she stops when you come back.
  if (hold?.auto && hold.until > elapsed + 1) hold.until = elapsed;
}

function fitCamera() {
  const width = window.innerWidth || 1;
  const height = window.innerHeight || 1;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  if (modelBox) {
    // Desktop shows the whole body; the stage card frames head to thigh below its title
    // overlay so the face stays legible. Both leave room for the highest reach of any clip (a
    // wave or a stretch above the head), so gestures are not cut off at the top of the window.
    // Frame from humanoid bones: the mesh bounding box of VRoid exports is much taller than
    // the body. VRM puts the feet on y = 0; anime heads reach about 1/3 of hips-to-head above it.
    const hips = bone('hips')?.getWorldPosition(new THREE.Vector3());
    const head = bone('head')?.getWorldPosition(new THREE.Vector3());
    const crown = hips && head ? head.y + (head.y - hips.y) * 0.34 : modelBox.max.y;
    let bottom = hips ? 0 : modelBox.min.y;
    if (!desktop && hips) bottom = hips.y - (crown - hips.y) * 0.5;
    const size = modelBox.getSize(new THREE.Vector3());
    const [headroom, share] = desktop ? [0.03, 0.94] : [0.2, 0.68];
    const below = 1 - share - headroom; // the gap under the framed body, as a share of the frame
    // A raised hand first uses the headroom above the hair (on the stage card, the band under its
    // title); only if it reaches higher than that does the frame grow, and then just enough.
    const handTop = reach ? reach.max.y + REACH_MARGIN : -Infinity;
    // Only height is reserved: arms swinging out sideways pass the edge for a moment at most, and
    // reserving that width in a narrow window would shrink her all the time.
    const visibleHeight = Math.max(
      (crown - bottom) / share,
      (handTop - bottom) / (1 - below - (desktop ? 0.01 : 0)),
      desktop ? 0 : (size.x * 0.75) / camera.aspect,
    );
    // The desktop pet stands on the window's bottom edge; the card keeps her head under its title.
    const centerY = desktop
      ? bottom - below * visibleHeight + visibleHeight / 2
      : Math.max(crown + headroom * visibleHeight, handTop) - visibleHeight / 2;
    const distance = visibleHeight / 2 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    camera.position.set(0, centerY, distance + size.z / 2);
    camera.lookAt(0, centerY, 0);
    Object.assign(view, { centerY, height: visibleHeight, width: visibleHeight * camera.aspect });
  }
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', fitCamera);

function bone(name) {
  return vrm?.humanoid?.getNormalizedBoneNode(name) ?? null;
}

function hasExpression(name) {
  return Boolean(vrm?.expressionManager?.getExpression(name));
}

// Fallback when the motion pack is unavailable: a still pose with breathing only.
function idlePose(time) {
  const breath = Math.sin(time * 1.6);
  bone('leftUpperArm')?.rotation.set(0, 0, THREE.MathUtils.degToRad(-72));
  bone('rightUpperArm')?.rotation.set(0, 0, THREE.MathUtils.degToRad(72));
  bone('leftLowerArm')?.rotation.set(0, THREE.MathUtils.degToRad(-8), 0);
  bone('rightLowerArm')?.rotation.set(0, THREE.MathUtils.degToRad(8), 0);
  bone('spine')?.rotation.set(THREE.MathUtils.degToRad(1.2 * breath), 0, 0);
  bone('chest')?.rotation.set(THREE.MathUtils.degToRad(0.8 * breath), 0, 0);
  let nod = 0;
  if (gestureStart >= 0) {
    const phase = (time - gestureStart) / 0.7;
    if (phase >= 1) gestureStart = -1;
    else nod = Math.sin(phase * Math.PI) * THREE.MathUtils.degToRad(12);
  }
  bone('neck')?.rotation.set(nod, THREE.MathUtils.degToRad(3 * Math.sin(time * 0.37)), 0);
}

const clamp01 = x => Math.max(0, Math.min(1, x));

function updateMouth(delta, manager) {
  if (elapsed - mouth.at > 0.25) mouth.target = 0; // the player stopped sending: close
  // Open fast, close a little slower, like a jaw.
  const rate = mouth.target > mouth.level ? 0.03 : 0.065;
  mouth.level += (mouth.target - mouth.level) * (1 - Math.exp(-delta / rate));
  mouth.tone += (mouth.targetTone - mouth.tone) * (1 - Math.exp(-delta / 0.06));
  // A stressed syllable (loudness jumping above its recent average) gives a small head beat.
  mouth.slow += (mouth.target - mouth.slow) * (1 - Math.exp(-delta / 0.3));
  if (mouth.target - mouth.slow > 0.28 && elapsed - mouth.lastBeat > 0.3) {
    mouth.beat = 1;
    mouth.lastBeat = elapsed;
  }
  mouth.beat *= Math.exp(-delta / 0.16);
  const speaking = elapsed - mouth.voiced < 0.6 ? 1 : 0;
  mouth.talk += (speaking - mouth.talk) * (1 - Math.exp(-delta / 0.35));
  const open = clamp01(mouth.level * 1.15);
  const t = mouth.tone;
  // Bright frames (high zero-crossing rate: i, e, s) narrow the mouth; dark ones round it. The
  // jaw (aa) always carries most of the opening; the vowel shapes only colour it.
  const shapes = {
    aa: Math.max(open * (0.6 + 0.4 * clamp01(1 - Math.abs(t - 0.5) * 1.6)), clipFace('aa')),
    ih: open * clamp01((t - 0.55) * 2.2) * 0.5,
    ou: open * clamp01((0.45 - t) * 2.2) * 0.5,
  };
  for (const [name, value] of Object.entries(shapes)) if (hasExpression(name)) manager.setValue(name, value);
}

// An interaction's expression: fades in fast, holds, and hands the face back to Core's emotion.
function react(name, intensity, seconds) {
  if (!EMOTIONS.includes(name)) return;
  const fresh = !reaction || reaction.name !== name || elapsed > reaction.end;
  reaction = { name, intensity, start: fresh ? elapsed : reaction.start, end: elapsed + seconds };
}

function reactionWeight() {
  if (!reaction) return 0;
  const w = Math.min(clamp01((elapsed - reaction.start) / 0.12), clamp01((reaction.end - elapsed) / 0.4));
  if (w <= 0 && elapsed > reaction.end) reaction = null;
  return w;
}

function clipFace(key) {
  if (!gestureFace) return 0;
  if (currentAction !== actions[gestureFace.name]) {
    gestureFace = null;
    return 0;
  }
  const span = gestureFace.face[key];
  if (!span) return 0;
  const t = elapsed - gestureFace.start;
  return span[2] * Math.min(clamp01((t - span[0]) / 0.25), clamp01((span[1] - t) / 0.3));
}

function moodTarget(name, r) {
  const own = name === desiredEmotion ? desiredIntensity : 0;
  return own * (1 - r) + (reaction && name === reaction.name ? reaction.intensity * r : 0);
}

// The body's style for the current blend of emotions.
const style = { ...STYLE.neutral };
function updateStyle() {
  Object.assign(style, STYLE.neutral);
  for (const name of EMOTIONS) {
    const w = moodWeights[name];
    if (!w || !STYLE[name]) continue;
    for (const key of Object.keys(style)) style[key] += (STYLE[name][key] - STYLE.neutral[key]) * w;
  }
}

function updateFace(delta) {
  const manager = vrm.expressionManager;
  const r = reactionWeight();
  const blend = 1 - Math.exp(-delta / 0.12);
  const slow = 1 - Math.exp(-delta / 0.5);
  for (const name of EMOTIONS) {
    const target = moodTarget(name, r);
    moodWeights[name] += (target - moodWeights[name]) * slow;
    if (!manager || !hasExpression(name)) continue;
    emotionWeights[name] += (Math.max(target, clipFace(name)) - emotionWeights[name]) * blend;
    manager.setValue(name, emotionWeights[name]);
  }
  updateStyle();
  if (!manager) return;
  if (hasExpression('blink')) {
    if (blinkStart < 0 && elapsed >= nextBlink) blinkStart = elapsed;
    let blink = 0;
    if (blinkStart >= 0) {
      const phase = (elapsed - blinkStart) / 0.16;
      if (phase >= 1) {
        blinkStart = -1;
        // Now and then a quick double blink; calm or sad eyes blink less often, startled ones hold.
        const rest = (2.5 + Math.random() * 3.5) / Math.max(0.2, style.blink);
        nextBlink = elapsed + (Math.random() < 0.12 ? 0.12 : rest);
      } else blink = Math.sin(phase * Math.PI);
    }
    // A smile already narrows the eyes; a full blink on top of it would squeeze them shut.
    blink = Math.max(blink * (1 - 0.5 * (emotionWeights.happy || 0)), clipFace('blink'));
    manager.setValue('blink', blink);
  }
  updateMouth(delta, manager);
}

// Procedural life layer, added on top of whatever clip the mixer wrote this frame. Clips loop
// exactly, so without it the character repeats the same 8 s forever; this adds what a loop
// cannot: eyes that glance first with the head following late, weight shifts at irregular
// intervals and low-frequency micro-motion that never repeats.
const life = {
  yaw: 0, yawV: 0, pitch: 0, pitchV: 0, shift: 0, shiftV: 0, shiftGoal: 0, standing: 1, standingV: 0,
  glanceYaw: 0, glancePitch: 0, nextGlance: 2.5, nextShift: 6, follow: 1, followV: 0,
  saccadeYaw: 0, saccadePitch: 0, nextSaccade: 1,
  pat: 0, patV: 0, patSide: 0, carried: 0, carriedV: 0,
  pitchPose: 0, pitchPoseV: 0, tiltPose: 0, tiltPoseV: 0, chestPose: 0, chestPoseV: 0,
};
const DEG = Math.PI / 180;
const lifeEuler = new THREE.Euler();
const lifeQuat = new THREE.Quaternion();
const headPos = new THREE.Vector3();
const gazeDir = new THREE.Vector3();
const headAhead = new THREE.Vector3();
const headTurn = new THREE.Quaternion();

// Critically damped spring toward a target (Game Programming Gems 4, 1.10).
function smoothDamp(key, target, time, delta) {
  const omega = 2 / time;
  const x = omega * delta;
  const decay = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
  const change = life[key] - target;
  const temp = (life[`${key}V`] + omega * change) * delta;
  life[`${key}V`] = (life[`${key}V`] - omega * temp) * decay;
  life[key] = target + (change + temp) * decay;
}

// Smooth 1D value noise in [-1, 1]; two octaves at unrelated rates never line up into a loop.
function hash(n) {
  const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return (s - Math.floor(s)) * 2 - 1;
}
function noise(seed, t) {
  const i = Math.floor(t);
  const f = t - i;
  const u = f * f * (3 - 2 * f);
  const a = hash(i + seed * 71.3);
  return a + (hash(i + 1 + seed * 71.3) - a) * u;
}
function drift(seed, t) {
  return noise(seed, t * 0.23) * 0.7 + noise(seed + 9, t * 0.61) * 0.3;
}

const LIFE_BONES = [
  'hips', 'spine', 'chest', 'neck', 'head', 'leftUpperArm', 'rightUpperArm',
  'leftLowerArm', 'rightLowerArm', 'leftLowerLeg', 'rightLowerLeg',
];
const lifeBase = new Map();
const hipsBase = new THREE.Vector3();

// The life layer adds to what the clips wrote, so each frame starts from the clips' pose again.
// The mixer only writes a bone when its clip value changes, so a held pose (a constant track)
// keeps whatever is left on the bone: restore what the clips last left, never zero it.
function restoreLifeBones() {
  for (const [name, quaternion] of lifeBase) bone(name)?.quaternion.copy(quaternion);
  if (lifeBase.size) bone('hips')?.position.copy(hipsBase);
}

function saveLifeBones() {
  for (const name of LIFE_BONES) {
    const node = bone(name);
    if (!node) continue;
    if (!lifeBase.has(name)) lifeBase.set(name, new THREE.Quaternion());
    lifeBase.get(name).copy(node.quaternion);
  }
  const hips = bone('hips');
  if (hips) hipsBase.copy(hips.position);
}

function turn(name, x, y, z) {
  const node = bone(name);
  if (!node) return;
  lifeQuat.setFromEuler(lifeEuler.set(x, y, z));
  node.quaternion.multiply(lifeQuat);
}

// Where she looks, by priority: a body.look from Core; then what her own body is doing (looking
// around: the eyes go with the head; reading: the notebook); then whatever interests her (the
// pointer, the chat box while you type); otherwise the viewer, with glances away whose size and
// direction follow her mood (sad eyes drop, angry ones hold) and saccades so the eyes never freeze.
function updateLife(delta) {
  if (!vrm) return;
  const free = elapsed > lookUntil;
  const leading = free && playing('look_around');
  const reading = free && notebook.visible && !playing('notebook_away');
  let focus = null;
  if (leading && bone('head')) {
    bone('head').getWorldQuaternion(headTurn);
    focus = bone('head').getWorldPosition(headAhead).add(gazeDir.set(0, -0.1, 2).applyQuaternion(headTurn));
  } else if (reading) focus = notebook.position;
  else if (free && elapsed < interest.until) focus = interest.point;
  const curious = Boolean(focus);
  const talking = mouth.talk > 0.5;
  if (free && !curious && elapsed >= life.nextGlance) {
    // Mostly back at the viewer; sometimes a glance away and back. Big glances often blink.
    // While speaking she mostly holds eye contact, with only brief, small glances.
    const away = life.glanceYaw === 0 && Math.random() < style.away * (talking ? 0.4 : 1);
    const size = (8 + Math.random() * 20) * (talking ? 0.5 : 1);
    life.glanceYaw = away ? (Math.random() < 0.5 ? -1 : 1) * size * DEG : 0;
    life.glancePitch = away ? (-8 + Math.random() * 14 - style.gaze) * DEG : 0;
    const stay = away ? 0.8 + Math.random() * 1.8 : 2.5 + Math.random() * 5;
    life.nextGlance = elapsed + stay / Math.max(0.4, style.pace);
    if (Math.abs(life.glanceYaw) > 15 * DEG && blinkStart < 0) nextBlink = elapsed;
  }
  bone('head')?.getWorldPosition(headPos);
  const target = !free ? lookTarget.position : focus ?? camera.position;
  gazeDir.subVectors(target, headPos);
  let yaw = Math.atan2(gazeDir.x, gazeDir.z);
  let pitch = Math.atan2(gazeDir.y, Math.hypot(gazeDir.x, gazeDir.z));
  // Facing the viewer, the head stays nearly level and the eyes alone find the lens below it; a
  // head bowed all the way to the camera reads as staring at the floor.
  let headPitch = curious || !free ? pitch : pitch * 0.35;
  if (free) {
    const glance = curious ? 0 : 1;
    yaw += life.glanceYaw * glance;
    pitch += life.glancePitch * glance - (curious ? 0 : style.gaze * 0.35 * DEG);
    headPitch += (life.glancePitch * glance - style.gaze * 0.2 * DEG);
    // Small saccades, like looking between someone's eyes and mouth; the eyes only, not the head.
    if (elapsed >= life.nextSaccade) {
      const size = THREE.MathUtils.clamp(style.pace, 0.5, 1.3);
      life.saccadeYaw = (Math.random() * 2 - 1) * 3.5 * size * DEG;
      life.saccadePitch = (Math.random() * 2 - 1) * 2.0 * size * DEG;
      life.nextSaccade = elapsed + (0.35 + Math.random() * 1.4) / Math.max(0.6, style.pace);
    }
    const eyeYaw = yaw + life.saccadeYaw;
    const eyePitch = pitch + life.saccadePitch;
    // Eyes lead: they jump to the glance now, the head arrives a few hundred ms later.
    const reach = gazeDir.length();
    lookTarget.position.set(
      headPos.x + Math.sin(eyeYaw) * Math.cos(eyePitch) * reach,
      headPos.y + Math.sin(eyePitch) * reach,
      headPos.z + Math.cos(eyeYaw) * Math.cos(eyePitch) * reach,
    );
  }
  smoothDamp('yaw', THREE.MathUtils.clamp(yaw, -35 * DEG, 35 * DEG), 0.35, delta);
  smoothDamp('pitch', THREE.MathUtils.clamp(headPitch, -20 * DEG, 15 * DEG), 0.4, delta);
  // Mood posture (degrees), interaction poses (0..1), all eased so nothing snaps.
  smoothDamp('pitchPose', style.pitch, 0.9, delta);
  smoothDamp('tiltPose', style.tilt, 0.9, delta);
  smoothDamp('chestPose', style.chest, 1.2, delta);
  // The pat clip has its own head dip; the lean toward the hand stays, smaller, on top of it.
  smoothDamp('pat', elapsed < pat.until ? (playing('pat') ? 0.4 : 1) : 0, 0.25, delta);
  smoothDamp('carried', carry.active && !playing('dangle') ? 1 : 0, 0.2, delta);

  if (elapsed >= life.nextShift) {
    life.shiftGoal = (Math.random() * 2 - 1) * (Math.abs(life.shiftGoal) > 0.4 ? 0.4 : 1);
    life.nextShift = elapsed + 5 + Math.random() * 9;
  }
  smoothDamp('shift', life.shiftGoal, 1.1, delta);
  // Weight shifts and torso drift only while standing in the idle loop, not mid-gesture or seated.
  smoothDamp('standing', currentAction === idleAction ? 1 : 0, 0.4, delta);
  // The fallback pose only resets some bones each frame; there the eyes glance but the body stays.
  if (!mixer) return;

  // Lively moods move faster and a little more, calm and sad ones slower and less.
  life.time = (life.time ?? 0) + delta * style.pace;
  const t = life.time;
  // The captured idle already shifts weight and breathes; keep the extra layer at half strength.
  const s = life.standing * 0.5 * THREE.MathUtils.clamp(style.pace, 0.6, 1.4);
  const shift = life.shift * s;
  // Head turn is shared down the chain so the neck never twists alone; pitch is nod-down positive.
  // With the chin in her hand (thinking) or a notebook in front of her mostly the eyes move; when
  // a clip turns the head itself (looking around) the life layer leaves it alone.
  const follow = leading ? 0 : playing('think') ? 0.35 : reading ? 0.3 : 1;
  smoothDamp('follow', follow, 0.3, delta);
  const yawTurn = life.yaw * life.follow;
  const pitchTurn = life.pitch * life.follow;
  turn('chest', 0, yawTurn * 0.12, 0);
  turn('neck', -pitchTurn * 0.4, yawTurn * 0.35, 0);
  turn('head', -pitchTurn * 0.5 + drift(1, t) * 1.5 * DEG, yawTurn * 0.45, drift(2, t) * 2.5 * DEG);
  // Speaking: a small nod on stressed syllables, livelier head motion and a slight lean in.
  const talk = mouth.talk;
  turn('neck', mouth.beat * 1.2 * DEG, 0, 0);
  turn('head', mouth.beat * 2.2 * DEG + talk * drift(14, t * 2.2) * 1.4 * DEG,
    talk * drift(15, t * 1.6) * 2.2 * DEG, talk * drift(16, t * 1.3) * 1.8 * DEG);
  turn('spine', talk * 1.2 * DEG, 0, 0);
  // Mood: a sad head hangs and the chest sinks, a happy one lifts and tilts, an angry chin drops.
  turn('chest', life.chestPose * 0.6 * DEG, 0, 0);
  turn('spine', life.chestPose * 0.4 * DEG, 0, 0);
  turn('neck', life.pitchPose * 0.4 * DEG, 0, 0);
  turn('head', life.pitchPose * 0.6 * DEG, 0, life.tiltPose * DEG);
  // A pat on the head: she leans into the hand, chin down, eyes closing in a smile.
  turn('neck', life.pat * 4 * DEG, 0, life.patSide * life.pat * 3 * DEG);
  turn('head', life.pat * 5 * DEG, 0, life.patSide * life.pat * 7 * DEG);
  // Picked up and carried by the window: she looks down, shoulders up.
  turn('neck', life.carried * 6 * DEG, 0, 0);
  turn('leftUpperArm', 0, 0, life.carried * 6 * DEG);
  turn('rightUpperArm', 0, 0, -life.carried * 6 * DEG);
  turn('hips', 0, drift(3, t) * 1.2 * DEG * s, shift * 2 * DEG);
  turn('spine', drift(4, t) * 1.0 * DEG * s, drift(5, t) * 1.5 * DEG * s, -shift * 1.6 * DEG);
  turn('chest', drift(6, t) * 0.8 * DEG * s, 0, -shift * 0.6 * DEG + drift(7, t) * 0.8 * DEG * s);
  turn('leftUpperArm', drift(8, t) * 2 * DEG * s, 0, drift(9, t) * 1.5 * DEG * s);
  turn('rightUpperArm', drift(10, t) * 2 * DEG * s, 0, drift(11, t) * 1.5 * DEG * s);
  turn('leftLowerArm', 0, drift(12, t) * 3 * DEG * s, 0);
  turn('rightLowerArm', 0, drift(13, t) * 3 * DEG * s, 0);
  // The free (left) knee eases as weight moves onto the right leg, and stiffens the other way.
  turn('leftLowerLeg', Math.max(0, -shift) * 5 * DEG, 0, 0);
  turn('rightLowerLeg', Math.max(0, shift) * 5 * DEG, 0, 0);
  const hips = bone('hips');
  if (hips) hips.position.x += shift * 0.012 * s;
}

function updateLook() {
  if (!vrm?.lookAt) return;
  vrm.lookAt.target = lookTarget;
}

function announceEmotion() {
  const settled = !hasExpression(desiredEmotion) || emotionWeights[desiredEmotion] > desiredIntensity * 0.6;
  if (!settled || lastAnnounced === desiredEmotion) return;
  document.documentElement.dataset.siroEmotion = desiredEmotion;
  window.parent.postMessage(
    { type: 'siro.renderer.ready', emotion: desiredEmotion, character: vrm.meta?.name || 'SIRO', renderer: 'VRM' },
    location.origin,
  );
  lastAnnounced = desiredEmotion;
}

const clock = new THREE.Clock();
let lastDesktopFrame = 0;
function loop(now) {
  requestAnimationFrame(loop);
  // SIRO desktop frame budget: retain normal web timing.
  if (desktop && now - lastDesktopFrame < 1000 / 24) return;
  lastDesktopFrame = now;
  const delta = Math.min(clock.getDelta(), 0.1);
  elapsed += delta;
  if (vrm) {
    if (mixer) {
      restoreLifeBones();
      mixer.update(delta);
      updateEmotionFade();
      updateHold();
      updateCarry();
      updateIdle();
      updateTalkGestures();
      updatePastimes();
      saveLifeBones();
    } else idlePose(elapsed);
    updateNotebook();
    updateLife(delta);
    updateFace(delta);
    updateLook();
    vrm.update(delta);
    announceEmotion();
  }
  renderer.render(scene, camera);
  frames += 1;
}

function renderSiro(message) {
  if (!message || message.v !== 1) return;
  engage();
  const previousEmotion = desiredEmotion;
  if (message.type === 'body.emotion') {
    const name = String(message.name);
    desiredEmotion = EMOTIONS.includes(name) ? name : 'neutral';
    const intensity = Number(message.intensity);
    desiredIntensity = Number.isFinite(intensity) ? Math.max(0, Math.min(1, intensity)) : 1;
    lastEmotionAt = elapsed;
  } else if (message.type === 'body.look' && vrm) {
    const x = Math.max(-1, Math.min(1, Number(message.x) || 0));
    const y = Math.max(-1, Math.min(1, Number(message.y) || 0));
    const head = bone('head')?.getWorldPosition(new THREE.Vector3()) ?? new THREE.Vector3(0, 1.4, 0);
    lookTarget.position.set(head.x + x * 0.8, head.y + y * 0.5, head.z + 1.2);
    lookUntil = elapsed + LOOK_HOLD_SECONDS;
  } else if (message.type === 'body.gesture') {
    if (!perform(String(message.name || 'nod'))) gestureStart = elapsed;
  } else if (message.type === 'body.speech') {
    const generation = String(message.generation_id ?? '');
    if (generation !== speechGeneration || !generation) {
      const gesture = speechGesture(String(message.text ?? ''));
      if (gesture && currentAction === idleAction && playGesture(gesture)) speechGeneration = generation;
    }
  }
  // A new emotion gets one body reaction as it arrives; the same emotion again stays quiet.
  if (message.type === 'body.emotion' && desiredEmotion !== previousEmotion) {
    const tier = (EMOTION_GESTURES[desiredEmotion] ?? []).find(([min]) => desiredIntensity >= min);
    const gesture = tier?.[1].find(name => actions[name]);
    if (gesture && currentAction === idleAction) playGesture(gesture);
  }
  // body.speech / body.cancel: audible speech has one owner in the parent page.
  // Never synthesize twice or fake lip motion here.
}

// SIRO renderer ownership v3 (same semantics as the Live2D bridge)
let siroDetached = false;
let siroRetryTimer;
let siroSocket;
function scheduleSiroReconnect() {
  if (!siroDetached && siroRetryTimer === undefined) {
    siroRetryTimer = window.setTimeout(() => {
      siroRetryTimer = undefined;
      void connectSiro();
    }, 1000);
  }
}
async function connectSiro() {
  if (siroDetached) return;
  try {
    const session = await fetch('/v1/session', { method: 'POST', headers: { Origin: location.origin } });
    if (!session.ok) throw new Error(`session ${session.status}`);
    const { token } = await session.json();
    if (siroDetached) return;
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${scheme}://${location.host}/ws/body`);
    siroSocket = socket;
    socket.addEventListener('open', () => {
      if (siroDetached || siroSocket !== socket) { socket.close(); return; }
      socket.send(JSON.stringify({ type: 'authenticate', token, ...(desktop ? { presentation: 'desktop' } : {}) }));
    });
    socket.addEventListener('message', event => {
      if (siroDetached || siroSocket !== socket) return;
      try { renderSiro(JSON.parse(event.data)); } catch (_) { /* ignore malformed frames */ }
    });
    socket.addEventListener('close', event => {
      if (siroSocket !== socket) return;
      siroSocket = undefined;
      if (event.reason === 'renderer replaced' || event.reason === 'desktop owner active') {
        siroDetached = true;
        if (siroRetryTimer !== undefined) window.clearTimeout(siroRetryTimer);
        siroRetryTimer = undefined;
        window.parent.postMessage({ type: 'siro.renderer.detached' }, location.origin);
      } else scheduleSiroReconnect();
    });
  } catch (_) {
    scheduleSiroReconnect();
  }
}
window.addEventListener('pagehide', () => {
  siroDetached = true;
  if (siroRetryTimer !== undefined) window.clearTimeout(siroRetryTimer);
  siroRetryTimer = undefined;
  siroSocket?.close();
});
// End SIRO renderer ownership v3

// SIRO desktop click-to-chat: only the displayed local character initiates this UI action.
let desktopPress;
window.addEventListener('pointerdown', event => {
  if (desktop && event.button === 0) desktopPress = { x: event.screenX, y: event.screenY };
});
window.addEventListener('pointerup', event => {
  const press = desktopPress;
  desktopPress = undefined;
  if (press && Math.hypot(event.screenX - press.x, event.screenY - press.y) < 8)
    window.parent.postMessage({ type: 'siro.renderer.interact' }, location.origin);
});

// ---- Interaction layer: the pointer on the character (presentation only; Core is not told) ----
// Her eyes follow the pointer while it moves over her. Stroking her head, or clicking it, is a
// pat: she dips into the hand with her eyes shut, smiling. A click on her body gets a smile; a
// second one is a poke (she jumps back, then looks at you); a fourth makes her pout and shake her
// head. Dragging the desktop window picks her up: she dangles until she is set down, then lands.
const pat = { until: -1, strokes: [], lastX: null, direction: 0, travel: 0 };
const carry = { active: false, since: 0, lastMove: 0, x: 0, y: 0, moved: false, touched: -1 };
let pokes = [];
let press;
const screenPoint = new THREE.Vector3();
const rayPoint = new THREE.Vector3();

// The pointer as a point in the scene, on a plane just in front of her face.
function pointerPoint(event, target) {
  const head = bone('head')?.getWorldPosition(screenPoint) ?? screenPoint.set(0, 1.4, 0);
  const planeZ = head.z + 0.6;
  rayPoint.set((event.clientX / (window.innerWidth || 1)) * 2 - 1, 1 - (event.clientY / (window.innerHeight || 1)) * 2, 0.5)
    .unproject(camera).sub(camera.position).normalize();
  if (Math.abs(rayPoint.z) < 1e-6) return null;
  return target.copy(camera.position).addScaledVector(rayPoint, (planeZ - camera.position.z) / rayPoint.z);
}

// Where her head is on screen (pixels) and roughly how big, for pats and clicks on the head.
function headOnScreen() {
  const head = bone('head');
  if (!head) return null;
  const centre = head.localToWorld(screenPoint.set(0, 0.08, 0)).project(camera);
  const top = head.localToWorld(rayPoint.set(0, 0.2, 0)).project(camera);
  const w = window.innerWidth || 1;
  const h = window.innerHeight || 1;
  const x = (centre.x + 1) / 2 * w;
  const y = (1 - centre.y) / 2 * h;
  return { x, y, radius: Math.max(12, Math.abs((1 - top.y) / 2 * h - y) * 1.15) };
}

function onHead(event) {
  const head = headOnScreen();
  return Boolean(head && Math.hypot(event.clientX - head.x, event.clientY - head.y) < head.radius);
}

window.addEventListener('pointermove', event => {
  if (!vrm || !gestureMenu.hidden) return;
  engage();
  // Hovering again after a drag means she has been put down; moves with the button held do not.
  if (carry.active && !(event.buttons & 1)) carry.touched = elapsed;
  if (press && event.buttons & 1) {
    // The desktop host starts moving the window past the same 7-pixel threshold.
    if (desktop && Math.hypot(event.screenX - press.x, event.screenY - press.y) >= 7) startCarry();
    return;
  }
  if (pointerPoint(event, interest.point)) interest.until = elapsed + 1.2;
  // A pat: the pointer sweeping back and forth over her head.
  if (!onHead(event)) {
    pat.lastX = null;
    return;
  }
  if (pat.lastX !== null) {
    const dx = event.clientX - pat.lastX;
    if (Math.sign(dx) && Math.sign(dx) !== pat.direction) {
      if (pat.travel > 6) pat.strokes.push(elapsed);
      pat.direction = Math.sign(dx);
      pat.travel = 0;
    }
    pat.travel += Math.abs(dx);
  }
  pat.lastX = event.clientX;
  pat.strokes = pat.strokes.filter(time => elapsed - time < 1.6);
  if (pat.strokes.length >= 3) patted(event);
});

function patted(event) {
  const head = headOnScreen();
  // She tilts her head toward the hand.
  if (head) life.patSide = THREE.MathUtils.clamp((head.x - event.clientX) / head.radius, -1, 1);
  pat.until = elapsed + 1.2;
  react('happy', 1, 1.8);
  interest.until = -1;
  if (currentAction === idleAction) playGesture('pat');
}

window.addEventListener('pointerdown', event => {
  if (carry.active) carry.touched = elapsed;
  if (event.button !== 0 || !vrm || !gestureMenu.hidden) return;
  press = { x: event.screenX, y: event.screenY };
});

window.addEventListener('pointerup', event => {
  if (carry.active) carry.touched = elapsed;
  const down = press;
  press = undefined;
  if (event.button !== 0 || !down || !vrm || Math.hypot(event.screenX - down.x, event.screenY - down.y) >= 7) return;
  engage();
  // Eye contact for whoever clicked.
  interest.until = -1;
  life.glanceYaw = 0;
  life.glancePitch = 0;
  life.nextGlance = elapsed + 2.5;
  if (onHead(event)) {
    patted(event);
    return;
  }
  pokes = pokes.filter(time => elapsed - time < 2.5);
  pokes.push(elapsed);
  if (pokes.length >= 4) {
    pokes = [];
    react('angry', 0.65, 2.2);
    if (currentAction === idleAction || playing('poke')) playGesture('shake');
  } else if (pokes.length >= 2) {
    // Poked: she jumps back, then looks at where it came from.
    react('surprised', 0.6, 0.7);
    if (currentAction === idleAction) playGesture('poke');
    if (pointerPoint(event, interest.point)) interest.until = elapsed + 1.4;
  } else react('happy', 0.45, 1.4);
});

// Picked up: the window is being dragged. She dangles until it stops moving (or the pointer
// comes back after the drag), then lands on her feet.
function startCarry() {
  if (carry.active) return;
  Object.assign(carry, {
    active: true, since: elapsed, lastMove: elapsed, x: window.screenX, y: window.screenY, moved: false, touched: -1,
  });
  react('surprised', 0.7, 1.4);
  hold = null;
  if (mixer && actions.dangle) playLoop('dangle', 0.25);
}

function updateCarry() {
  if (!carry.active) return;
  if (window.screenX !== carry.x || window.screenY !== carry.y) {
    Object.assign(carry, { x: window.screenX, y: window.screenY, moved: true, lastMove: elapsed });
  }
  const settled = carry.moved && elapsed - carry.lastMove > 0.4;
  const back = carry.touched > carry.since + 0.5;
  if (!settled && !back && elapsed - carry.since < 8) return;
  carry.active = false;
  if (playing('dangle') && !playGesture('land')) returnToIdle(currentAction);
}

// ---- Pastimes: left alone she does small things now and then; after a long quiet she sits
// down until someone comes back. Never while talking, mid-gesture or held up.
function updatePastimes() {
  if (!mixer || elapsed < nextIdleBehaviour) return;
  nextIdleBehaviour = elapsed + 20 + Math.random() * 40;
  const quiet = elapsed - lastActive;
  if (quiet < BORED_SECONDS || currentAction !== idleAction || mouth.talk > 0.1 || hold || carry.active) return;
  const choices = [];
  const add = (name, weight) => { for (let i = 0; i < weight; i++) choices.push(name); };
  const hour = clockHour();
  if (quiet > SETTLE_SECONDS && actions.sit_down && actions.sit_loop) add('sit', 3);
  if (actions.yawn) add('yawn', hour >= 23 || hour < 5 ? 4 : 0);
  for (const name of ['fix_hair', 'hum', 'look_around']) if (actions[name]) add(name, 2);
  if (actions.stretch) add('stretch', 1);
  if (actions.notebook_out && actions.notebook_read) add('notebook', 1);
  if (!actions.look_around) add('look', 2);
  const choice = choices[Math.floor(Math.random() * choices.length)];
  if (choice === 'sit') startHold('sit', 40 + Math.random() * 50, true);
  else if (choice === 'notebook') startHold('notebook', 20 + Math.random() * 20, true);
  else if (choice === 'look') {
    // A slow look to one side and back, as if something caught her eye.
    life.glanceYaw = (Math.random() < 0.5 ? -1 : 1) * (22 + Math.random() * 10) * DEG;
    life.glancePitch = (Math.random() * 10 - 4) * DEG;
    life.nextGlance = elapsed + 1.8 + Math.random() * 1.5;
  } else playGesture(choice);
}

// The local hour, read at most every half minute.
let hourReadAt = -Infinity;
let hourNow = 12;
function clockHour() {
  if (elapsed - hourReadAt > 30) {
    hourNow = new Date().getHours();
    hourReadAt = elapsed;
  }
  return hourNow;
}

// Talking: now and then a hand gesture, less often when her arms are folded or clasped.
function updateTalkGestures() {
  if (mouth.talk < 0.5) {
    nextTalkGesture = Infinity;
    return;
  }
  if (nextTalkGesture === Infinity) nextTalkGesture = elapsed + 2 + Math.random() * 2.5;
  if (elapsed < nextTalkGesture) return;
  const armsBusy = [actions.idle_angry, actions.idle_happy].some(action => action && action === idleAction);
  nextTalkGesture = elapsed + (4 + Math.random() * 3) * (armsBusy ? 2 : 1);
  if (currentAction !== idleAction || hold) return;
  const options = TALK_GESTURES.filter(name => actions[name] && name !== lastTalkGesture);
  if (!options.length) return;
  lastTalkGesture = options[Math.floor(Math.random() * options.length)];
  playGesture(lastTalkGesture);
}

// While an emotion holds strongly enough, its own idle loop (idle_happy, idle_sad...) replaces
// the plain one; when all has been calm for a while, or late in the evening, she relaxes.
function updateIdle() {
  const hour = clockHour();
  const quiet = elapsed - lastActive;
  const calm = desiredEmotion === 'neutral' && (quiet > CALM_SECONDS || ((hour >= 22 || hour < 5) && quiet > 45));
  const wanted = (desiredIntensity >= MOOD_IDLE_INTENSITY && actions[`idle_${desiredEmotion}`])
    || (calm && actions.idle_relaxed) || actions.idle;
  if (!wanted || wanted === idleAction) return;
  const previous = idleAction;
  idleAction = wanted;
  if (currentAction !== previous) return; // a gesture is playing; it hands back to the new idle
  wanted.reset().play();
  previous.crossFadeTo(wanted, 0.8, false);
  currentAction = wanted;
}

// Core sends an emotion with each turn; without one for a while, she settles back to neutral.
function updateEmotionFade() {
  if (desiredEmotion === 'neutral' || elapsed - lastEmotionAt < EMOTION_FADE_SECONDS) return;
  desiredEmotion = 'neutral';
  desiredIntensity = 1;
}

// ---- The notebook: a prop, not part of the model, placed on her palms each frame. It grows in
// as she brings it up (notebook_out) and shrinks away as she puts it down (notebook_away).
const notebook = new THREE.Group();
{
  const cover = new THREE.Mesh(new THREE.BoxGeometry(0.15, 0.012, 0.21), new THREE.MeshLambertMaterial({ color: 0x26305a }));
  const pages = new THREE.Mesh(new THREE.BoxGeometry(0.142, 0.006, 0.202), new THREE.MeshLambertMaterial({ color: 0xf7f4ec }));
  pages.position.y = 0.008;
  notebook.add(cover, pages);
  notebook.visible = false;
  scene.add(notebook);
}
const leftPalm = new THREE.Vector3();
const rightPalm = new THREE.Vector3();
const chestTurn = new THREE.Quaternion();
const chestEuler = new THREE.Euler(0, 0, 0, 'YXZ');

function updateNotebook() {
  let size = 0;
  if (playing('notebook_read')) size = 1;
  else if (playing('notebook_out')) size = clamp01((actions.notebook_out.time - 0.3) / 0.6);
  else if (playing('notebook_away')) size = 1 - clamp01((actions.notebook_away.time - 0.1) / 0.5);
  const left = bone('leftHand');
  const right = bone('rightHand');
  notebook.visible = size > 0.01 && Boolean(left && right);
  if (!notebook.visible) return;
  left.getWorldPosition(leftPalm);
  right.getWorldPosition(rightPalm);
  // The hand bones sit at the wrists; the palms are a hand's length further out. Rest it on them.
  bone('chest')?.getWorldQuaternion(chestTurn);
  chestEuler.setFromQuaternion(chestTurn, 'YXZ');
  notebook.position.addVectors(leftPalm, rightPalm).multiplyScalar(0.5);
  notebook.position.x += Math.sin(chestEuler.y) * 0.07;
  notebook.position.z += Math.cos(chestEuler.y) * 0.07;
  notebook.position.y += 0.035;
  // Turned with her chest and tipped about 30 degrees toward her face.
  notebook.rotation.set(-30 * DEG, chestEuler.y, 0, 'YXZ');
  notebook.scale.setScalar(size);
}

// Read-only diagnostics for automated renderer checks.
window.__siroVrm = Object.freeze({
  loaded: () => Boolean(vrm),
  frames: () => frames,
  expression: name => vrm?.expressionManager?.getValue(name) ?? null,
  lookTarget: () => lookTarget.position.toArray(),
  neckPitch: () => bone('neck')?.rotation.x ?? null,
  bone: name => bone(name)?.quaternion.toArray() ?? null,
  eyes: () => (vrm?.lookAt ? [vrm.lookAt.yaw, vrm.lookAt.pitch] : null),
  reaction: () => (reaction && elapsed < reaction.end ? reaction.name : null),
  framing: () => ({ ...view, reachTop: reach?.max.y ?? null }),
  head: () => headOnScreen(),
  notebook: () => notebook.visible,
  activity: () => Object.keys(actions).find(name => actions[name] === currentAction) ?? null,
});

// Right click on the character opens a small gesture menu (manual testing and play).
const menuStyle = document.createElement('style');
menuStyle.textContent = `
#gesture-menu { position: fixed; display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
  padding: 6px; border-radius: 10px; background: rgba(28, 30, 44, 0.94);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35); z-index: 10; }
#gesture-menu[hidden] { display: none; }
#gesture-menu button { font: 13px system-ui, sans-serif; color: #eef1ff; background: #3a3d57;
  border: 0; border-radius: 6px; padding: 6px 12px; cursor: pointer; }
#gesture-menu button:hover { background: #565a80; }
#gesture-menu button:disabled { opacity: 0.4; cursor: default; }`;
document.head.append(menuStyle);
const gestureMenu = document.createElement('div');
gestureMenu.id = 'gesture-menu';
gestureMenu.hidden = true;
for (const [name, label] of MENU_GESTURES) {
  const item = document.createElement('button');
  item.type = 'button';
  item.textContent = label;
  item.dataset.gesture = name;
  item.addEventListener('pointerdown', event => event.stopPropagation());
  item.addEventListener('pointerup', event => event.stopPropagation());
  item.addEventListener('click', () => {
    gestureMenu.hidden = true;
    perform(name);
  });
  gestureMenu.append(item);
}
document.body.append(gestureMenu);
window.addEventListener('contextmenu', event => {
  event.preventDefault();
  if (!mixer) return;
  for (const item of gestureMenu.children) {
    const name = item.dataset.gesture;
    item.disabled = !(HOLDS[name] ? actions[HOLDS[name][0]] && actions[HOLDS[name][1]] : actions[name]);
  }
  gestureMenu.hidden = false;
  const x = Math.min(event.clientX, window.innerWidth - gestureMenu.offsetWidth - 4);
  const y = Math.min(event.clientY, window.innerHeight - gestureMenu.offsetHeight - 4);
  gestureMenu.style.left = `${Math.max(4, x)}px`;
  gestureMenu.style.top = `${Math.max(4, y)}px`;
});
window.addEventListener('pointerdown', event => {
  if (!gestureMenu.hidden && !gestureMenu.contains(event.target)) gestureMenu.hidden = true;
}, true);
window.addEventListener('keydown', event => {
  if (event.key === 'Escape') gestureMenu.hidden = true;
});

function speechGesture(text) {
  const clauses = text.trim().split(/[，。！？、,.!?~～…\n]+/).filter(Boolean);
  if (!clauses.length) return null;
  const head = clauses[0].trim();
  const tail = clauses[clauses.length - 1].trim();
  for (const [name, pattern, where] of SPEECH_GESTURES) {
    if (!actions[name]) continue;
    if (pattern.test(head) || (where === 'both' && pattern.test(tail))) return name;
  }
  return null;
}

// Held states (sitting, reading the notebook): the entry clip, its loop held for a while, then
// the exit clip back to the idle. `auto` marks one she started herself; she ends it when engaged.
function startHold(kind, seconds, auto = false) {
  const [enter, loop] = HOLDS[kind];
  if (!mixer || !actions[enter] || !actions[loop] || hold || carry.active) return false;
  hold = { kind, until: elapsed + actions[enter].getClip().duration + seconds, auto };
  if (playGesture(enter)) return true;
  hold = null;
  return false;
}

function updateHold() {
  if (!hold || elapsed < hold.until || currentAction !== actions[HOLDS[hold.kind][1]]) return;
  const exit = HOLDS[hold.kind][2];
  hold = null;
  if (!playGesture(exit)) returnToIdle(currentAction);
}

function returnToIdle(from) {
  idleAction.reset().play();
  from?.crossFadeTo(idleAction, CROSSFADE, false);
  currentAction = idleAction;
}

function playLoop(name, fade = CROSSFADE) {
  const action = actions[name];
  if (!action) return false;
  action.reset().setLoop(THREE.LoopRepeat, Infinity).play();
  currentAction?.crossFadeTo(action, fade, false);
  currentAction = action;
  gestureFace = null;
  return true;
}

function perform(name) {
  if (name === 'sit') return startHold('sit', SIT_SECONDS);
  if (name === 'notebook') return startHold('notebook', NOTEBOOK_SECONDS);
  if (hold) return false;
  return playGesture(name);
}

// Whether a clip the pack may or may not have is the one playing now.
function playing(name) {
  return Boolean(currentAction) && currentAction === actions[name];
}

// One-shot gestures cross-fade in over the idle loop and hand control back to it when done.
function playGesture(name) {
  const action = actions[name];
  if (!mixer || !action || looping.has(action)) return false;
  // Seated, reading or held up, other gestures wait until she is back on her feet.
  const steps = Object.values(HOLDS).flat();
  const busy = hold || playing('dangle')
    || Object.values(HOLDS).some(([enter, loop]) => playing(enter) || playing(loop));
  if (busy && !steps.includes(name) && name !== 'land') return false;
  if (currentAction === action && action.isRunning()) return true;
  action.reset().setLoop(THREE.LoopOnce, 1);
  action.clampWhenFinished = true;
  action.play();
  currentAction?.crossFadeTo(action, CROSSFADE, false);
  currentAction = action;
  gestureFace = GESTURE_FACES[name] ? { name, face: GESTURE_FACES[name], start: elapsed } : null;
  if (name === 'think') {
    // People look up and away while they think, and back once they have it.
    life.glanceYaw = (Math.random() < 0.5 ? -1 : 1) * (10 + Math.random() * 8) * DEG;
    life.glancePitch = (7 + Math.random() * 5) * DEG;
    life.nextGlance = elapsed + action.getClip().duration - 0.5;
  }
  return true;
}

// Sample every clip once on load and record how far the hands and head reach, so the camera can
// keep the whole range in frame (a wave above the head, a bow forward) instead of cutting it off.
function measureReach(mix) {
  const box = new THREE.Box3();
  const point = new THREE.Vector3();
  for (const action of Object.values(actions)) {
    const duration = action.getClip().duration;
    mix.stopAllAction();
    action.reset().setLoop(THREE.LoopOnce, 1).play();
    for (let i = 0, steps = Math.max(1, Math.ceil(duration * 15)); i <= steps; i++) {
      mix.setTime((duration * i) / steps);
      vrm.scene.updateMatrixWorld(true);
      for (const name of REACH_BONES) {
        const node = bone(name);
        if (node) box.expandByPoint(node.getWorldPosition(point));
      }
    }
  }
  mix.stopAllAction();
  // playGesture sets one-shots up itself; everything else loops as clipAction made it.
  for (const action of Object.values(actions)) action.reset().setLoop(THREE.LoopRepeat, Infinity);
  vrm.humanoid?.resetNormalizedPose();
  return box.isEmpty() ? null : box;
}

async function loadMotions(loader) {
  const response = await fetch(PACK_URL);
  if (!response.ok) throw new Error(`motion pack ${response.status}`);
  const pack = await response.json();
  const mix = new THREE.AnimationMixer(vrm.scene);
  if (vrm.lookAt) {
    const proxy = new VRMLookAtQuaternionProxy(vrm.lookAt);
    proxy.name = 'VRMLookAtQuaternionProxy';
    vrm.scene.add(proxy);
  }
  for (const item of pack.activities) {
    const gltf = await loader.loadAsync(new URL(item.file, new URL(PACK_URL, location.href)).href);
    const animation = gltf.userData.vrmAnimations?.[0];
    if (!animation) continue;
    const action = mix.clipAction(createVRMAnimationClip(animation, vrm));
    if (item.loop) looping.add(action);
    actions[item.activity] = action;
  }
  if (!actions.idle) throw new Error('motion pack has no idle loop');
  reach = measureReach(mix);
  mix.addEventListener('finished', event => {
    if (event.action !== currentAction || event.action === idleAction) return;
    if (hold && event.action === actions[HOLDS[hold.kind][0]]) {
      playLoop(HOLDS[hold.kind][1]);
      return;
    }
    returnToIdle(event.action);
  });
  idleAction = actions.idle;
  idleAction.play();
  currentAction = idleAction;
  mixer = mix;
  mixer.update(0);
}

async function loadModel() {
  const loader = new GLTFLoader();
  loader.register(parser => new VRMLoaderPlugin(parser));
  loader.register(parser => new VRMAnimationLoaderPlugin(parser));
  const gltf = await loader.loadAsync(MODEL_URL);
  const loaded = gltf.userData.vrm;
  if (!loaded) throw new Error('file is not a VRM model');
  VRMUtils.removeUnnecessaryVertices(gltf.scene);
  VRMUtils.rotateVRM0(loaded);
  scene.add(loaded.scene);
  vrm = loaded;
  const applier = vrm.lookAt?.applier;
  for (const [key, limit] of [
    ['rangeMapHorizontalInner', EYE_RANGE.horizontal], ['rangeMapHorizontalOuter', EYE_RANGE.horizontal],
    ['rangeMapVerticalDown', EYE_RANGE.vertical], ['rangeMapVerticalUp', EYE_RANGE.vertical],
  ]) {
    const map = applier?.[key];
    if (map && map.inputMaxValue > limit) map.inputMaxValue = limit;
  }
  try {
    await loadMotions(loader);
  } catch (error) {
    // The model still renders; it just stays in the procedural fallback pose.
    console.warn('SIRO motions unavailable:', error);
    idlePose(0);
  }
  vrm.update(0);
  modelBox = new THREE.Box3().setFromObject(vrm.scene);
  fitCamera();
  statusLine.textContent = '';
  document.documentElement.dataset.siroRenderer = 'vrm';
}

fitCamera();
requestAnimationFrame(loop);
loadModel()
  .then(() => connectSiro())
  .catch(() => {
    statusLine.textContent = '角色模型載入失敗。請確認 VRM 模型與 manifest。';
    document.documentElement.dataset.siroRendererError = 'model';
  });
