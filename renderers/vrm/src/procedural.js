// Additive motion that can sit on top of a clip: analytic two-bone IK, pose weights,
// emotion breathing, and which way she faces when the window is off to one side.
// No three.js here, so the math can run under node:test.

export const BREATH_HZ = {
  neutral: 0.22,
  happy: 0.34,
  sad: 0.15,
  angry: 0.38,
  surprised: 0.44,
  relaxed: 0.13,
};

const BREATH_AMP = {
  neutral: 0.8,
  happy: 1.05,
  sad: 0.55,
  angry: 1.15,
  surprised: 1.05,
  relaxed: 0.6,
};

// Names that are a pose, not a captured clip. A soft nod or shake is also a pose.
export const PROCEDURAL_ONLY = new Set(['lean', 'shrug', 'tilt', 'attentive', 'point', 'reach']);

export function clamp(value, low, high) {
  return Math.min(high, Math.max(low, value));
}

export function proceduralInsteadOfClip(name, intensity) {
  if (PROCEDURAL_ONLY.has(name)) return true;
  return (name === 'nod' || name === 'shake') && intensity < 0.55;
}

export function suppressClientSpeechGesture(message) {
  return message?.motion === 'server';
}

// Two-bone IK for an arm that hangs down (rest direction -Y). tx is outward, ty is up.
// shoulder is radians to swing the upper arm off that rest; elbow is radians of bend
// from straight (0 = straight). Both are in the plane of the target.
export function hangingTwoBone(l1, l2, tx, ty) {
  if (!(l1 > 0) || !(l2 > 0) || !Number.isFinite(tx) || !Number.isFinite(ty)) {
    return { shoulder: 0, elbow: 0, distance: 0, clamped: true };
  }
  const raw = Math.hypot(tx, ty);
  const min = Math.abs(l1 - l2);
  const max = l1 + l2;
  let distance = Math.min(Math.max(raw, min), max);
  if (distance < 1e-8) distance = 1e-8;
  const cosElbow = clamp((l1 * l1 + l2 * l2 - distance * distance) / (2 * l1 * l2), -1, 1);
  const elbow = Math.PI - Math.acos(cosElbow);
  const cosAlpha = clamp((l1 * l1 + distance * distance - l2 * l2) / (2 * l1 * distance), -1, 1);
  const alpha = Math.acos(cosAlpha);
  const shoulder = Math.atan2(tx, -ty) - alpha;
  return { shoulder, elbow, distance: raw, clamped: Math.abs(distance - raw) > 1e-3 };
}

// Where the hand lands if the bones follow hangingTwoBone's angles.
export function armEndpoint(l1, l2, shoulder, elbow) {
  return {
    x: l1 * Math.sin(shoulder) + l2 * Math.sin(shoulder + elbow),
    y: l1 * -Math.cos(shoulder) + l2 * -Math.cos(shoulder + elbow),
  };
}

// A point reaches out; a reach lifts toward something in front of her. scale is arm length.
export function reachPoint(kind, scale) {
  const span = scale > 0 ? scale : 1;
  if (kind === 'reach') return { x: 0.18 * span, y: 0.62 * span };
  return { x: 0.48 * span, y: 0.28 * span };
}

export function breathRadians(emotion, time) {
  const hz = BREATH_HZ[emotion] ?? BREATH_HZ.neutral;
  const amp = BREATH_AMP[emotion] ?? BREATH_AMP.neutral;
  return Math.sin(time * hz * Math.PI * 2) * 0.012 * amp;
}

// Window centre as -1 (left edge of the screen) to +1 (right). She looks back toward
// the rest of the desk, so a window on the right turns her head to her left.
export function userYawBias(side) {
  const yaw = -clamp(Number(side) || 0, -1, 1) * 0.14;
  return yaw === 0 ? 0 : yaw;
}

function emptyPose() {
  return {
    lean: 0, shrug: 0, tilt: 0, attentive: 0, point: 0, reach: 0, think: 0, nod: 0, shake: 0,
  };
}

export function createPoseMixer() {
  const active = new Map();
  return {
    play(name, now, intensity = 1, seconds = 1.5) {
      const span = Math.max(0.3, seconds);
      active.set(name, {
        intensity: clamp(intensity, 0, 1),
        start: now,
        until: now + span,
        hold: false,
      });
    },
    hold(name, now, intensity = 1, seconds = 1.2) {
      const prev = active.get(name);
      active.set(name, {
        intensity: clamp(intensity, 0, 1),
        start: prev?.start ?? now,
        until: now + Math.max(0.3, seconds),
        hold: true,
      });
    },
    sample(now) {
      const out = emptyPose();
      for (const [name, item] of active) {
        const span = Math.max(1e-4, item.until - item.start);
        const t = now - item.start;
        if (t < 0 || now > item.until + 1e-6) {
          active.delete(name);
          continue;
        }
        const weight = item.hold
          ? (item.until - now < 0.25 ? Math.max(0, (item.until - now) / 0.25) : 1)
          : Math.sin(Math.PI * clamp(t / span, 0, 1));
        const amp = weight * item.intensity;
        if (name === 'nod') out.nod += Math.sin(t * Math.PI * 2 * (1 + item.intensity)) * amp;
        else if (name === 'shake') out.shake += Math.sin(t * Math.PI * 2 * 2.2) * amp;
        else if (Object.hasOwn(out, name)) out[name] = Math.max(out[name], amp);
      }
      return out;
    },
  };
}
