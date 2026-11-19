"""Convert CSMSC (Databaker BZNSYP) into a MeloTTS training folder.

Run with the MeloTTS venv from ~/tts-train/MeloTTS (needs melo importable):
    ~/.venvs/melotts/bin/python scripts/tts_train/prepare_csmsc.py \
        --src ~/tts-train/data/csmsc/raw/BZNSYP --out ~/tts-train/data/csmsc/melo

Reads ProsodyLabeling/000001-010000.txt (odd lines: "<id>\t<text with #1..#4>"),
strips the prosody marks, resamples Wave/<id>.wav to 44.1 kHz mono 16-bit and
writes <out>/metadata.list as "<abs wav>|csmsc|ZH_MIX_EN|<text>". The text is
already Simplified Chinese. Every sentence is run through Melo's ZH_MIX_EN
frontend (no BERT); failures are listed and left out. Re-runnable.
"""

from __future__ import annotations

import argparse
import re
import sys
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sr", type=int, default=44100)
    args = ap.parse_args()

    from melo.text.cleaner import clean_text

    src, out = Path(args.src).expanduser(), Path(args.out).expanduser()
    (out / "wavs").mkdir(parents=True, exist_ok=True)
    labels = next(src.rglob("000001-010000.txt"))
    lines = labels.read_text(encoding="utf-8-sig").splitlines()
    items = []
    for line in lines[0::2]:
        if "\t" not in line:
            continue
        utt, text = line.split("\t", 1)
        text = re.sub(r"#\d", "", text).strip()
        items.append((utt.strip(), text))

    rows, errors, seconds = [], [], 0.0
    for n, (utt, text) in enumerate(items, 1):
        wav_in = src / "Wave" / f"{utt}.wav"
        wav_out = out / "wavs" / f"{utt}.wav"
        try:
            clean_text(text, "ZH_MIX_EN")
        except Exception as exc:
            errors.append((utt, text, repr(exc)[:80]))
            continue
        if not wav_out.exists():
            audio, sr = sf.read(wav_in, dtype="float64", always_2d=True)
            audio = audio.mean(axis=1)
            g = gcd(sr, args.sr)
            audio = resample_poly(audio, args.sr // g, sr // g)
            sf.write(wav_out, np.clip(audio, -1.0, 32767 / 32768), args.sr, subtype="PCM_16")
        seconds += sf.info(wav_out).duration
        rows.append(f"{wav_out.resolve()}|csmsc|ZH_MIX_EN|{text}\n")
        if n % 1000 == 0:
            print(f"{n}/{len(items)}", flush=True)
    (out / "metadata.list").write_text("".join(rows), encoding="utf-8")
    print(
        f"sentences={len(items)} written={len(rows)} frontend_errors={len(errors)} hours={seconds / 3600:.2f}"
    )
    for e in errors[:20]:
        print("  error", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
