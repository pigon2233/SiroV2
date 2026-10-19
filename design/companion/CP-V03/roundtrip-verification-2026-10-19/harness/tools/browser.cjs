'use strict';
// Headless Chrome with software WebGL (SwiftShader via ANGLE). No network: everything is served from 127.0.0.1.
function launchArgs() {
  return {
    executablePath: process.env.CHROME || '/usr/bin/google-chrome',
    headless: true,
    args: [
      '--headless=new', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
      '--ignore-gpu-blocklist', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
      '--disable-background-networking', '--disable-component-update', '--disable-sync', '--metrics-recording-only',
      '--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1', '--force-color-profile=srgb'
    ]
  };
}
module.exports = { launchArgs };
