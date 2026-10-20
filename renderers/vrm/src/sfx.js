// Soft sound effects for SIRO's body gestures. Everything is synthesised with WebAudio: there are
// no sound files, so nothing to license. Quiet by design: low master volume (halved at night),
// silent while she speaks or the microphone listens, rate limited, and one switch turns it off.
const STORAGE_KEY = 'siro.sfx';
const MASTER = 0.3;
const NIGHT_FACTOR = 0.5;
const OWN_GAP_SECONDS = 600; // sounds she makes on her own (pastimes): at most one per 10 minutes
const MIN_GAP = { rustle: 1.5, giggle: 30, poke: 0.25, clap: 0, thump: 0.5, paper: 0.5 };

function isNight(hour) {
  return hour >= 23 || hour < 8;
}

export function createSfx({ speaking = () => false, hour = () => new Date().getHours(), now = () => performance.now() / 1000 } = {}) {
  let context = null;
  let master = null;
  let noise = null;
  let enabled = true;
  try {
    enabled = localStorage.getItem(STORAGE_KEY) !== 'off';
  } catch { /* storage may be blocked */ }
  let lastOwn = -Infinity;
  const lastByName = {};
  const played = [];

  function ensure() {
    if (context) {
      if (context.state !== 'running') context.resume?.().catch?.(() => {});
      return context.state === 'running';
    }
    const Ctor = globalThis.AudioContext ?? globalThis.webkitAudioContext;
    if (!Ctor) return false;
    try {
      context = new Ctor({ latencyHint: 'playback' });
      master = context.createGain();
      master.connect(context.destination);
      const length = Math.floor(context.sampleRate * 0.5);
      noise = context.createBuffer(1, length, context.sampleRate);
      const data = noise.getChannelData(0);
      for (let i = 0; i < length; i++) data[i] = Math.random() * 2 - 1;
    } catch (error) {
      console.warn('SIRO sfx: no audio context', error);
      context = null;
      return false;
    }
    context.resume?.().catch?.(() => {});
    context.addEventListener?.('statechange', () => console.info(`SIRO sfx: audio ${context.state}`));
    console.info(`SIRO sfx: audio ${context.state}`);
    return context.state === 'running';
  }

  // A burst of filtered noise with a fast decay.
  function burst(at, { freq, q = 1, type = 'bandpass', peak, attack = 0.003, decay }) {
    const source = context.createBufferSource();
    source.buffer = noise;
    const filter = context.createBiquadFilter();
    filter.type = type;
    filter.frequency.value = freq;
    filter.Q.value = q;
    const gain = context.createGain();
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.linearRampToValueAtTime(peak, at + attack);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + attack + decay);
    source.connect(filter).connect(gain).connect(master);
    source.start(at, Math.random() * 0.2, attack + decay + 0.05);
  }

  // A short pitched blip whose frequency glides from one value to another.
  function tone(at, { from, to, peak, decay, wave = 'sine' }) {
    const osc = context.createOscillator();
    osc.type = wave;
    osc.frequency.setValueAtTime(from, at);
    osc.frequency.exponentialRampToValueAtTime(to, at + decay);
    const gain = context.createGain();
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.linearRampToValueAtTime(peak, at + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + decay);
    osc.connect(gain).connect(master);
    osc.start(at);
    osc.stop(at + decay + 0.05);
  }

  const VOICES = {
    // One soft clap of the hands: a mid noise snap with a little body underneath.
    clap(t) {
      burst(t, { freq: 1700, q: 0.9, peak: 0.5, decay: 0.07 });
      burst(t, { freq: 700, q: 0.7, peak: 0.25, decay: 0.05 });
    },
    // Cloth against cloth: a low, slow noise swish.
    rustle(t) {
      burst(t, { freq: 2400, q: 0.6, peak: 0.16, attack: 0.05, decay: 0.2 });
    },
    // A "boop" as the finger lands.
    poke(t) {
      tone(t, { from: 620, to: 330, peak: 0.4, decay: 0.1 });
    },
    // Feet landing: a dull low thud.
    thump(t) {
      tone(t, { from: 110, to: 50, peak: 0.55, decay: 0.16 });
      burst(t, { freq: 300, q: 0.7, type: 'lowpass', peak: 0.2, decay: 0.08 });
    },
    // A page turned: dry high noise.
    paper(t) {
      burst(t, { freq: 4200, q: 0.5, peak: 0.12, attack: 0.02, decay: 0.12 });
      burst(t + 0.09, { freq: 3200, q: 0.6, peak: 0.08, attack: 0.01, decay: 0.08 });
    },
    // A "hehe": two or three quick rising chirps.
    giggle(t) {
      for (const [i, base] of [820, 900, 780].entries()) {
        tone(t + i * 0.13, { from: base, to: base * 1.35, peak: 0.16, decay: 0.09, wave: 'triangle' });
      }
    },
  };

  function play(name, { own = false } = {}) {
    const voice = VOICES[name];
    if (!enabled || !voice || speaking()) return false;
    const clock = now();
    if (own && (isNight(hour()) || clock - lastOwn < OWN_GAP_SECONDS)) return false;
    if (clock - (lastByName[name] ?? -Infinity) < (MIN_GAP[name] ?? 0)) return false;
    if (!ensure()) {
      console.info(`SIRO sfx: ${name} skipped, audio ${context?.state ?? 'unavailable'}`);
      return false;
    }
    master.gain.value = MASTER * (isNight(hour()) ? NIGHT_FACTOR : 1);
    voice(context.currentTime + 0.01);
    lastByName[name] = clock;
    if (own) lastOwn = clock;
    played.push(name);
    if (played.length > 50) played.shift();
    return true;
  }

  // Open the audio device early: a context starts suspended and only runs a moment later.
  if (enabled) setTimeout(ensure, 0);

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
  };
}
