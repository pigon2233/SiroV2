// SIRO activity controller v1: renderer-local body activities over the pack's six body IDs.
// The runtime picks low-frequency intents; every frame is blended here without model calls.
// Expression, mouth, breath, blink, physics and gaze stay with their existing owners.

export type ActivityClip = {
  duration: number;
  loop: boolean;
  entry: number;
  exit: number;
  resume: number;
  curves: Record<string, number[]>;
};

export type ActivityPack = {
  schema: string;
  pack_id: string;
  version: string;
  digest: string;
  body_ids: string[];
  activities: Record<string, ActivityClip>;
};

export type ActivityIntent = {
  instance_id: string;
  generation_id: string;
  activity: string;
  pack_version: string;
  op: string;
  ttl_s?: number;
};

export type ActivityEvent = {
  type: string;
  instance_id: string;
  generation_id: string;
  activity: string | null;
  reason?: string;
};

type Track = {
  kind: string;
  instance: string;
  generation: string;
  phase: number;
  expiresIn: number | null;
  started: boolean;
};

export const RUNTIME_SCHEMA = 'siro.visual.pack.runtime.v0';
export const BODY_IDS = [
  'ParamAngleX', 'ParamAngleY', 'ParamAngleZ',
  'ParamBodyAngleX', 'ParamBodyAngleY', 'ParamBodyAngleZ'
];
const REST_ID = 'rest';

function lerp(a: number, b: number, w: number): number {
  return a + (b - a) * w;
}

function bezier(p0: number, p1: number, p2: number, p3: number, u: number): number {
  const a = lerp(p0, p1, u), b = lerp(p1, p2, u), c = lerp(p2, p3, u);
  const d = lerp(a, b, u), e = lerp(b, c, u);
  return lerp(d, e, u);
}

// motion3 segments: [t0, v0, type, points...]; 0 linear, 1 bezier, 2 stepped, 3 inverse stepped.
// Packs set AreBeziersRestricted, so bezier progress is evaluated on the segment time ratio.
export function evaluateCurve(segments: number[], time: number): number {
  let t0 = segments[0], v0 = segments[1], index = 2;
  if (time <= t0) return v0;
  while (index < segments.length) {
    const kind = segments[index];
    const width = kind === 1 ? 6 : 2;
    const end = index + 1 + width;
    const t1 = segments[end - 2], v1 = segments[end - 1];
    if (time <= t1) {
      const u = t1 > t0 ? (time - t0) / (t1 - t0) : 1;
      if (kind === 0) return lerp(v0, v1, u);
      if (kind === 1) return bezier(v0, segments[index + 2], segments[index + 4], v1, u);
      if (kind === 2) return time < t1 ? v0 : v1;
      return v1;
    }
    t0 = t1; v0 = v1; index = end;
  }
  return v0;
}

export function validatePack(pack: unknown): string | null {
  const value = pack as ActivityPack;
  if (!value || value.schema !== RUNTIME_SCHEMA) return 'schema';
  if (typeof value.version !== 'string' || !value.version) return 'version';
  if (JSON.stringify(value.body_ids) !== JSON.stringify(BODY_IDS)) return 'body_ids';
  if (!value.activities || !value.activities.idle) return 'idle';
  for (const kind of Object.keys(value.activities)) {
    const clip = value.activities[kind];
    if (!(clip.duration > 0) || !(clip.entry > 0) || !(clip.exit > 0) || !(clip.resume > 0)) {
      return 'timing';
    }
    for (const id of BODY_IDS) if (!Array.isArray(clip.curves[id])) return 'curves';
  }
  return null;
}

export class SiroActivityController {
  onEvent: (event: ActivityEvent) => void = () => {};
  private pack: ActivityPack | null = null;
  private disabled: string | null = null;
  private hasParameter: ((id: string) => boolean) | null = null;
  private pending: ActivityIntent | null = null;
  private current: Track | null = null;
  private saved: Track | null = null;
  private blendFrom: Record<string, number> | null = null;
  private captureNext = false;
  private blendElapsed = 0;
  private blendDuration = 0;
  private releasing = false;
  private lastWritten: Record<string, number> | null = null;

