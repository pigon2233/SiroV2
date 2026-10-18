"""Apply SIRO's single-character state bridge to the existing licensed local SDK."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ACTIVITY_SOURCE = Path(__file__).with_name("companion_renderer") / "siroactivity.ts"
ACTIVITY_IMPORT = "import { siroActivity } from './siroactivity'; // SIRO activity overlay v1\n"
ACTIVITY_FRAME = """    // SIRO activity overlay v1: body IDs after stock motion.
    siroActivity.tick(
      deltaTimeSeconds,
      id => this._model.getParameterValueById(CubismFramework.getIdManager().getId(id)),
      (id, value) => {
        const index = this._model.getParameterIndex(CubismFramework.getIdManager().getId(id));
        const low = this._model.getParameterMinimumValue(index);
        const high = this._model.getParameterMaximumValue(index);
        this._model.setParameterValueByIndex(index, Math.max(low, Math.min(high, value)));
      }
    );
"""
ACTIVITY_BIND = """
            siroActivity.bindModel(id => {
              const index = this._model.getParameterIndex(CubismFramework.getIdManager().getId(id));
              return index >= 0 && index < this._model.getParameterCount();
            });"""
ACTIVITY_BRIDGE = """// SIRO activity bridge v1
// No audio-energy lip sync exists yet, so the renderer never forces ParamMouthOpenY:
// expression and motion keep it. Forcing 0 on cancel pinned it shut for later speech (V01-D01).
function releaseMouth(): void {
  LAppDelegate.getInstance().getSiroManager()?.setSiroMouthOpen(null);
}
function stopSpeaking(): void {
  releaseMouth();
  siroActivity.cancelSpeech();
}
siroActivity.onEvent = event => {
  document.documentElement.dataset.siroActivity = siroActivity.snapshot().activity ?? 'stock';
  window.parent.postMessage({...event, type: 'siro.renderer.activity', event: event.type},
    location.origin);
};
void fetch('/v1/body/pack')
  .then(response => (response.ok ? response.json() : null))
  .catch((): null => null)
  .then(pack => {
    const error = siroActivity.load(pack);
    document.documentElement.dataset.siroPack = error
      ? `unsupported:${error}` : `${pack.pack_id}@${pack.version}`;
  });
