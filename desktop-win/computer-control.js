'use strict';
// Last-line safety floor for desktop input in the Windows shell. Mirrors services/computer_use/safety.py:
// default OFF, latched emergency stop, allowlist, rate limit, no secret-looking text. Only the owner
// (tray menu) can enable; stop() always wins until the owner enables again.
const {spawn} = require('node:child_process');
const path = require('node:path');

const KINDS = new Set(['move', 'click', 'scroll', 'key', 'type']);
const MAX_TYPE = 200, PER_SECOND = 5, PER_MINUTE = 120, TIMEOUT_MS = 3000, READY_TIMEOUT_MS = 15000;
const BLOCKED = new Set(['alt+f4', 'ctrl+alt+delete', 'ctrl+shift+escape', 'win+l', 'win+r', 'win+x', 'ctrl+escape']);
const ALIASES = {control: 'ctrl', del: 'delete', windows: 'win', esc: 'escape'};
const SECRET = /sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\./;
const normalize = key => String(key).split('+').map(p => p.trim().toLowerCase()).filter(Boolean).map(p => ALIASES[p] || p).join('+');

function defaultSpawn() {
  const script = path.join(__dirname, 'input-helper.ps1');
  return spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', script],
    {stdio: ['pipe', 'pipe', 'ignore'], windowsHide: true});
}

class ComputerControl {
  // getBounds() -> {x, y, width, height} in physical pixels; env is read for secret values.
  constructor({getBounds, spawnHelper = defaultSpawn, now = Date.now, env = process.env, onState = () => {}}) {
    Object.assign(this, {getBounds, spawnHelper, now, env});
    this.listeners = [onState];
    this.ready = Promise.resolve(); this.enabled = false; this.stopped = false; this.stamps = []; this.helper = null; this.pending = new Map(); this.seq = 0; this.buffer = '';
  }
  emit(state) { for (const listener of this.listeners) { try { listener(state); } catch (_) { /* a listener must not block stop */ } } }
  get active() { return this.enabled && !this.stopped; }
  enable() { this.stopped = false; this.enabled = true; this.stamps = []; try { this.ensureHelper(); } catch (_) { /* spawned on first use */ } this.emit('enabled'); }
  disable() { this.enabled = false; this.kill('disabled'); this.emit('disabled'); }
  stop() { this.stopped = true; this.kill('emergency_stop'); this.emit('stopped'); }
  kill(reason) {
    const helper = this.helper; this.helper = null;
    if (helper) { try { helper.kill(); } catch (_) { /* already gone */ } }
    for (const {resolve, timer} of this.pending.values()) { clearTimeout(timer); resolve({ok: false, error: reason}); }
    this.pending.clear(); this.buffer = '';
  }
  problem(a) {
    if (this.stopped) return 'emergency_stop';
    if (!this.enabled) return 'control_disabled';
    if (!a || !KINDS.has(a.kind)) return 'action_not_allowed';
    if (['move', 'click'].includes(a.kind) && !(Number.isInteger(a.x) && Number.isInteger(a.y))) return 'missing_coordinates';
    if (a.kind === 'click' && !['left', 'right'].includes(a.button || 'left')) return 'button_not_allowed';
    if (Number.isInteger(a.x) && Number.isInteger(a.y)) {
      const b = this.getBounds();
      if (a.x < b.x || a.y < b.y || a.x >= b.x + b.width || a.y >= b.y + b.height) return 'out_of_bounds';
    }
    if (a.kind === 'scroll' && !(Number.isInteger(a.amount) && Math.abs(a.amount) <= 20 && a.amount !== 0)) return 'bad_amount';
    if (a.kind === 'key') {
      const c = normalize(a.key || ''); if (!c || BLOCKED.has(c)) return 'key_blocked';
      if (a.hold_ms !== undefined && a.hold_ms !== null && !(Number.isInteger(a.hold_ms) && a.hold_ms >= 0 && a.hold_ms <= 2000)) return 'bad_hold';
    }
    if (a.kind === 'type') {
      if (a.focus_is_secret) return 'secret_field';
      if (typeof a.text !== 'string' || !a.text || a.text.length > MAX_TYPE) return 'text_length';
      if (SECRET.test(a.text) || Object.entries(this.env).some(([k, v]) => /key|token|secret|password/i.test(k) && v && v.length >= 8 && a.text.includes(v))) return 'secret_text';
    }
    const t = this.now();
    this.stamps = this.stamps.filter(s => t - s < 60000);
    if (this.stamps.length >= PER_MINUTE || this.stamps.filter(s => t - s < 1000).length >= PER_SECOND) return 'rate_limited';
    this.stamps.push(t);
    return '';
  }
  ensureHelper() {
    if (this.helper) return this.helper;
    const helper = this.helper = this.spawnHelper();
    this.ready = new Promise(resolve => { this.markReady = resolve; });
    helper.stdout.on('data', chunk => {
      this.buffer += chunk;
      let i;
      while ((i = this.buffer.indexOf('\n')) >= 0) {
        const line = this.buffer.slice(0, i).trim(); this.buffer = this.buffer.slice(i + 1);
        let reply; try { reply = JSON.parse(line); } catch (_) { continue; }
        if (reply.ready) { this.markReady(); continue; }
        const entry = this.pending.get(reply.id);
        if (entry) { clearTimeout(entry.timer); this.pending.delete(reply.id); entry.resolve({ok: !!reply.ok, error: reply.error, data: reply}); }
      }
    });
    helper.on('exit', code => { if (this.helper === helper) { this.kill('helper_exited'); this.emit(`helper_exited:${code}`); } });
    return helper;
  }
  // Resolves {ok, error}; never throws. A timeout means the effect is unknown, not success.
  execute(action) {
    const reason = this.problem(action);
    if (reason) return Promise.resolve({ok: false, error: reason});
    return this.send(action);
  }
  // Read-only foreground window query (title, process, rect, password-focus). Only while active.
  queryWindow() {
    if (!this.active) return Promise.resolve({ok: false, error: this.stopped ? 'emergency_stop' : 'control_disabled'});
    return this.send({kind: 'window'});
  }
  async send(action) {
    // A cold helper compiles its C# first; wait for its ready line (nothing was sent yet, so no side effect).
    let helper;
    try { helper = this.ensureHelper(); } catch (e) { return {ok: false, error: 'helper_unavailable'}; }
    const ready = await Promise.race([this.ready.then(() => true), new Promise(r => setTimeout(() => r(false), READY_TIMEOUT_MS))]);
    if (!ready || this.helper !== helper) return {ok: false, error: this.stopped ? 'emergency_stop' : 'helper_unavailable'};
    if (this.stopped || !this.enabled) return {ok: false, error: this.stopped ? 'emergency_stop' : 'control_disabled'};
    const id = ++this.seq;
    return new Promise(resolve => {
      const timer = setTimeout(() => { this.pending.delete(id); resolve({ok: false, error: 'outcome_unknown'}); }, TIMEOUT_MS);
      this.pending.set(id, {resolve, timer});
      try { helper.stdin.write(JSON.stringify({...action, id}) + '\n'); }
      catch (e) { clearTimeout(timer); this.pending.delete(id); resolve({ok: false, error: 'helper_unavailable'}); }
    });
  }
}

module.exports = {ComputerControl, normalize};
