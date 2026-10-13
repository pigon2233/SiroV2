#!/usr/bin/env python3
"""Prepare the ignored Cubism Web renderer from the owner-downloaded SDK ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

SDK_SHA256 = (
    "67064a7fb1812cf502f5c4a03bfe12cc638c75a621bb4acf06bb28763df06ba0"  # pragma: allowlist secret
)
SDK_DIR = "CubismSdkForWeb-5-r.5"
DEMO = Path("Samples/TypeScript/Demo")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f"expected one SDK marker in {path}: {old[:60]!r}")
    path.write_text(text.replace(old, new, 1))


def patch_renderer(root: Path) -> None:
    src = root / DEMO / "src"
    replace_once(
        src / "lappmodel.ts",
        "    this._model.update();\n  }\n\n  /**\n   * 引数で指定したモーション",
        """    if (this._siroMouthOpen !== null) {
      this._model.setParameterValueById(
        CubismFramework.getIdManager().getId('ParamMouthOpenY'),
        this._siroMouthOpen
      );
    }

    this._model.update();
  }

  public setSiroMouthOpen(value: number | null): void {
    this._siroMouthOpen = value === null ? null : Math.max(0, Math.min(1, value));
  }

  public stopSiroMotion(): void {
    this._motionManager.stopAllMotions();
    this._expressionManager.stopAllMotions();
    this.setSiroMouthOpen(0);
  }

  /**
   * 引数で指定したモーション""",
    )
    replace_once(
        src / "lappmodel.ts",
        "  /**\n   * イベントの発火を受け取る",
        "  private _siroMouthOpen: number | null = null;\n\n  /**\n   * イベントの発火を受け取る",
    )
    replace_once(
        src / "lapplive2dmanager.ts",
        "  /**\n   * 画面をタップした時の処理",
        """  public setSiroExpression(expressionId: string): void {
    this._models[0]?.setExpression(expressionId);
  }

  public setSiroMouthOpen(value: number | null): void {
    this._models[0]?.setSiroMouthOpen(value);
  }

  public playSiroGesture(): void {
    this._models[0]?.startRandomMotion(
      LAppDefine.MotionGroupTapBody,
      LAppDefine.PriorityForce
    );
  }

  public cancelSiroPresentation(): void {
    this._models[0]?.stopSiroMotion();
  }

  /**
   * 画面をタップした時の処理""",
    )
    replace_once(
        src / "lappdelegate.ts",
        "  /**\n   * 解放する。",
        """  public getSiroManager() {
    return this._subdelegates[0]?.getLive2DManager();
  }

  /**
   * 解放する。""",
    )
    bridge = """
let mouthTimer: number | undefined;
let speechStopTimer: number | undefined;
let activeGeneration: string | undefined;
let activeUtterance: SpeechSynthesisUtterance | undefined;

function stopSpeaking(): void {
  if (mouthTimer !== undefined) window.clearInterval(mouthTimer);
  if (speechStopTimer !== undefined) window.clearTimeout(speechStopTimer);
  mouthTimer = undefined;
  speechStopTimer = undefined;
  if (activeUtterance !== undefined) window.speechSynthesis.cancel();
  activeUtterance = undefined;
  LAppDelegate.getInstance().getSiroManager()?.setSiroMouthOpen(0);
}

function speakText(message: Record<string, unknown>): boolean {
  if (!('speechSynthesis' in window)) return false;
  const prosody = (message.prosody ?? {}) as Record<string, unknown>;
  const utterance = new SpeechSynthesisUtterance(String(message.text ?? ''));
  utterance.lang = 'zh-TW';
  utterance.rate = Math.max(0.5, Math.min(2, Number(prosody.rate) || 1));
  utterance.pitch = Math.max(0, Math.min(2, 1 + (Number(prosody.pitch) || 0)));
  utterance.volume = Math.max(0, Math.min(1, Number(prosody.energy) || 0.5));
  utterance.addEventListener('end', () => {
    if (activeUtterance !== utterance) return;
    stopSpeaking();
    activeGeneration = undefined;
  });
  utterance.addEventListener('error', () => {
    if (activeUtterance !== utterance) return;
    stopSpeaking();
    activeGeneration = undefined;
  });
  activeUtterance = utterance;
  window.speechSynthesis.speak(utterance);
  return true;
}

function renderSiro(message: Record<string, unknown>): void {
  if (message.v !== 1) return;
  const manager = LAppDelegate.getInstance().getSiroManager();
  if (message.type === 'body.emotion') {
    const expressions: Record<string, string> = {
      happy: 'F05', sad: 'F08', angry: 'F03', surprised: 'F06', neutral: 'F01'
    };
    manager?.setSiroExpression(expressions[String(message.name)] ?? 'F05');
  } else if (message.type === 'body.gesture') {
    manager?.playSiroGesture();
  } else if (message.type === 'body.look') {
    manager?.onDrag(Number(message.x) || 0, Number(message.y) || 0);
  } else if (message.type === 'body.speech') {
    activeGeneration = String(message.generation_id);
    stopSpeaking();
    let open = false;
    mouthTimer = window.setInterval(() => {
      open = !open;
      manager?.setSiroMouthOpen(open ? 0.8 : 0.15);
    }, 120);
    if (!speakText(message)) {
      const duration = Math.max(700, Math.min(12000, String(message.text ?? '').length * 110));
      speechStopTimer = window.setTimeout(() => {
        stopSpeaking();
        activeGeneration = undefined;
      }, duration);
    }
  } else if (
    message.type === 'body.cancel' && String(message.generation_id) === activeGeneration
  ) {
    stopSpeaking();
    manager?.cancelSiroPresentation();
    activeGeneration = undefined;
  }
}

async function connectSiro(): Promise<void> {
  try {
    const session = await fetch('/v1/session', {
      method: 'POST', headers: { Origin: location.origin }
    });
    if (!session.ok) throw new Error(`session ${session.status}`);
    const { token } = await session.json();
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${scheme}://${location.host}/ws/body`);
    socket.addEventListener('open', () =>
      socket.send(JSON.stringify({ type: 'authenticate', token }))
    );
    socket.addEventListener('message', event => renderSiro(JSON.parse(event.data)));
    socket.addEventListener('close', event => {
      stopSpeaking();
      if (event.reason !== 'renderer replaced') window.setTimeout(connectSiro, 1000);
    });
  } catch (_) {
    window.setTimeout(connectSiro, 1000);
  }
}
"""
    replace_once(
        src / "main.ts",
        "import * as LAppDefine from './lappdefine';\n",
        "import * as LAppDefine from './lappdefine';\n" + bridge,
    )
    replace_once(
        src / "main.ts",
        "    LAppDelegate.getInstance().run();",
        "    LAppDelegate.getInstance().run();\n    void connectSiro();",
    )
    replace_once(root / DEMO / "vite.config.mts", "    base: '/',", "    base: '/live2d/',")
    replace_once(
        src / "lappdefine.ts",
        "export const ResourcesPath = '../../Resources/';",
        "export const ResourcesPath = '/live2d/Resources/';",
    )
    replace_once(
        src / "lappdefine.ts",
        "export const ShaderPath = '../../Framework/Shaders/WebGL/';",
        "export const ShaderPath = '/live2d/Framework/Shaders/WebGL/';",
    )


def make_manifest(root: Path, accepted_by: str, accepted_at: str) -> None:
    paths = sorted((root / "Core").rglob("*")) + sorted(
        (root / "Samples/Resources/Haru").rglob("*")
    )
    files = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in paths
        if path.is_file()
    ]
    manifest = {
        "schema_version": 1,
        "asset_id": "live2d.cubism-web-5-r.5-haru",
        "source_url": "https://www.live2d.com/en/sdk/download/web/",
        "license_name": "Live2D Proprietary/Open Software and Free Material License Agreements",
        "license_url": "https://www.live2d.com/eula/live2d-free-material-license-agreement_en.html",
        "accepted_by": accepted_by,
        "accepted_at": accepted_at,
        "files": files,
    }
    (root / "asset-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path, help="owner-downloaded CubismSdkForWeb-5-r.5.zip")
    parser.add_argument("--output", type=Path, default=Path("models/live2d-sdk-5-r.5"))
    parser.add_argument("--accepted-by", default="owner")
    parser.add_argument(
        "--accepted-at", default=datetime.now().astimezone().isoformat(timespec="seconds")
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    archive = args.zip.resolve()
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SDK_SHA256:
        raise SystemExit("SDK ZIP SHA-256 does not match Cubism Web 5-r.5")
    destination = args.output.resolve()
    if destination.exists() and not args.force:
        raise SystemExit(f"destination exists: {destination}; pass --force to rebuild")

    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        staging = Path(temp)
        with zipfile.ZipFile(archive) as bundle:
            if any(
                Path(name).is_absolute() or ".." in Path(name).parts for name in bundle.namelist()
            ):
                raise SystemExit("unsafe path in SDK ZIP")
            bundle.extractall(staging)
        root = staging / SDK_DIR
        patch_renderer(root)
        demo = root / DEMO
        subprocess.run(["npm", "ci"], cwd=demo, check=True)
        subprocess.run(["npm", "run", "build"], cwd=demo, check=True)
        make_manifest(root, args.accepted_by, args.accepted_at)
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        shutil.move(str(root), destination / SDK_DIR)
    print(destination / SDK_DIR / DEMO / "dist")


if __name__ == "__main__":
    main()
