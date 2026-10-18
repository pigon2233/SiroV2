"""CP-P01 real-renderer probe: real gateway + body WS + Haru build, parameters read per frame.

Usage (from the repo root, licensed SDK build outside Git):
    PYTHONPATH=src python docs/evidence/CP-P01-2026-10-18/renderer_probe.py DIST OUT.json

DIST is a renderer built by scripts/repair_companion_renderer.py. The only diagnostic hook is
a probe-side wrapper around Live2DCubismCore.Model.fromMoc that exposes the model's parameter
arrays to the page; production code is not changed. No audio, provider or user data is used.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from pathlib import Path

import uvicorn
from playwright.async_api import Route, async_playwright

from siro.adapters.body.visual_pack import load_visual_pack
from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.ports.body import EmotionIntent, SpeechIntent
from siro.services.presentation.gateway import DEFAULT_BODY_PACK, create_app

IDS = [
    "ParamAngleX",
    "ParamAngleY",
    "ParamAngleZ",
    "ParamBodyAngleX",
    "ParamBodyAngleY",
    "ParamBodyAngleZ",
    "ParamMouthOpenY",
    "ParamBreath",
    "ParamEyeLOpen",
]
HOOK = """
;(function () {
  const original = Live2DCubismCore.Model.fromMoc;
  Live2DCubismCore.Model.fromMoc = function (moc) {
    const model = original.call(this, moc);
    (window.__siroModels = window.__siroModels || []).push(model);
    return model;
  };
})();
"""
SAMPLER = """
(ids) => {
  window.__siroFrames = []; window.__siroEvents = [];
  window.addEventListener('message', event => {
    if (event.data && event.data.type === 'siro.renderer.activity')
      window.__siroEvents.push({t: performance.now(), ...event.data});
  });
  const model = window.__siroModels[window.__siroModels.length - 1];
  const index = Object.fromEntries(ids.map(id => [id, model.parameters.ids.indexOf(id)]));
  const sample = () => {
    const row = {t: performance.now(), activity: document.documentElement.dataset.siroActivity ||
      'stock', expression: document.documentElement.dataset.siroExpression || ''};
    for (const id of ids) row[id] = model.parameters.values[index[id]];
    window.__siroFrames.push(row);
    requestAnimationFrame(sample);
  };
  requestAnimationFrame(sample);
  return index;
}
"""


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


async def main(dist: Path, out: Path) -> None:
    pack = load_visual_pack(DEFAULT_BODY_PACK, dist)
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    transport = WebSocketBodyTransport()
    body = MinimalWebBodyAdapter(transport, activity_pack=pack)
    app = create_app(
        allowed_origins={origin},
        body_transport=transport,
        live2d_dist=dist,
        body_pack=pack,
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    serving = asyncio.create_task(server.serve())
    marks: list[dict[str, object]] = []
    loop = asyncio.get_running_loop()
    try:
        while not server.started:
            await asyncio.sleep(0.05)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path="/usr/bin/google-chrome",
                headless=True,
                args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
            )
            page = await browser.new_page(viewport={"width": 640, "height": 640})

            async def hook(route: Route) -> None:
                response = await route.fetch()
                await route.fulfill(response=response, body=(await response.text()) + HOOK)

            await page.route("**/Core/live2dcubismcore.js", hook)
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(f"{origin}/live2d/")
            await page.wait_for_function(
                "document.documentElement.dataset.siroPack === 'siro.haru.upperbody@0.1.0'"
                " && (window.__siroModels || []).length > 0",
                timeout=30000,
            )
            while not transport.connected:
                await asyncio.sleep(0.05)
            await page.wait_for_function("document.documentElement.dataset.siroExpression")
            index = await page.evaluate(SAMPLER, IDS)
            start = loop.time()

            async def at(seconds: float, label: str, action: object) -> None:
                await asyncio.sleep(max(0.0, start + seconds - loop.time()))
                page_ms = await page.evaluate("performance.now()")
                marks.append({"t": round(loop.time() - start, 3), "page_ms": page_ms, "label": label})
                assert callable(action)
                await action()

            await at(0.0, "emotion angry (F03)", lambda: body.set_emotion(EmotionIntent("angry")))
            await at(1.0, "reading_pose", lambda: body.set_activity("reading_pose", generation_id="g1"))
            await at(3.0, "attention", lambda: body.set_activity("attention", generation_id="g1"))
            await at(5.0, "nod", lambda: body.set_activity("nod", generation_id="g1"))
            await at(7.5, "speech 1", lambda: body.speak(SpeechIntent("s1", "我在這裡，先看一下。", "g2")))
            await at(8.5, "cancel", lambda: body.cancel("active", "probe"))
            await at(10.0, "speech 2", lambda: body.speak(SpeechIntent("s2", "新的回覆。", "g3")))
            await at(12.5, "thinking", lambda: body.set_activity("thinking", generation_id="g4"))
            repeat = dict(transport._activity or {})  # noqa: SLF001 - probe resends the exact intent

            async def twenty() -> None:
                for _ in range(20):
                    await transport.send(dict(repeat))

            await at(13.5, "same thinking intent x20", twenty)

            async def reconnect() -> None:
                await transport.detach(reason="probe network drop")

            await at(14.5, "body socket dropped (renderer reconnects)", reconnect)
            await at(17.0, "stop activity", body.stop_activity)
            await asyncio.sleep(max(0.0, start + 19.0 - loop.time()))
            frames = await page.evaluate("window.__siroFrames")
            events = await page.evaluate("window.__siroEvents")
            await browser.close()
    finally:
        server.should_exit = True
        await serving
    t0 = frames[0]["t"]
    for row in frames:
        row["t"] = round((row["t"] - t0) / 1000, 4)
    for event in events:
        event["t"] = round((event["t"] - t0) / 1000, 4)
    for mark in marks:
        mark["frame_t"] = round((float(mark.pop("page_ms")) - t0) / 1000, 4)
    out.write_text(
        json.dumps(
            {
                "fixture": "real gateway create_app + WebSocketBodyTransport + Haru 5-r.5 build; "
                "headless Chrome SwiftShader; no audio",
                "pack": f"{pack.pack_id}@{pack.version}",
                "pack_digest": pack.digest,
                "parameter_index": index,
                "page_errors": errors,
                "marks": marks,
                "events": events,
                "frames": frames,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]).resolve(), Path(sys.argv[2])))
