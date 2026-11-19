# ruff: noqa: RUF001
"""Synthesize fixed test sentences from training checkpoints so progress can be heard.

MeloTTS venv, runs on CPU (training owns the GPU):
    ~/.venvs/melotts/bin/python scripts/tts_train/synth_samples.py --run ~/tts-train/runs/mix-v2 --watch

Every G_<step>.pth with step % --every == 0 (and the newest one when --watch
ends) gets <run>/samples/G_<step>/{1,2,3}.wav spoken as speaker "siro". With
--watch it polls every 2 minutes (checkpoints are pruned to the last few, so
they must be caught while they exist) and exits once train_siro.sh logged
"=== exit 0" in console.log. Text is converted to Simplified for the frontend.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

SENTENCES = [
    "你回來啦！今天過得怎麼樣？",
    "我剛剛幫你把行程整理好了，明天早上九點要開會喔。",
    "這首歌的旋律好療癒，我們一起聽聽看吧～",
]


def synth(run: Path, ckpt: Path, speaker: str) -> None:
    import opencc
    from melo.api import TTS

    t2s = opencc.OpenCC("t2s").convert
    out = run / "samples" / ckpt.stem
    out.mkdir(parents=True, exist_ok=True)
    tts = TTS(language="ZH", device="cpu", config_path=str(run / "config.json"), ckpt_path=str(ckpt))
    sid = tts.hps.data.spk2id[speaker]
    for i, text in enumerate(SENTENCES, 1):
        tts.tts_to_file(t2s(text), sid, str(out / f"{i}.wav"), quiet=True)
    (out / "sentences.txt").write_text("\n".join(SENTENCES) + "\n", encoding="utf-8")
    print(f"samples for {ckpt.name} -> {out}", flush=True)


def pending(run: Path, every: int) -> list[Path]:
    todo = []
    for ckpt in run.glob("G_*.pth"):
        step = int(re.findall(r"\d+", ckpt.stem)[0])
        if step and step % every == 0 and not (run / "samples" / ckpt.stem / "3.wav").exists():
            todo.append(ckpt)
    return sorted(todo, key=lambda p: int(re.findall(r"\d+", p.stem)[0]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--every", type=int, default=5000)
    ap.add_argument("--speaker", default="siro")
    ap.add_argument("--watch", action="store_true")
    args = ap.parse_args()
    run = Path(args.run).expanduser()
    while True:
        for ckpt in pending(run, args.every):
            try:
                synth(run, ckpt, args.speaker)
            except Exception as exc:  # noqa: BLE001 - keep watching; training must not depend on this
                print(f"sample synthesis failed for {ckpt.name}: {exc!r}", flush=True)
        log = run / "console.log"
        finished = log.exists() and log.read_text(errors="replace").rstrip().splitlines()[-1:] and \
            log.read_text(errors="replace").rstrip().splitlines()[-1].startswith("=== exit 0")
        if not args.watch:
            return 0
        if finished:
            newest = max(run.glob("G_*.pth"), key=lambda p: int(re.findall(r"\d+", p.stem)[0]), default=None)
            if newest and not (run / "samples" / newest.stem / "3.wav").exists():
                synth(run, newest, args.speaker)
            return 0
        time.sleep(120)


if __name__ == "__main__":
    sys.exit(main())
