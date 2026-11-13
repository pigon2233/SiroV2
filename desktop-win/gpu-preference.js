'use strict';

// Which GPU draws the desktop pet. The default keeps the discrete NVIDIA card
// free for TTS and the language model. Quality and frame caps are unchanged;
// this only chooses the adapter. Windows ANGLE stays on its D3D11 default.

const WINDOWS_GPU_KEY = 'HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences';

function petGpuMode(envValue) {
  const text = envValue == null ? '' : String(envValue).trim().toLowerCase();
  if (text === '' || text === 'low-power') return 'low-power';
  if (text === 'high-performance' || text === 'discrete') return 'high-performance';
  if (text === 'default') return 'default';
  return 'default';
}

function envIsExplicit(envValue) {
  return envValue != null && String(envValue).trim() !== '';
}

// existing is the current UserGpuPreferences data for this exe, or null.
function petGpuPlan(envValue, existing) {
  const mode = petGpuMode(envValue);
  const switches = mode === 'low-power' ? ['force_low_power_gpu'] : [];
  const powerPreference = mode === 'default' ? null : mode;
  let registry = null;
  if (mode === 'high-performance') registry = 'GpuPreference=2;';
  else if (mode === 'low-power' && (!existing || envIsExplicit(envValue))) registry = 'GpuPreference=1;';
  if (registry && existing === registry) registry = null;
  return {mode, switches, powerPreference, registry};
}

function preferenceFromRegQuery(stdout) {
  const match = /REG_SZ\s+(GpuPreference=\d+;?)/i.exec(String(stdout || ''));
  if (!match) return null;
  return match[1].endsWith(';') ? match[1] : `${match[1]};`;
}

function regQueryArgs(exePath) {
  return ['query', WINDOWS_GPU_KEY, '/v', exePath];
}

function regAddArgs(exePath, data) {
  return ['add', WINDOWS_GPU_KEY, '/v', exePath, '/t', 'REG_SZ', '/d', data, '/f'];
}

// Add gpu= to a desktop renderer URL. Other pages are left alone so the
// console stage card does not inherit the pet's adapter hint.
function appendGpuQuery(url, powerPreference) {
  if (powerPreference !== 'low-power' && powerPreference !== 'high-performance') return url;
  let parsed;
  try { parsed = new URL(url); } catch (_) { return url; }
  if (parsed.searchParams.get('presentation') !== 'desktop') return url;
  if (parsed.searchParams.get('gpu') === powerPreference) return url;
  parsed.searchParams.set('gpu', powerPreference);
  return parsed.toString();
}

// Windows reads this key when electron.exe starts, so the launcher runs it
// first. Calling it again from the running app only affects the next launch.
// HKCU only, and only this exe. A value the owner already set is left in place
// unless they explicitly asked for low-power or high-performance.
function applyWindowsGpuPreference({platform, envValue, exePath, execFile}) {
  if (platform !== 'win32' || typeof execFile !== 'function' || !exePath) return;
  execFile('reg', regQueryArgs(exePath), {windowsHide: true}, (err, stdout) => {
    const existing = err ? null : preferenceFromRegQuery(stdout);
    const plan = petGpuPlan(envValue, existing);
    if (!plan.registry) return;
    execFile('reg', regAddArgs(exePath, plan.registry), {windowsHide: true}, () => {});
  });
}

module.exports = {
  WINDOWS_GPU_KEY,
  petGpuMode, petGpuPlan, preferenceFromRegQuery, regQueryArgs, regAddArgs, appendGpuQuery,
  applyWindowsGpuPreference,
};
