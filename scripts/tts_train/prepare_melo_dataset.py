"""Turn the SIRO LJSpeech-style corpus into a MeloTTS training folder.

Run with the MeloTTS venv (needs scipy + soundfile; opencc only with --t2s):
    ~/.venvs/melotts/bin/python scripts/tts_train/prepare_melo_dataset.py \
        --corpus ~/.local/share/siro/tts-corpus/siro-sweet-b-v1 \
        --out ~/tts-train/data/siro-sweet-b-v1 [--t2s]

The source corpus is only read. Output:
    <out>/wavs/<id>.wav   44.1 kHz mono 16-bit (MeloTTS configs/config.json)
    <out>/metadata.list   <abs wav>|siro|ZH_MIX_EN|<text>

ZH_MIX_EN is what MeloTTS's own ZH model uses; plain ``ZH`` deletes English
words and asserts on 222 of our sentences. ``--t2s`` converts the text to
Simplified Chinese for the frontend only (jieba/pypinyin pick wrong readings
for Traditional polyphones such as 樂/覺/行). Audio is resampled only when
the target file is missing, so the script can be re-run.
"""

from __future__ import annotations

import argparse
import sys
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def resample(src: Path, dst: Path, target_sr: int) -> float:
    audio, sr = sf.read(src, dtype="float64", always_2d=True)
    audio = audio.mean(axis=1)
    if sr != target_sr:
        g = gcd(sr, target_sr)
        audio = resample_poly(audio, target_sr // g, sr // g)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    sf.write(dst, np.clip(audio, -1.0, 32767 / 32768), target_sr, subtype="PCM_16")
    return peak


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sr", type=int, default=44100)
    ap.add_argument("--speaker", default="siro")
    ap.add_argument("--language", default="ZH_MIX_EN")
    ap.add_argument("--t2s", action="store_true", help="convert text to Simplified (opencc)")
    args = ap.parse_args()

    convert = None
    if args.t2s:
        import opencc  # only needed for --t2s

        convert = opencc.OpenCC("t2s").convert

    corpus, out = args.corpus.expanduser(), args.out.expanduser()
    wav_out = out / "wavs"
    wav_out.mkdir(parents=True, exist_ok=True)

    rows = [
        line.split("|", 1)
        for line in (corpus / "metadata.csv").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    lines, missing, clipped = [], 0, 0
    for n, (utt, text) in enumerate(rows, 1):
        src, dst = corpus / "wavs" / f"{utt}.wav", wav_out / f"{utt}.wav"
        if not src.exists():
            missing += 1
            continue
        if not dst.exists() and resample(src, dst, args.sr) > 1.0:
            clipped += 1
        text = text.strip().replace("|", " ")
        if convert:
            text = convert(text)
        lines.append(f"{dst.resolve()}|{args.speaker}|{args.language}|{text}\n")
        if n % 500 == 0:
            print(f"{n}/{len(rows)}", flush=True)

    (out / "metadata.list").write_text("".join(lines), encoding="utf-8")
    print(
        f"rows={len(rows)} written={len(lines)} missing_wav={missing} clipped={clipped} t2s={bool(convert)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
