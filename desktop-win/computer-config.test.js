'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {readComputerEnv, computerToken} = require('./computer-config.js');

function tmpFile(text) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'siro-cfg-'));
  const file = path.join(dir, 'computer.env');
  fs.writeFileSync(file, text);
  return file;
}

test('reads SIRO_COMPUTER_* keys, tolerates CRLF, quotes, export and comments', () => {
  const file = tmpFile('# note\r\nSIRO_COMPUTER_TOKEN="abc123"\r\nexport SIRO_COMPUTER_ALLOWED_PROCESSES=a.exe,b.exe\r\nOTHER_SECRET=nope\r\n');
  assert.deepStrictEqual(readComputerEnv(file), {SIRO_COMPUTER_TOKEN: 'abc123', SIRO_COMPUTER_ALLOWED_PROCESSES: 'a.exe,b.exe'});
});

test('missing file means feature off; env var beats the file', () => {
  assert.deepStrictEqual(readComputerEnv(path.join(os.tmpdir(), 'siro-no-such-file.env')), {});
  assert.strictEqual(computerToken({}, path.join(os.tmpdir(), 'siro-no-such-file.env')), '');
  const file = tmpFile('SIRO_COMPUTER_TOKEN=fromfile\n');
  assert.strictEqual(computerToken({}, file), 'fromfile');
  assert.strictEqual(computerToken({SIRO_COMPUTER_TOKEN: 'fromenv'}, file), 'fromenv');
});
