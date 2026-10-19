// Compiles src/harness.ts + the licensed SDK Framework sources (read in place) into build/harness.js
// using the rolldown bundler already present in the SDK's Demo node_modules (no installs).
// build/ contains compiled SDK code: local testing only, do not redistribute.
'use strict';
const path = require('path');

const SDK = process.env.CUBISM_SDK ||
  '/home/jasonliao/文件/Siro/SiroV2/models/live2d-sdk-5-r.5/CubismSdkForWeb-5-r.5';
const ROOT = path.resolve(__dirname, '..');

async function build() {
  const { rolldown } = require(path.join(SDK, 'Samples/TypeScript/Demo/node_modules/rolldown'));
  const bundle = await rolldown({
    input: path.join(ROOT, 'src/harness.ts'),
    resolve: { alias: { '@sdk': path.join(SDK, 'Framework/src') } },
    logLevel: 'warn'
  });
  await bundle.write({ file: path.join(ROOT, 'build/harness.js'), format: 'iife', sourcemap: true });
  await bundle.close();
  return path.join(ROOT, 'build/harness.js');
}

module.exports = { build, SDK };
if (require.main === module) build().then(f => console.log('built', f)).catch(e => { console.error(e); process.exit(1); });
