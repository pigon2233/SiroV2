'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {processNameKey, ComputerControl} = require('./computer-control.js');
const cases = require('../tests/fixtures/computer-process-names.json');

test('exact canonical vectors match backend/native without prefix widening', () => {
  for (const [left,right,expected] of cases) {
    assert.equal(!!processNameKey(left) && processNameKey(left) === processNameKey(right), expected, `${left}/${right}`);
  }
});

test('normalized focus remains off and explicitly boolean gated', async () => {
  const calls=[];
  const control = new ComputerControl({getBounds: () => ({x:0,y:0,width:100,height:100})});
  control.send = async value => {calls.push(value); return {ok:true};}; // fake only; never spawn helper
  assert.equal((await control.focus('Slay the Spire 2',true)).error,'control_disabled');
  control.enabled=true; // only the fake instance
  assert.equal((await control.focus('Slay the Spire 2')).error,'bad_process');
  assert.equal((await control.focus('Slay the Spire 2','true')).error,'bad_process');
  assert.equal((await control.focus('Slay the Spire 2',true)).ok,true);
  assert.deepEqual(calls,[{kind:'focus',process:'Slay the Spire 2',normalize_process_names:true}]);
  for (const bad of ['../game','C:game','---','game\\x']) assert.equal((await control.focus(bad,true)).error,'bad_process');
  control.stop();
  assert.equal((await control.focus('slaythespire2',true)).error,'emergency_stop');
});

test('authenticated bridge forwards only an explicit true normalization flag', async () => {
  const {ComputerBridgeClient} = require('./computer-bridge.js');
  const calls=[];
  const control={listeners:[],focus:async (...args) => {calls.push(args);return {ok:true};}};
  const client=new ComputerBridgeClient({origin:'http://localhost',token:'x'.repeat(32),control,observe:async()=>{throw Error('no capture');}});
  for (const flag of [true,'1',undefined]) await client.handle({op:'focus',payload:{process:'slaythespire2',normalize_process_names:flag}});
  assert.deepEqual(calls,[['slaythespire2',true],['slaythespire2',false],['slaythespire2',false]]);
});
