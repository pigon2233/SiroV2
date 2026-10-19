// Read-only loopback HTTP server (127.0.0.1, ephemeral port) for the harness.
// Routes:
//   /                      -> web/index.html
//   /build/<file>          -> build/<file>
//   /sdk-core/<file>       -> <SDK>/Core/<file>                  (licensed SDK, served locally only)
//   /sdk-shaders/<file>    -> <SDK>/Framework/Shaders/WebGL/<file>
//   /m/<label>/<relpath>   -> files under a registered model folder (read-only)
//   /f/<key>               -> a single registered file (e.g. a motion3.json given on the CLI)
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const { SDK } = require('./build.cjs');

const ROOT = path.resolve(__dirname, '..');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.map': 'application/json', '.json': 'application/json',
  '.png': 'image/png', '.vert': 'text/plain', '.frag': 'text/plain', '.moc3': 'application/octet-stream' };

function within(base, rel) {
  const p = path.resolve(base, rel);
  return p === base || p.startsWith(base + path.sep) ? p : null;
}

function start() {
  const folders = new Map();
  const files = new Map();
  const log = [];
  const server = http.createServer((req, res) => {
    const url = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    let file = null;
    if (url === '/') file = path.join(ROOT, 'web/index.html');
    else if (url.startsWith('/build/')) file = within(path.join(ROOT, 'build'), url.slice(7));
    else if (url.startsWith('/sdk-core/')) file = within(path.join(SDK, 'Core'), url.slice(10));
    else if (url.startsWith('/sdk-shaders/')) file = within(path.join(SDK, 'Framework/Shaders/WebGL'), url.slice(13));
    else if (url.startsWith('/m/')) {
      const [, , label, ...rest] = url.split('/');
      const base = folders.get(label);
      if (base) file = within(base, rest.join('/'));
    } else if (url.startsWith('/f/')) file = files.get(url.slice(3)) || null;
    log.push(`${req.method} ${url} -> ${file ? 'ok' : 'none'}`);
    if (req.method !== 'GET' || !file || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      res.writeHead(404); res.end('not found'); return;
    }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => {
    const { port } = server.address();
    resolve({
      origin: `http://127.0.0.1:${port}`,
      addFolder(label, dir) { folders.set(label, path.resolve(dir)); return `/m/${label}/`; },
      addFile(key, f) { files.set(key, path.resolve(f)); return `/f/${key}`; },
      log,
      close: () => new Promise(r => server.close(r))
    });
  }));
}

module.exports = { start };
