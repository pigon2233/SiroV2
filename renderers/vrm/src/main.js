// SIRO VRM renderer: presentation only. It follows the same body.v1 boundary and
// renderer-ownership rules as the Live2D renderer and never owns speech audio.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

const MODEL_URL = '/vrm-model/model.vrm';
const desktop = new URLSearchParams(location.search).get('presentation') === 'desktop';
const statusLine = document.querySelector('#status');
const EMOTIONS = ['happy', 'sad', 'angry', 'surprised', 'relaxed'];
const LOOK_HOLD_SECONDS = 4;

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
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
let nextBlink = 2;
let blinkStart = -1;
let elapsed = 0;
let frames = 0;
const emotionWeights = Object.fromEntries(EMOTIONS.map(name => [name, 0]));

function fitCamera() {
  const width = window.innerWidth || 1;
  const height = window.innerHeight || 1;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  if (modelBox) {
    const size = modelBox.getSize(new THREE.Vector3());
    const center = modelBox.getCenter(new THREE.Vector3());
    const visibleHeight = Math.max(size.y, size.x / camera.aspect) * 1.08;
    const distance = visibleHeight / 2 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    camera.position.set(0, center.y, distance + size.z);
    camera.lookAt(0, center.y, 0);
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
}

function updateLook() {
  if (!vrm?.lookAt) return;
  if (elapsed > lookUntil) lookTarget.position.copy(camera.position);
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
    idlePose(elapsed);
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
    gestureStart = elapsed;
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
});

async function loadModel() {
  const loader = new GLTFLoader();
  loader.register(parser => new VRMLoaderPlugin(parser));
  const gltf = await loader.loadAsync(MODEL_URL);
  const loaded = gltf.userData.vrm;
  if (!loaded) throw new Error('file is not a VRM model');
  VRMUtils.removeUnnecessaryVertices(gltf.scene);
  VRMUtils.rotateVRM0(loaded);
  scene.add(loaded.scene);
  vrm = loaded;
  idlePose(0);
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
