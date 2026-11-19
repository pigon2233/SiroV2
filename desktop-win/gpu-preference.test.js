'use strict';
const test = require('node:test');
const assert = require('node:assert');
const {
  petGpuPlan, preferenceFromRegQuery, regAddArgs, appendGpuQuery, applyWindowsGpuPreference,
  WINDOWS_GPU_KEY,
} = require('./gpu-preference.js');

test('the pet uses the integrated GPU unless asked otherwise', () => {
  for (const env of [undefined, null, '', 'low-power', '  low-power  ']) {
    const plan = petGpuPlan(env, null);
    assert.deepStrictEqual(plan.switches, ['force_low_power_gpu']);
    assert.strictEqual(plan.powerPreference, 'low-power');
    assert.strictEqual(plan.registry, 'GpuPreference=1;');
  }
  const high = petGpuPlan('high-performance', null);
  assert.deepStrictEqual(high.switches, []);
  assert.strictEqual(high.powerPreference, 'high-performance');
  assert.strictEqual(high.registry, 'GpuPreference=2;');
  assert.deepStrictEqual(petGpuPlan('discrete', null).switches, []);
  assert.strictEqual(petGpuPlan('discrete', null).registry, 'GpuPreference=2;');
  const leave = petGpuPlan('default', null);
  assert.deepStrictEqual(leave.switches, []);
  assert.strictEqual(leave.powerPreference, null);
  assert.strictEqual(leave.registry, null);
  assert.strictEqual(petGpuPlan('typo', null).mode, 'default');
});

test('an existing Windows GPU choice is kept until the owner names one', () => {
  assert.strictEqual(petGpuPlan(undefined, 'GpuPreference=2;').registry, null);
  assert.strictEqual(petGpuPlan('', 'GpuPreference=1;').registry, null);
  assert.strictEqual(petGpuPlan('low-power', 'GpuPreference=2;').registry, 'GpuPreference=1;');
  assert.strictEqual(petGpuPlan('high-performance', 'GpuPreference=1;').registry, 'GpuPreference=2;');
  assert.strictEqual(petGpuPlan('high-performance', 'GpuPreference=2;').registry, null);
  assert.strictEqual(petGpuPlan('default', 'GpuPreference=2;').registry, null);
});

test('registry text and desktop renderer URLs stay specific', () => {
  assert.strictEqual(preferenceFromRegQuery('    REG_SZ    GpuPreference=1\r\n'), 'GpuPreference=1;');
  assert.strictEqual(preferenceFromRegQuery('no value'), null);
  const exe = 'C:\\SIRO\\desktop-win\\node_modules\\electron\\dist\\electron.exe';
  assert.deepStrictEqual(regAddArgs(exe, 'GpuPreference=1;'), [
    'add', WINDOWS_GPU_KEY, '/v', exe, '/t', 'REG_SZ', '/d', 'GpuPreference=1;', '/f',
  ]);
  const desktop = 'http://127.0.0.1:8000/vrm/?presentation=desktop';
  assert.strictEqual(appendGpuQuery(desktop, 'low-power'), `${desktop}&gpu=low-power`);
  assert.strictEqual(appendGpuQuery(`${desktop}&gpu=low-power`, 'low-power'), `${desktop}&gpu=low-power`);
  assert.strictEqual(appendGpuQuery('http://127.0.0.1:8000/vrm/', 'low-power'), 'http://127.0.0.1:8000/vrm/');
  assert.strictEqual(appendGpuQuery(desktop, null), desktop);
});

test('the registry is not touched off Windows or when the plan is a no-op', () => {
  const calls = [];
  const execFile = (cmd, args, options, done) => { calls.push({cmd, args, options}); done?.(null, ''); };
  applyWindowsGpuPreference({platform: 'linux', envValue: '', exePath: 'electron.exe', execFile});
  assert.strictEqual(calls.length, 0);
  applyWindowsGpuPreference({platform: 'win32', envValue: 'default', exePath: 'electron.exe', execFile});
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].cmd, 'reg');
  calls[0] = null;
  const busy = [];
  const queryThen = (cmd, args, options, done) => {
    busy.push(args[0]);
    if (args[0] === 'query') done(null, '    REG_SZ    GpuPreference=2;');
    else done(null, '');
  };
  applyWindowsGpuPreference({platform: 'win32', envValue: undefined, exePath: 'C:\\electron.exe', execFile: queryThen});
  assert.deepStrictEqual(busy, ['query']);
});
