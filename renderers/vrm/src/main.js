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
// Emotions that also get a small body reaction; the face is driven separately.
const EMOTION_GESTURES = { happy: 'nod', surprised: 'attention' };
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
let sitUntil = -1;
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
// Mouth: the parent page owns speech audio and sends its loudness and tone on the playback clock
// (siro.speech.mouth). Nothing here invents mouth motion without heard audio.
const mouth = { level: 0, tone: 0.5, target: 0, targetTone: 0.5, at: -1, slow: 0, beat: 0, lastBeat: -1, voiced: -1, talk: 0 };
window.addEventListener('message', event => {
  if (event.origin !== location.origin || event.source !== window.parent) return;
  const data = event.data;
  if (data?.type !== 'siro.speech.mouth' || data.v !== 1) return;
  const level = Number(data.level);
  const tone = Number(data.tone);
  mouth.target = Number.isFinite(level) ? Math.max(0, Math.min(1, level)) : 0;
  mouth.targetTone = Number.isFinite(tone) ? Math.max(0, Math.min(1, tone)) : 0.5;
  mouth.at = elapsed;
  if (mouth.target > 0.1) mouth.voiced = elapsed;
});

function fitCamera() {
  const width = window.innerWidth || 1;
  const height = window.innerHeight || 1;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  if (modelBox) {
    // Desktop shows the whole body; the stage card frames head to thigh below its title
    // overlay so the face stays legible. Outstretched arms may be cropped by the card.
    // Frame from humanoid bones: the mesh bounding box of VRoid exports is much taller than
    // the body. VRM puts the feet on y = 0; anime heads reach about 1/3 of hips-to-head above it.
    const hips = bone('hips')?.getWorldPosition(new THREE.Vector3());
    const head = bone('head')?.getWorldPosition(new THREE.Vector3());
    const top = hips && head ? head.y + (head.y - hips.y) * 0.34 : modelBox.max.y;
    let bottom = hips ? 0 : modelBox.min.y;
    if (!desktop && hips) bottom = hips.y - (top - hips.y) * 0.5;
    const size = modelBox.getSize(new THREE.Vector3());
    const [headroom, share] = desktop ? [0.03, 0.94] : [0.2, 0.68];
    const widthLimit = desktop ? 0 : (size.x * 0.75) / camera.aspect;
    const visibleHeight = Math.max((top - bottom) / share, widthLimit);
    const centerY = top + headroom * visibleHeight - visibleHeight / 2;
    const distance = visibleHeight / 2 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    camera.position.set(0, centerY, distance + size.z / 2);
    camera.lookAt(0, centerY, 0);
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
  const open = mouth.level;
  const t = mouth.tone;
  // Bright frames (high zero-crossing rate: i, e, s) narrow the mouth; dark ones round it.
  const shapes = {
    aa: open * (0.35 + 0.65 * clamp01(1 - Math.abs(t - 0.5) * 1.6)),
    ih: open * clamp01((t - 0.55) * 2.2) * 0.7,
    ou: open * clamp01((0.45 - t) * 2.2) * 0.7,
  };
  for (const [name, value] of Object.entries(shapes)) if (hasExpression(name)) manager.setValue(name, value);
}

function updateFace(delta) {
  const manager = vrm.expressionManager;
  if (!manager) return;
  const blend = 1 - Math.exp(-delta / 0.12);
  for (const name of EMOTIONS) {
    if (!hasExpression(name)) continue;
    const target = name === desiredEmotion ? desiredIntensity : 0;
    emotionWeights[name] += (target - emotionWeights[name]) * blend;
    manager.setValue(name, emotionWeights[name]);
  }
  if (hasExpression('blink')) {
    if (blinkStart < 0 && elapsed >= nextBlink) blinkStart = elapsed;
    let blink = 0;
    if (blinkStart >= 0) {
      const phase = (elapsed - blinkStart) / 0.16;
      if (phase >= 1) {
        blinkStart = -1;
        nextBlink = elapsed + 2.5 + Math.random() * 3.5;
      } else blink = Math.sin(phase * Math.PI);
    }
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
  glanceYaw: 0, glancePitch: 0, nextGlance: 2.5, nextShift: 6,
};
const DEG = Math.PI / 180;
const lifeEuler = new THREE.Euler();
const lifeQuat = new THREE.Quaternion();
const headPos = new THREE.Vector3();
const gazeDir = new THREE.Vector3();

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
let restHips;

// Clips do not write every bone; reset the ones the life layer touches so it never accumulates.
function resetLifeBones() {
  for (const name of LIFE_BONES) bone(name)?.quaternion.identity();
  if (restHips) bone('hips')?.position.copy(restHips);
}

function turn(name, x, y, z) {
  const node = bone(name);
  if (!node) return;
  lifeQuat.setFromEuler(lifeEuler.set(x, y, z));
  node.quaternion.multiply(lifeQuat);
}

function updateLife(delta) {
  if (!vrm) return;
  const free = elapsed > lookUntil;
  if (free && elapsed >= life.nextGlance) {
    // Mostly back at the viewer; sometimes a glance away and back. Big glances often blink.
    // While speaking she mostly holds eye contact, with only brief, small glances.
    const talking = mouth.talk > 0.5;
    const away = life.glanceYaw === 0 && Math.random() < (talking ? 0.25 : 0.6);
    life.glanceYaw = away ? (Math.random() < 0.5 ? -1 : 1) * (8 + Math.random() * 20) * (talking ? 0.5 : 1) * DEG : 0;
    life.glancePitch = away ? (-8 + Math.random() * 14) * DEG : 0;
    life.nextGlance = elapsed + (away ? 0.8 + Math.random() * 1.8 : 2.5 + Math.random() * 5);
    if (Math.abs(life.glanceYaw) > 15 * DEG && blinkStart < 0) nextBlink = elapsed;
  }
  bone('head')?.getWorldPosition(headPos);
  const target = free ? camera.position : lookTarget.position;
  gazeDir.subVectors(target, headPos);
  let yaw = Math.atan2(gazeDir.x, gazeDir.z);
  let pitch = Math.atan2(gazeDir.y, Math.hypot(gazeDir.x, gazeDir.z));
  if (free) {
    yaw += life.glanceYaw;
    pitch += life.glancePitch;
    // Eyes lead: they jump to the glance now, the head arrives a few hundred ms later.
    const reach = gazeDir.length();
    lookTarget.position.set(
      headPos.x + Math.sin(yaw) * Math.cos(pitch) * reach,
      headPos.y + Math.sin(pitch) * reach,
      headPos.z + Math.cos(yaw) * Math.cos(pitch) * reach,
    );
  }
  smoothDamp('yaw', THREE.MathUtils.clamp(yaw, -35 * DEG, 35 * DEG), 0.35, delta);
  smoothDamp('pitch', THREE.MathUtils.clamp(pitch, -20 * DEG, 15 * DEG), 0.4, delta);

  if (elapsed >= life.nextShift) {
    life.shiftGoal = (Math.random() * 2 - 1) * (Math.abs(life.shiftGoal) > 0.4 ? 0.4 : 1);
    life.nextShift = elapsed + 5 + Math.random() * 9;
  }
  smoothDamp('shift', life.shiftGoal, 1.1, delta);
  // Weight shifts and torso drift only while standing in the idle loop, not mid-gesture or seated.
  smoothDamp('standing', currentAction === idleAction ? 1 : 0, 0.4, delta);
  // The fallback pose only resets some bones each frame; there the eyes glance but the body stays.
  if (!mixer) return;

  const t = elapsed;
  // The captured idle already shifts weight and breathes; keep the extra layer at half strength.
  const s = life.standing * 0.5;
  const shift = life.shift * s;
  // Head turn is shared down the chain so the neck never twists alone; pitch is nod-down positive.
  turn('chest', 0, life.yaw * 0.12, 0);
  turn('neck', -life.pitch * 0.4, life.yaw * 0.35, 0);
  turn('head', -life.pitch * 0.5 + drift(1, t) * 1.5 * DEG, life.yaw * 0.45, drift(2, t) * 2.5 * DEG);
  // Speaking: a small nod on stressed syllables, livelier head motion and a slight lean in.
  const talk = mouth.talk;
  turn('neck', mouth.beat * 1.2 * DEG, 0, 0);
  turn('head', mouth.beat * 2.2 * DEG + talk * drift(14, t * 2.2) * 1.4 * DEG,
    talk * drift(15, t * 1.6) * 2.2 * DEG, talk * drift(16, t * 1.3) * 1.8 * DEG);
  turn('spine', talk * 1.2 * DEG, 0, 0);
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
      resetLifeBones();
      mixer.update(delta);
      updateSit();
    } else idlePose(elapsed);
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
  if (message.type === 'body.emotion') {
    const name = String(message.name);
    desiredEmotion = EMOTIONS.includes(name) ? name : 'neutral';
    const intensity = Number(message.intensity);
    desiredIntensity = Number.isFinite(intensity) ? Math.max(0, Math.min(1, intensity)) : 1;
  } else if (message.type === 'body.look' && vrm) {
    const x = Math.max(-1, Math.min(1, Number(message.x) || 0));
    const y = Math.max(-1, Math.min(1, Number(message.y) || 0));
    const head = bone('head')?.getWorldPosition(new THREE.Vector3()) ?? new THREE.Vector3(0, 1.4, 0);
    lookTarget.position.set(head.x + x * 0.8, head.y + y * 0.5, head.z + 1.2);
    lookUntil = elapsed + LOOK_HOLD_SECONDS;
  } else if (message.type === 'body.gesture') {
    if (!playGesture(String(message.name || 'nod'))) gestureStart = elapsed;
  } else if (message.type === 'body.speech') {
    const generation = String(message.generation_id ?? '');
    if (generation !== speechGeneration || !generation) {
      const gesture = speechGesture(String(message.text ?? ''));
      if (gesture && currentAction === idleAction && playGesture(gesture)) speechGeneration = generation;
    }
  }
  if (message.type === 'body.emotion' && EMOTION_GESTURES[desiredEmotion]) {
    playGesture(EMOTION_GESTURES[desiredEmotion]);
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

// Read-only diagnostics for automated renderer checks.
window.__siroVrm = Object.freeze({
  loaded: () => Boolean(vrm),
  frames: () => frames,
  expression: name => vrm?.expressionManager?.getValue(name) ?? null,
  lookTarget: () => lookTarget.position.toArray(),
  neckPitch: () => bone('neck')?.rotation.x ?? null,
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
  for (const item of gestureMenu.children) item.disabled = !(item.dataset.gesture === 'sit' ? actions.sit_down : actions[item.dataset.gesture]);
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

// Sitting: sit_down, hold sit_loop, then stand_up back to idle.
function sitDown() {
  const down = actions.sit_down;
  const hold = actions.sit_loop;
  if (!mixer || !down || !hold || sitUntil >= 0) return false;
  sitUntil = elapsed + down.getClip().duration + SIT_SECONDS;
  return playGesture('sit_down');
}

function updateSit() {
  if (sitUntil < 0 || elapsed < sitUntil || currentAction !== actions.sit_loop) return;
  sitUntil = -1;
  if (!playGesture('stand_up')) {
    idleAction.reset().play();
    currentAction.crossFadeTo(idleAction, CROSSFADE, false);
    currentAction = idleAction;
  }
}

function perform(name) {
  if (name === 'sit') return sitDown();
  if (sitUntil >= 0) return false;
  return playGesture(name);
}

// One-shot gestures cross-fade in over the idle loop and hand control back to it when done.
function playGesture(name) {
  const action = actions[name];
  if (!mixer || !action || looping.has(action)) return false;
  if (currentAction === action && action.isRunning()) return true;
  action.reset().setLoop(THREE.LoopOnce, 1);
  action.clampWhenFinished = true;
  action.play();
  currentAction?.crossFadeTo(action, CROSSFADE, false);
  currentAction = action;
  return true;
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
  mix.addEventListener('finished', event => {
    if (event.action !== currentAction || event.action === idleAction) return;
    if (event.action === actions.sit_down && sitUntil >= 0) {
      actions.sit_loop.reset().setLoop(THREE.LoopRepeat, Infinity).play();
      event.action.crossFadeTo(actions.sit_loop, CROSSFADE, false);
      currentAction = actions.sit_loop;
      return;
    }
    idleAction.reset().play();
    event.action.crossFadeTo(idleAction, CROSSFADE, false);
    currentAction = idleAction;
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
  restHips = bone('hips')?.position.clone();
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