  // A missing or invalid pack keeps the stock character; activities report unsupported.
  load(pack: unknown): string | null {
    const error = pack === null ? 'no_pack' : validatePack(pack);
    if (error) {
      this.disabled = error;
      const pending = this.pending;
      this.pending = null;
      if (pending) this.request(pending);
      return error;
    }
    this.pack = pack as ActivityPack;
    this.flush();
    return null;
  }

  // The model reports which parameters really exist once setup completes.
  bindModel(hasParameter: (id: string) => boolean): void {
    this.hasParameter = hasParameter;
    this.flush();
  }

  private flush(): void {
    const pending = this.pending;
    if (!pending || !this.pack || !this.hasParameter) return;
    this.pending = null;
    this.request(pending);
  }

  snapshot(): {activity: string | null; instance: string | null; generation: string | null; phase: number} {
    const track = this.current;
    return {
      activity: track ? track.kind : null,
      instance: track ? track.instance : null,
      generation: track ? track.generation : null,
      phase: track ? track.phase : 0
    };
  }

  request(intent: ActivityIntent): ActivityEvent {
    const reply = (type: string, reason?: string, activity: string | null = intent.activity) => {
      const event: ActivityEvent = {
        type, instance_id: intent.instance_id, generation_id: intent.generation_id, activity
      };
      if (reason) event.reason = reason;
      this.onEvent(event);
      return event;
    };
    if (intent.op === 'stop') {
      const waiting = this.pending;
      if (waiting && waiting.instance_id === intent.instance_id &&
          waiting.generation_id === intent.generation_id) {
        this.pending = null;
        return reply('interrupted', 'stopped', waiting.activity);
      }
      const track = this.current;
      if (!track || track.instance !== intent.instance_id || track.generation !== intent.generation_id) {
        return reply('ignored', 'stale');
      }
      this.stop('stopped');
      return {type: 'stopped', instance_id: intent.instance_id, generation_id: intent.generation_id,
        activity: track.kind};
    }
    if (intent.op !== 'start') return reply('failed', 'op');
    if (this.disabled) return reply('unsupported', this.disabled);
    if (!this.pack || !this.hasParameter) {
      // Only the newest intent waits for the pack/model; nothing is replayed later.
      const waiting = this.pending;
      if (waiting) {
        this.onEvent({type: 'interrupted', instance_id: waiting.instance_id,
          generation_id: waiting.generation_id, activity: waiting.activity, reason: 'superseded'});
      }
      this.pending = intent;
      return reply('accepted', 'not_ready');
    }
    if (intent.pack_version !== this.pack.version) return reply('unsupported', 'pack_version');
    const clip = this.pack.activities[intent.activity];
    if (!clip) return reply('unsupported', 'activity');
    const check = this.hasParameter;
    if (!BODY_IDS.every(id => check(id))) return reply('unsupported', 'parameters');
    const ttl = typeof intent.ttl_s === 'number' && intent.ttl_s > 0 ? intent.ttl_s : null;
    const current = this.current;
    if (current && current.kind === intent.activity && clip.loop) {
      if (current.instance === intent.instance_id && current.generation === intent.generation_id) {
        return reply('duplicate');
      }
      // Same looping activity under a new owner: keep the phase, retire the old ids.
      this.emitTrack('interrupted', current, 'superseded');
      current.instance = intent.instance_id;
      current.generation = intent.generation_id;
      current.expiresIn = ttl;
      return reply('accepted');
    }
    const saved = this.saved;
    if (saved && saved.kind === intent.activity && clip.loop) {
      // A gesture is playing over this activity; let it finish and resume the same phase.
      this.emitTrack('interrupted', saved, 'superseded');
      saved.instance = intent.instance_id;
      saved.generation = intent.generation_id;
      saved.expiresIn = ttl;
      return reply('accepted');
    }
    const track: Track = {
      kind: intent.activity, instance: intent.instance_id, generation: intent.generation_id,
      phase: 0, expiresIn: ttl, started: false
    };
    if (!clip.loop) {
      // One-shot gestures pause the main activity and resume its saved phase afterwards.
      if (current && this.clip(current.kind).loop) this.saved = current;
      else if (current) this.emitTrack('interrupted', current, 'replaced');
    } else {
      if (current) this.emitTrack('interrupted', current, 'replaced');
      if (this.saved) this.emitTrack('interrupted', this.saved, 'replaced');
      this.saved = null;
    }
    this.current = track;
    this.releasing = false;
    this.beginBlend(clip.entry);
    return reply('accepted');
  }

