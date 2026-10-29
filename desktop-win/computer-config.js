'use strict';
// Desktop-control config shared with the WSL launcher: %USERPROFILE%\siro-computer\computer.env.
// No file (or no token) = the feature stays off. Only SIRO_COMPUTER_* keys are read.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const DEFAULT_FILE = path.join(os.homedir(), 'siro-computer', 'computer.env');

function readComputerEnv(file = process.env.SIRO_COMPUTER_ENV_FILE || DEFAULT_FILE) {
  let text;
  try { text = fs.readFileSync(file, 'utf8'); } catch (_) { return {}; }
  const values = {};
  for (const raw of text.split(/\r?\n/)) {
    const match = /^\s*(?:export\s+)?(SIRO_COMPUTER_[A-Z_]+)\s*=\s*(.*?)\s*$/.exec(raw);
    if (match) values[match[1]] = match[2].replace(/^(['"])(.*)\1$/, '$2');
  }
  return values;
}

// An explicit environment variable wins over the file.
function computerToken(env = process.env, file) {
  return env.SIRO_COMPUTER_TOKEN || readComputerEnv(file).SIRO_COMPUTER_TOKEN || '';
}

module.exports = {readComputerEnv, computerToken, DEFAULT_FILE};
