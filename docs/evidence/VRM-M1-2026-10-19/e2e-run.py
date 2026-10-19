"""E2E: real create_app + uvicorn + owner VRM + headless Chromium."""
import asyncio, json, sys, threading, time, importlib.util
from pathlib import Path
import uvicorn
from playwright.sync_api import sync_playwright

ROOT = Path("/home/claude/SiroV2")
S = Path(sys.argv[1])
OUT = S / "e2e"
spec = importlib.util.spec_from_file_location("prep", ROOT / "scripts/prepare_vrm_renderer.py")
prep = importlib.util.module_from_spec(spec); spec.loader.exec_module(prep)
from siro.adapters.body.web import WebSocketBodyTransport
from siro.adapters.body.assets import verified_vrm_model
from siro.services.presentation.gateway import create_app

manifest = prep.register_model(S / "siro-v2-blender.vrm", OUT / "asset", source_url="https://vroid.com/en/studio",
    license_url="https://vroid.com/en/studio/terms", license_name="VRoid Studio terms (owner-created)",
    accepted_by="owner", force=True)
PORT = 8765
transport = WebSocketBodyTransport()
app = create_app(allowed_origins={f"http://127.0.0.1:{PORT}"}, body_transport=transport,
                 vrm_dist=S / "vrm-dist", vrm_model=verified_vrm_model(manifest))
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
loop = asyncio.new_event_loop()
threading.Thread(target=lambda: loop.run_until_complete(server.serve()), daemon=True).start()
while not server.started: time.sleep(0.1)

def send(msg):
    asyncio.run_coroutine_threadsafe(transport.send(msg), loop).result(5)

report = {}
exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx = b.new_context(viewport={"width": 540, "height": 960})
    ctx.add_init_script("window.__posted=[];addEventListener('message',e=>__posted.push(e.data&&e.data.type))")
    page = ctx.new_page()
    msgs = []
    page.on("console", lambda m: msgs.append(m.text))
    page.goto(f"http://127.0.0.1:{PORT}/")
    report["index_iframe_src"] = page.eval_on_selector("iframe", "f => f.getAttribute('src')") if page.query_selector("iframe") else None
    page.goto(f"http://127.0.0.1:{PORT}/vrm/")
    page.wait_for_function("window.__siroVrm && window.__siroVrm.loaded()", timeout=90000)
    deadline = time.time() + 30
    while not asyncio.run_coroutine_threadsafe(asyncio.sleep(0, transport.connected), loop).result(): 
        assert time.time() < deadline, "renderer never authenticated"; time.sleep(0.2)
    report["connected"] = True
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "01-neutral.png"))
    for name in ["happy", "sad", "surprised", "angry", "relaxed"]:
        send({"v": 1, "type": "body.emotion", "name": name, "intensity": 1})
        page.wait_for_function(f"document.documentElement.dataset.siroEmotion === '{name}'", timeout=30000)
        page.wait_for_timeout(800)
        report[f"expr_{name}"] = page.evaluate(f"window.__siroVrm.expression('{name}')")
        page.screenshot(path=str(OUT / f"02-{name}.png"))
    send({"v": 1, "type": "body.look", "x": 1, "y": 0.3})
    page.wait_for_timeout(600)
    report["look_target"] = page.evaluate("window.__siroVrm.lookTarget()")
    send({"v": 1, "type": "body.gesture", "name": "nod"})
    page.wait_for_timeout(350)
    report["nod_pitch"] = page.evaluate("window.__siroVrm.neckPitch()")
    send({"v": 1, "type": "body.speech", "intent_id": "i", "generation_id": "g", "text": "測試", "prosody": {}})
    report["speech_synth_used"] = page.evaluate("typeof speechSynthesis !== 'undefined' && speechSynthesis.speaking")
    f0 = page.evaluate("window.__siroVrm.frames()"); page.wait_for_timeout(2000)
    report["fps_web"] = (page.evaluate("window.__siroVrm.frames()") - f0) / 2
    d = ctx.new_page()
    d.goto(f"http://127.0.0.1:{PORT}/vrm/?presentation=desktop")
    d.wait_for_function("window.__siroVrm && window.__siroVrm.loaded()", timeout=90000)
    page.wait_for_timeout(3000)
    report["web_posted"] = page.evaluate("[...new Set(__posted)]")
    report["web_detached_by_desktop"] = "siro.renderer.detached" in report["web_posted"]
    report["desktop_owns_transport"] = d.evaluate("[...new Set(__posted)]")
    d.wait_for_timeout(1500)
    f0 = d.evaluate("window.__siroVrm.frames()"); d.wait_for_timeout(2000)
    report["fps_desktop"] = (d.evaluate("window.__siroVrm.frames()") - f0) / 2
    d.screenshot(path=str(OUT / "03-desktop-transparent.png"), omit_background=True)
    report["console_errors"] = [m for m in msgs if "rror" in m]
    b.close()
server.should_exit = True
print(json.dumps(report, indent=1, ensure_ascii=False))
(OUT / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
