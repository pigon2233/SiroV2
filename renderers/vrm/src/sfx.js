// Soft sound effects for SIRO's body gestures. Short recorded clips (src/sfx, see LICENSES.md) are
// played through an <audio> element (the same path her voice takes), with no dependence on WebAudio
// output, which can be silent in some webviews. If a clip fails to load, a synthesised stand-in
// built below plays instead. Quiet by
// design: low master volume (halved at night), silent while she speaks or the microphone listens,
// rate limited, and one switch turns it off.
const STORAGE_KEY = 'siro.sfx';
const MASTER = 0.4;
const NIGHT_FACTOR = 0.5;
const RATE = 22050;
const OWN_GAP_SECONDS = 600; // sounds she makes on her own (pastimes): at most one per 10 minutes
const MIN_GAP = { rustle: 8, giggle: 30, poke: 0.25, clap: 0, thump: 0.5, paper: 0.5, paper_out: 0.5, paper_read: 0.5, paper_away: 0.5 };
// Recorded clips, all level-matched; `gain` trims a clip further. Each play varies slightly in level
// and speed so repeats (the three claps) are not identical.
const FILES = {
  clap: { file: 'clap.wav', gain: 1 },
  poke: { file: 'poke.wav', gain: 1 },
  thump: { file: 'thump.wav', gain: 0.7 },
  rustle: { file: 'rustle.wav', gain: 0.5 },
  paper_out: { file: 'paper_out.wav', gain: 1 },
  paper_read: { file: 'paper_read.wav', gain: 1 },
  paper_away: { file: 'paper_away.wav', gain: 1 },
};
const FALLBACK = { paper_out: 'paper', paper_read: 'paper', paper_away: 'paper' };

function isNight(hour) {
  return hour >= 23 || hour < 8;
}

// A biquad filter (RBJ cookbook) over a sample array, in place.
function filter(data, type, freq, q) {
  const w = (2 * Math.PI * freq) / RATE;
  const alpha = Math.sin(w) / (2 * q);
  const cos = Math.cos(w);
  let b0;
  let b1;
  let b2;
  if (type === 'lowpass') {
    b0 = (1 - cos) / 2; b1 = 1 - cos; b2 = b0;
  } else {
    b0 = alpha; b1 = 0; b2 = -alpha;
  }
  const a0 = 1 + alpha;
  const a1 = -2 * cos;
  const a2 = 1 - alpha;
  let x1 = 0; let x2 = 0; let y1 = 0; let y2 = 0;
  for (let i = 0; i < data.length; i++) {
    const x = data[i];
    const y = (b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2) / a0;
    x2 = x1; x1 = x; y2 = y1; y1 = y;
    data[i] = y;
  }
}

// Mix `layer` into `out` at `at` seconds, normalised, with a fast attack and exponential decay.
function mix(out, at, layer, peak, attack, decay) {
  const start = Math.floor(at * RATE);
  const attackSamples = Math.max(1, Math.floor(attack * RATE));
  const total = Math.min(Math.floor((attack + decay) * RATE), layer.length);
  let top = 1e-6;
  for (let i = 0; i < total; i++) top = Math.max(top, Math.abs(layer[i]));
  for (let i = 0; i < total && start + i < out.length; i++) {
    const envelope = i < attackSamples ? i / attackSamples : Math.exp((-6.9 * (i - attackSamples)) / (decay * RATE));
    out[start + i] += (layer[i] / top) * peak * envelope;
  }
}

function noiseBurst(out, at, { freq, q = 1, type = 'bandpass', peak, attack = 0.003, decay }) {
  const layer = new Float32Array(Math.floor((attack + decay + 0.05) * RATE));
  for (let i = 0; i < layer.length; i++) layer[i] = Math.random() * 2 - 1;
  filter(layer, type, freq, q);
  mix(out, at, layer, peak, attack, decay);
}

function tone(out, at, { from, to, peak, decay, wave = 'sine' }) {
  const layer = new Float32Array(Math.floor((decay + 0.05) * RATE));
  let phase = 0;
  for (let i = 0; i < layer.length; i++) {
    const freq = from * (to / from) ** Math.min(1, i / RATE / decay);
    phase += (2 * Math.PI * freq) / RATE;
    layer[i] = wave === 'triangle' ? (2 / Math.PI) * Math.asin(Math.sin(phase)) : Math.sin(phase);
  }
  mix(out, at, layer, peak, 0.01, decay);
}

