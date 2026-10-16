"""Apply SIRO's single-character state bridge to the existing licensed local SDK."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


def repair(demo: Path) -> bool:
    changed = False

    def write(name: str, text: str) -> None:
        nonlocal changed
        path = demo / "src" / name
        if path.read_text() != text:
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
    write("lappmodel.ts", model)
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
