"""Hit-test SIRO nav links in real headless Firefox (geckodriver) without scrolling."""

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

index = Path(sys.argv[1]).resolve().as_uri()
port = 4499
gd = subprocess.Popen(
    ["geckodriver", "--port", str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)


def call(method, path, body=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["value"]


try:
    time.sleep(2)
    out = {}
    for scale, (w, h) in {
        "960x560": (960, 560),
        "960x500": (960, 500),
        "960x460": (960, 460),
        "1000x420": (1000, 420),
        "1100x400": (1100, 400),
    }.items():
        caps = {
            "capabilities": {
                "alwaysMatch": {"moz:firefoxOptions": {"args": ["-headless"], "prefs": {}}}
            }
        }
        sid = call("POST", "/session", caps)["sessionId"]
        try:
            call("POST", f"/session/{sid}/window/rect", {"width": w, "height": h})
            call("POST", f"/session/{sid}/url", {"url": index + "#/chat"})
            time.sleep(1)
            out[scale] = call(
                "POST",
                f"/session/{sid}/execute/sync",
                {
                    "script": """
const side = document.querySelector('.sidebar'), cs = getComputedStyle(side);
const links = [...document.querySelectorAll('.primary-nav a')].map(a => {

  const r = a.getBoundingClientRect(), x = r.left + r.width/2, y = r.top + r.height/2;
  const hit = document.elementFromPoint(x, y);
  const owner = hit ? (hit.closest('a')?.dataset.nav || hit.className || hit.tagName) : null;
  return [a.dataset.nav, Math.round(y), owner];
});
return {viewport:[innerWidth, innerHeight], dpr: devicePixelRatio, overflowY: cs.overflowY,
  sideClient: side.clientHeight, sideScroll: side.scrollHeight, position: cs.position, links};""",
                    "args": [],
                },
            )
        finally:
            call("DELETE", f"/session/{sid}")
    for k, v in out.items():
        bad = [x for x in v["links"] if x[2] != x[0] or x[1] < 0 or x[1] > v["viewport"][1]]
        print(
            k,
            v["viewport"],
            v["position"],
            v["overflowY"],
            v["sideClient"],
            v["sideScroll"],
            "BAD",
            bad,
        )
finally:
    gd.terminate()