const VOICES = {
  // One soft clap of the hands: a mid noise snap with a little body underneath.
  clap: { length: 0.2, build(out) {
    // Hands never meet in one instant: a few micro-bursts a few milliseconds apart, then a
    // short low "pock" from the cupped palms.
    for (const [at, peak] of [[0, 0.35], [0.006, 0.45], [0.012, 0.3]]) {
      noiseBurst(out, at, { freq: 1300, q: 1.4, peak, attack: 0.001, decay: 0.03 });
    }
    noiseBurst(out, 0.004, { freq: 420, q: 1.2, peak: 0.4, attack: 0.002, decay: 0.05 });
  } },
  // Cloth against cloth: a slow noise swish.
  rustle: { length: 0.4, build(out) {
    noiseBurst(out, 0, { freq: 2400, q: 0.6, peak: 0.25, attack: 0.05, decay: 0.2 });
  } },
  // A "boop" as the finger lands.
  poke: { length: 0.25, build(out) {
    tone(out, 0, { from: 620, to: 330, peak: 0.5, decay: 0.1 });
  } },
  // Feet landing: a dull low thud.
  thump: { length: 0.3, build(out) {
    tone(out, 0, { from: 110, to: 50, peak: 0.7, decay: 0.16 });
    noiseBurst(out, 0, { freq: 300, q: 0.7, type: 'lowpass', peak: 0.25, decay: 0.08 });
  } },
  // A page turned: dry high noise.
  paper: { length: 0.4, build(out) {
    noiseBurst(out, 0, { freq: 4200, q: 0.5, peak: 0.2, attack: 0.02, decay: 0.12 });
    noiseBurst(out, 0.09, { freq: 3200, q: 0.6, peak: 0.12, attack: 0.01, decay: 0.08 });
  } },
  // A "hehe": three quick rising chirps.
  giggle: { length: 0.6, build(out) {
    for (const [i, base] of [820, 900, 780].entries()) {
      tone(out, i * 0.13, { from: base, to: base * 1.35, peak: 0.3, decay: 0.09, wave: 'triangle' });
    }
  } },
};

function wavUrl(samples) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset, value) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); };
  text(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); text(8, 'WAVEfmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, RATE, true); view.setUint32(28, RATE * 2, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); text(36, 'data'); view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, samples[i])) * 32767, true);
  }
  return URL.createObjectURL(new Blob([buffer], { type: 'audio/wav' }));
}

export function createSfx({ speaking = () => false, hour = () => new Date().getHours(), now = () => performance.now() / 1000 } = {}) {
  let enabled = true;
  try {
    enabled = localStorage.getItem(STORAGE_KEY) !== 'off';
  } catch { /* storage may be blocked */ }
  let lastOwn = -Infinity;
  let lastResult = 'none';
  const lastByName = {};
  const urls = {};
  const played = [];

  function urlFor(name) {
    if (!urls[name]) {
      const voice = VOICES[name];
      const out = new Float32Array(Math.floor(voice.length * RATE));
      voice.build(out);
      filter(out, 'lowpass', 3600, 0.7); // take the edge off everything
      urls[name] = wavUrl(out);
    }
    return urls[name];
  }

  function play(name, { own = false, force = false } = {}) {
    if (!enabled || !(FILES[name] || VOICES[name]) || (!force && speaking())) return false;
    const clock = now();
    if (!force && own && (isNight(hour()) || clock - lastOwn < OWN_GAP_SECONDS)) return false;
    if (!force && clock - (lastByName[name] ?? -Infinity) < (MIN_GAP[name] ?? 0)) return false;
    try {
      const clip = FILES[name];
      const audio = new Audio(clip ? new URL(`./sfx/${clip.file}`, import.meta.url).href : urlFor(name));
      audio.volume = Math.min(1, MASTER * (clip?.gain ?? 1) * (0.85 + Math.random() * 0.15) * (isNight(hour()) ? NIGHT_FACTOR : 1));
      if (clip) {
        audio.playbackRate = 0.96 + Math.random() * 0.08;
        audio.addEventListener('error', () => {
          const voice = FALLBACK[name] ?? name;
          if (!VOICES[voice]) return;
          const backup = new Audio(urlFor(voice));
          backup.volume = audio.volume;
          backup.play()?.catch?.(() => {});
        }, { once: true });
      }
      audio.play()?.then?.(() => { lastResult = 'playing'; }, error => {
        lastResult = `blocked: ${error?.name ?? error}`;
        console.info(`SIRO sfx: ${name} ${lastResult}`);
      });
    } catch (error) {
      lastResult = `error: ${error?.name ?? error}`;
      return false;
    }
    lastByName[name] = clock;
    if (own) lastOwn = clock;
    played.push(name);
    if (played.length > 50) played.shift();
    return true;
  }

  return {
    play,
    get enabled() { return enabled; },
    setEnabled(value) {
      enabled = Boolean(value);
      try {
        localStorage.setItem(STORAGE_KEY, enabled ? 'on' : 'off');
      } catch { /* storage may be blocked */ }
    },
    // Names of the sounds played so far, for automated checks.
    get played() { return played.slice(); },
    // What the last attempt to start a sound did, shown by the test-listen button.
    get audioState() { return lastResult; },
  };
}
