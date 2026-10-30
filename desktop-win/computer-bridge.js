'use strict';
// Long-polls the backend for commands, runs them through ComputerControl, posts the results.
// Polls only while control is active, so the backend sees the executor offline when it is off.
const HEADER = 'X-SIRO-Computer-Token';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

class ComputerBridgeClient {
  constructor({origin, token, control, observe, fetchImpl = fetch, pollTimeoutMs = 30000}) {
    Object.assign(this, {origin, token, control, observe, fetchImpl, pollTimeoutMs});
    this.running = false;
    control.listeners.push(state => this.mirror(state));
  }
  get configured() { return typeof this.token === 'string' && this.token.length >= 32; }
  start() {
    if (!this.configured || this.running) return;
    this.running = true;
    this.loop();
  }
  halt() { this.running = false; }
  post(path, body) {
    return this.fetchImpl(`${this.origin}/v1/computer${path}`, {
      method: 'POST', headers: {[HEADER]: this.token, 'Content-Type': 'application/json'},
      body: JSON.stringify(body || {}), signal: AbortSignal.timeout(this.pollTimeoutMs),
    });
  }
  // Mirrors the owner's tray switch and the emergency stop to the backend (best effort).
  mirror(state) {
    if (!this.configured) return;
    const request = state === 'stopped' ? this.post('/stop') : state === 'enabled' || state === 'disabled' ? this.post('/state', {enabled: state === 'enabled'}) : null;
    if (request) request.catch(() => {});
  }
  async handle(command) {
    if (command.op === 'observe') return this.observe();
    if (command.op === 'input') return this.control.execute(command.payload);
    if (command.op === 'focus') return this.control.focus(command.payload && command.payload.process);
    return {ok: false, error: 'unknown_op'};
  }
  async loop() {
    let backoff = 500;
    while (this.running) {
      if (!this.control.active) { await sleep(500); continue; }
      try {
        const response = await this.post('/poll');
        if (response.status === 204) { backoff = 500; continue; }
        if (!response.ok) throw new Error(`poll ${response.status}`);
        const command = await response.json();
        const result = await this.handle(command);
        await this.post('/result', {id: command.id, ok: !!result.ok, error: result.error || '', data: result.data || null});
        backoff = 500;
      } catch (_) {
        await sleep(backoff); backoff = Math.min(backoff * 2, 5000);
      }
    }
  }
}

module.exports = {ComputerBridgeClient, HEADER};