function renderSiro(message: Record<string, unknown>): void {
  if (message.v !== 1) return;
  const manager = LAppDelegate.getInstance().getSiroManager();
  if (message.type === 'body.emotion') desiredEmotion = String(message.name);
  else if (message.type === 'body.look') {
    manager?.onDrag(Number(message.x) || 0, Number(message.y) || 0);
  }
  else if (message.type === 'body.speech') releaseMouth();
  else if (message.type === 'body.cancel') stopSpeaking();
  else if (message.type === 'body.activity') {
    siroActivity.request(message as unknown as ActivityIntent);
  }
  // Audible speech has one owner in the parent page. Never synthesize twice or fake lip motion.
}
// End SIRO activity bridge v1
"""


def repair(demo: Path) -> bool:
    changed = False

    def write(name: str, text: str) -> None:
        nonlocal changed
        path = demo / "src" / name
        if not path.is_file() or path.read_text() != text:
            path.write_text(text)
            changed = True

    model = (demo / "src/lappmodel.ts").read_text()
    if "public applySiroExpression" not in model:
        model = model.replace(
            "  public setExpression(expressionId: string): void {",
            """  public applySiroExpression(expressionId: string): boolean {
    if (this._state !== LoadStep.CompleteSetup || !this._expressions.has(expressionId)) {
      return false;
    }
    this.setExpression(expressionId);
    return true;
  }

  public setExpression(expressionId: string): void {""",
        )
    model = model.replace(
        "this._wavFileHandler.start(path);",
        "// Audible speech is owned by the parent page, not sample motion sounds.",
    )
    if "// SIRO activity overlay v1" not in model:
        frame = "    this._model.saveParameters(); // 状態を保存"
        setup = "            this._state = LoadStep.CompleteSetup;"
        if model.count(frame) != 1 or model.count(setup) != 1:
            raise RuntimeError("unsupported SDK model update loop for activity overlay")
        model = ACTIVITY_IMPORT + model.replace(frame, ACTIVITY_FRAME + frame).replace(
            setup, setup + ACTIVITY_BIND
        )
    write("lappmodel.ts", model)
    write("siroactivity.ts", ACTIVITY_SOURCE.read_text())
    manager = (demo / "src/lapplive2dmanager.ts").read_text()
    if "private _siroAppliedModel" not in manager:
        manager = manager.replace(
            "  public setSiroExpression(expressionId: string): void {",
            """  private _siroAppliedModel: LAppModel | null = null;
  private _siroAppliedExpression = '';

  public syncSiroExpression(expressionId: string): boolean {
    const model = this._models[0];
    if (!model) return false;
    if (this._siroAppliedModel === model && this._siroAppliedExpression === expressionId) {
      return true;
    }
    if (!model.applySiroExpression(expressionId)) {
      return false;
    }
    this._siroAppliedModel = model;
    this._siroAppliedExpression = expressionId;
    return true;
  }

  public setSiroExpression(expressionId: string): void {""",
        )
    manager = manager.replace(
        "model.setRandomExpression();",
        "// Facial expression has one owner: the SIRO affect projection.",
    )
    write("lapplive2dmanager.ts", manager)
    main = (demo / "src/main.ts").read_text()
    if "// SIRO persistent presentation v2" not in main:
        start = main.index("let mouthTimer:")
        end = main.index("async function connectSiro()", start)
        main = (
            main[:start]
            + """// SIRO persistent presentation v2: one validated Haru mapping; no speech replay.
let desiredEmotion = 'neutral';
let lastAnnounced = '';
const expressions: Record<string, string> = {
  happy: 'F05', sad: 'F08', angry: 'F03', surprised: 'F06', neutral: 'F01'
};
function stopSpeaking(): void {
  LAppDelegate.getInstance().getSiroManager()?.setSiroMouthOpen(0);
}
function renderSiro(message: Record<string, unknown>): void {
  if (message.v !== 1) return;
  const manager = LAppDelegate.getInstance().getSiroManager();
  if (message.type === 'body.emotion') desiredEmotion = String(message.name);
  else if (message.type === 'body.look') {
    manager?.onDrag(Number(message.x) || 0, Number(message.y) || 0);
  }
  else if (message.type === 'body.cancel') stopSpeaking();
  // Audible speech has one owner in the parent page. Never synthesize twice or fake lip motion.
}
window.setInterval(() => {
  const expression = expressions[desiredEmotion] ?? 'F01';
  if (!LAppDelegate.getInstance().getSiroManager()?.syncSiroExpression(expression)) return;
  document.documentElement.dataset.siroEmotion = desiredEmotion;
  document.documentElement.dataset.siroExpression = expression;
  if (lastAnnounced !== desiredEmotion) {
    window.parent.postMessage(
      {type:'siro.renderer.ready', emotion:desiredEmotion, character:'Haru'}, location.origin
    );
    lastAnnounced = desiredEmotion;
  }
}, 100);

"""
            + main[end:]
        )
    if "// SIRO activity bridge v1" in main:
        main = re.sub(
            r"// SIRO activity bridge v1.*?// End SIRO activity bridge v1\n",
            lambda _: ACTIVITY_BRIDGE,
            main,
            count=1,
            flags=re.S,
        )
    else:
        start = main.index("function stopSpeaking(): void {")
        end = main.index("window.setInterval(() => {", start)
        main = main[:start] + ACTIVITY_BRIDGE + main[end:]
    activity_import = "import { siroActivity, type ActivityIntent } from './siroactivity';\n"
    if activity_import not in main:
        main = main.replace(
            "import * as LAppDefine from './lappdefine';\n",
            "import * as LAppDefine from './lappdefine';\n" + activity_import,
            1,
        )
        if activity_import not in main:
            main = activity_import + main
    # Keep reconnect ownership independent of the emotion/mouth projection above.
    # An explicitly replaced renderer must never reclaim the one body socket.
    connection = """// SIRO renderer ownership v3
let siroDetached = false;
let siroRetryTimer: number | undefined;
let siroSocket: WebSocket | undefined;
function scheduleSiroReconnect(): void {
  if (!siroDetached && siroRetryTimer === undefined) {
    siroRetryTimer = window.setTimeout(() => {
      siroRetryTimer = undefined;
      void connectSiro();
    }, 1000);
  }
}
async function connectSiro(): Promise<void> {
  if (siroDetached) return;
  try {
    const session = await fetch('/v1/session', {
      method: 'POST', headers: { Origin: location.origin }
    });
    if (!session.ok) throw new Error(`session ${session.status}`);
    const { token } = await session.json();
    if (siroDetached) return;
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${scheme}://${location.host}/ws/body`);
    siroSocket = socket;
    socket.addEventListener('open', () => {
      if (siroDetached || siroSocket !== socket) { socket.close(); return; }
      const presentation = new URLSearchParams(location.search).get('presentation');
      socket.send(JSON.stringify({
        type: 'authenticate', token,
        ...(presentation === 'desktop' ? {presentation: 'desktop'} : {})
      }));
    });
    socket.addEventListener('message', event => {
      if (siroDetached || siroSocket !== socket) return;
      renderSiro(JSON.parse(event.data));
    });
    socket.addEventListener('close', event => {
      if (siroSocket !== socket) return;
      siroSocket = undefined;
      stopSpeaking();
      if (event.reason === 'renderer replaced' || event.reason === 'desktop owner active') {
        siroDetached = true;
        if (siroRetryTimer !== undefined) window.clearTimeout(siroRetryTimer);
        siroRetryTimer = undefined;
        window.parent.postMessage({type: 'siro.renderer.detached'}, location.origin);
      } else scheduleSiroReconnect();
    });
  } catch (_) {
    scheduleSiroReconnect();
  }
}
window.addEventListener('pagehide', () => {
  siroDetached = true;
  if (siroRetryTimer !== undefined) window.clearTimeout(siroRetryTimer);
  siroRetryTimer = undefined;
  siroSocket?.close();
});
// End SIRO renderer ownership v3"""
    if "// SIRO renderer ownership v3" in main:
        main = re.sub(
            r"// SIRO renderer ownership v3.*?// End SIRO renderer ownership v3",
            lambda _: connection,
            main,
            count=1,
            flags=re.S,
        )
    else:
        main, count = re.subn(
            r"async function connectSiro\(\): Promise<void> \{.*?\n\}",
            lambda _: connection,
            main,
            count=1,
            flags=re.S,
        )
        if count != 1:
            raise RuntimeError("expected exactly one renderer connection bridge")
    if "// SIRO desktop click-to-chat" not in main:
        main += """
// SIRO desktop click-to-chat: only the displayed local character initiates this UI action.
let desktopPress: {x: number; y: number} | undefined;
window.addEventListener('pointerdown', event => {
  if (new URLSearchParams(location.search).get('presentation') === 'desktop' && event.button === 0)
    desktopPress = {x: event.screenX, y: event.screenY};
});
window.addEventListener('pointerup', event => {
  const press = desktopPress; desktopPress = undefined;
  if (press && Math.hypot(event.screenX - press.x, event.screenY - press.y) < 8)
    window.parent.postMessage({type:'siro.renderer.interact'}, location.origin);
});
"""
    write("main.ts", main)
    define = (demo / "src/lappdefine.ts").read_text()
    define = re.sub(
        r"export const ModelDir: string\[\] = \[.*?\];",
        "export const ModelDir: string[] = ['Haru'];",
        define,
        flags=re.S,
    )
    write("lappdefine.ts", define)
    view = (demo / "src/lappview.ts").read_text()
    view = view.replace(
        "this._gear.render(this._programId);",
        "// Single verified character: no unverified model-switch control.",
    )
    view = view.replace(
        "lapplive2dmanager.nextScene();",
        "// Character selection remains fixed until emotion mappings are verified.",
    )
    view = view.replace(
        "this._back.render(this._programId);",
        "// Use the companion page background instead of the SDK classroom.",
    )
    write("lappview.ts", view)
    delegate = (
        (demo / "src/lappsubdelegate.ts")
        .read_text()
        .replace("gl.clearColor(0.0, 0.0, 0.0, 1.0);", "gl.clearColor(0.0, 0.0, 0.0, 0.0);")
    )
    write("lappsubdelegate.ts", delegate)
    render_loop = demo / "src/lappdelegate.ts"
    if render_loop.is_file():
        loop_source = render_loop.read_text()
        if "SIRO desktop frame budget" not in loop_source:
            original = "    const loop = (): void => {"
            if original not in loop_source:
                raise ValueError("unsupported SDK render loop for desktop frame budget")
            loop_source = loop_source.replace(
                original,
                "    // SIRO desktop frame budget: retain normal web timing.\n"
                "    const desktop = new URLSearchParams(location.search).get('presentation') "
                "=== 'desktop';\n"
                "    let lastDesktopFrame = 0;\n"
                "    const loop = (): void => {\n"
                "      const frameNow = performance.now();\n"
                "      if (desktop && frameNow - lastDesktopFrame < 1000 / 24) {\n"
                "        requestAnimationFrame(loop); return;\n"
                "      }\n"
                "      lastDesktopFrame = frameNow;",
                1,
            )
            render_loop.write_text(loop_source)
            changed = True
    index = demo / "index.html"
    markup = index.read_text()
    if "/* SIRO stage */" not in markup:
        markup = markup.replace(
            "<style>",
            "<style>/* SIRO stage */ html, body { background: "
            "radial-gradient(ellipse at 50% 45%, #49394e, #191c2a 75%); }",
        )
        index.write_text(markup)
        changed = True
    if "/* SIRO desktop transparency */" not in markup:
        markup = markup.replace(
            "</head>",
            """<script>
  if (new URLSearchParams(location.search).get('presentation') === 'desktop') {
    document.documentElement.dataset.siroPresentation = 'desktop';
  }
</script>
<style>/* SIRO desktop transparency */
  html[data-siro-presentation="desktop"],
  html[data-siro-presentation="desktop"] body { background: transparent !important; }
</style>
</head>""",
            1,
        )
        if "/* SIRO desktop transparency */" not in markup:
            raise RuntimeError("expected renderer HTML head")
        index.write_text(markup)
        changed = True
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", type=Path)
    args = parser.parse_args()
    if repair(args.demo) or not (args.demo / "dist/index.html").exists():
        subprocess.run(["npm", "run", "build"], cwd=args.demo, check=True)
    print("Verified single-character renderer bridge ready")


if __name__ == "__main__":
    main()
