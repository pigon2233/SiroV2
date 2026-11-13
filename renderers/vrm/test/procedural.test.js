import assert from 'node:assert/strict';
import test from 'node:test';
import {
  BREATH_HZ,
  armEndpoint,
  breathRadians,
  createPoseMixer,
  hangingTwoBone,
  proceduralInsteadOfClip,
  reachPoint,
  suppressClientSpeechGesture,
  userYawBias,
} from '../src/procedural.js';

test('two-bone IK reaches a target inside the arm and stays straight when hanging', () => {
  const down = hangingTwoBone(1, 1, 0, -2);
  assert.ok(Math.abs(down.shoulder) < 1e-6);
  assert.ok(Math.abs(down.elbow) < 1e-6);
  const side = hangingTwoBone(1, 1, 1, 0);
  const end = armEndpoint(1, 1, side.shoulder, side.elbow);
  assert.ok(Math.abs(end.x - 1) < 1e-6, end.x);
  assert.ok(Math.abs(end.y) < 1e-6, end.y);
  const up = hangingTwoBone(0.25, 0.22, 0.05, 0.4);
  const hand = armEndpoint(0.25, 0.22, up.shoulder, up.elbow);
  assert.ok(Math.hypot(hand.x - 0.05, hand.y - 0.4) < 1e-5);
  const far = hangingTwoBone(1, 1, 10, 0);
  assert.equal(far.clamped, true);
  assert.ok(far.elbow < 0.02);
});

test('pose weights blend and then expire', () => {
  const mixer = createPoseMixer();
  mixer.play('nod', 0, 1, 1);
  mixer.hold('tilt', 0, 0.5, 2);
  const mid = mixer.sample(0.1);
  assert.ok(Math.abs(mid.nod) > 0.2);
  assert.ok(mid.tilt > 0.4);
  const later = mixer.sample(3);
  assert.equal(later.nod, 0);
  assert.equal(later.tilt, 0);
});

test('a soft nod is procedural and a wave stays a clip', () => {
  assert.equal(proceduralInsteadOfClip('nod', 0.4), true);
  assert.equal(proceduralInsteadOfClip('shake', 0.8), false);
  assert.equal(proceduralInsteadOfClip('point', 1), true);
  assert.equal(proceduralInsteadOfClip('reach', 0.2), true);
  assert.equal(proceduralInsteadOfClip('wave', 1), false);
  assert.ok(reachPoint('point', 1).x > reachPoint('reach', 1).x);
});

test('breathing follows emotion and the window faces back toward the desk', () => {
  assert.ok(BREATH_HZ.happy > BREATH_HZ.sad);
  assert.ok(breathRadians('happy', 1 / (4 * BREATH_HZ.happy)) > 0);
  assert.equal(breathRadians('sad', 0), 0);
  assert.ok(userYawBias(1) < 0);
  assert.ok(userYawBias(-1) > 0);
  assert.equal(userYawBias(0), 0);
  assert.equal(suppressClientSpeechGesture({motion: 'server'}), true);
  assert.equal(suppressClientSpeechGesture({text: '你好'}), false);
});