  // Speech cancellation ends only the speaking pose; other activities keep running.
  cancelSpeech(): void {
    if (this.saved && this.saved.kind === 'speaking_pose') {
      this.emitTrack('interrupted', this.saved, 'speech_cancelled');
      this.saved = null;
    }
    if (this.current && this.current.kind === 'speaking_pose') this.stop('speech_cancelled');
  }

  tick(dt: number, read: (id: string) => number, write: (id: string, value: number) => void): void {
    if (!this.current && !this.releasing) return;
    const step = Math.max(0, Math.min(dt, 0.25));
    let track = this.current;
    if (track) {
      track.phase += step;
      if (track.expiresIn !== null) {
        track.expiresIn -= step;
        if (track.expiresIn <= 0) {
          this.stop('expired');
          track = this.current;
        }
      }
    }
    if (track && !this.clip(track.kind).loop && track.phase >= this.clip(track.kind).duration) {
      this.emitTrack('finished', track);
      this.next(this.clip(track.kind).exit);
      track = this.current;
    }
    if (track && !track.started) {
      track.started = true;
      this.emitTrack('started', track);
    }
    if (this.captureNext) {
      const from: Record<string, number> = {};
      for (const id of BODY_IDS) from[id] = this.lastWritten ? this.lastWritten[id] : read(id);
      this.blendFrom = from;
      this.captureNext = false;
    }
    let weight = 1;
    if (this.blendFrom) {
      this.blendElapsed += step;
      const u = Math.min(1, this.blendElapsed / this.blendDuration);
      weight = u * u * (3 - 2 * u);
    }
    const written: Record<string, number> = {};
    for (const id of BODY_IDS) {
      const target = track ? this.sample(track, id) : read(id);
      const value = this.blendFrom ? lerp(this.blendFrom[id], target, weight) : target;
      write(id, value);
      written[id] = value;
    }
    this.lastWritten = written;
    if (this.blendFrom && weight >= 1) {
      this.blendFrom = null;
      if (this.releasing) {
        // Stock motion owns these IDs again from the next frame.
        this.releasing = false;
        this.lastWritten = null;
      }
    }
  }

  private clip(kind: string): ActivityClip {
    return (this.pack as ActivityPack).activities[kind];
  }

  private sample(track: Track, id: string): number {
    const clip = this.clip(track.kind);
    const time = clip.loop ? track.phase % clip.duration : Math.min(track.phase, clip.duration);
    return evaluateCurve(clip.curves[id], time);
  }

  private beginBlend(duration: number): void {
    this.captureNext = true;
    this.blendFrom = null;
    this.blendElapsed = 0;
    this.blendDuration = duration;
  }

  private stop(reason: string): void {
    const track = this.current;
    if (!track) return;
    this.emitTrack('interrupted', track, reason);
    this.next(this.clip(track.kind).exit);
  }

  // After an activity ends: resume a paused activity, rest in idle, or hand back to stock motion.
  private next(exitSeconds: number): void {
    const ended = this.current;
    const saved = this.saved;
    this.saved = null;
    if (saved) {
      saved.started = true;
      this.current = saved;
      this.beginBlend(this.clip(saved.kind).resume);
      return;
    }
    if (ended && ended.kind !== 'idle') {
      this.current = {
        kind: 'idle', instance: REST_ID, generation: ended.generation, phase: 0,
        expiresIn: null, started: false
      };
      this.beginBlend(exitSeconds);
      return;
    }
    this.current = null;
    this.releasing = true;
    this.beginBlend(exitSeconds);
  }

  private emitTrack(type: string, track: Track, reason?: string): void {
    const event: ActivityEvent = {
      type, instance_id: track.instance, generation_id: track.generation, activity: track.kind
    };
    if (reason) event.reason = reason;
    this.onEvent(event);
  }
}

export const siroActivity = new SiroActivityController();
