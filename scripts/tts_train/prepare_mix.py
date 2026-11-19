"""Build the multi-speaker MeloTTS training folder: CSMSC + SIRO v2 selection.

MeloTTS venv (scipy, soundfile, opencc), run from anywhere:
    ~/.venvs/melotts/bin/python scripts/tts_train/prepare_mix.py --out ~/tts-train/data/mix-v2

* SIRO: every row of siro-sweet-b-v2/selected.csv, resampled to 44.1 kHz mono
  16-bit into <out>/wavs/siro/, text converted to Simplified (opencc t2s) for the
  Chinese frontend, speaker "siro".
* CSMSC: rows of ~/tts-train/data/csmsc/melo/metadata.list as they are (already
  44.1 kHz, Simplified), speaker "csmsc".
Writes <out>/metadata.list. Next: preprocess_text.py (BERT features, split), then
oversample_siro in this script's ``--oversample`` step.
"""

from __future__ import annotations

import argparse
import csv
import sys
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def resample(src: str, dst: Path, sr_out: int) -> None:
    audio, sr = sf.read(src, dtype="float64", always_2d=True)
    audio = audio.mean(axis=1)
    if sr != sr_out:
        g = gcd(sr, sr_out)
        audio = resample_poly(audio, sr_out // g, sr // g)
    sf.write(dst, np.clip(audio, -1.0, 32767 / 32768), sr_out, subtype="PCM_16")


def cmd_build(args) -> int:
    import opencc

    t2s = opencc.OpenCC("t2s").convert
    out = Path(args.out).expanduser()
    (out / "wavs" / "siro").mkdir(parents=True, exist_ok=True)
    lines, siro_sec = [], 0.0
    for r in csv.DictReader(open(Path(args.selected).expanduser(), encoding="utf-8")):
        dst = out / "wavs" / "siro" / f"{r['id']}.wav"
        if not dst.exists():
            resample(r["wav"], dst, args.sr)
        siro_sec += sf.info(dst).duration
        text = t2s(r["text"].strip()).replace("|", " ")
        lines.append(f"{dst.resolve()}|siro|ZH_MIX_EN|{text}\n")
    n_siro = len(lines)
    csmsc = Path(args.csmsc).expanduser().read_text(encoding="utf-8").splitlines(keepends=True)
    lines += csmsc
    (out / "metadata.list").write_text("".join(lines), encoding="utf-8")
    print(f"siro {n_siro} ({siro_sec / 3600:.2f} h) + csmsc {len(csmsc)} -> {out / 'metadata.list'}")
    return 0


def cmd_oversample(args) -> int:
    """Repeat siro lines in train.list so the target voice is not drowned by CSMSC."""
    out = Path(args.out).expanduser()
    train = (out / "train.list").read_text(encoding="utf-8").splitlines(keepends=True)
    siro = [line for line in train if line.split("|")[1] == "siro"]
    other = [line for line in train if line.split("|")[1] != "siro"]
    (out / "train.list").write_text("".join(other + siro * args.factor), encoding="utf-8")
    print(f"train.list: csmsc {len(other)}, siro {len(siro)} x{args.factor} = {len(siro) * args.factor}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", required=True)
    b.add_argument("--selected", default="~/.local/share/siro/tts-corpus/siro-sweet-b-v2/selected.csv")
    b.add_argument("--csmsc", default="~/tts-train/data/csmsc/melo/metadata.list")
    b.add_argument("--sr", type=int, default=44100)
    o = sub.add_parser("oversample")
    o.add_argument("--out", required=True)
    o.add_argument("--factor", type=int, default=2)
    args = ap.parse_args()
    return cmd_build(args) if args.cmd == "build" else cmd_oversample(args)


if __name__ == "__main__":
    sys.exit(main())
