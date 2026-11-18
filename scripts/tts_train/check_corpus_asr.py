# ruff: noqa: RUF001
"""Check whether corpus recordings are intelligible: Whisper transcript vs text.

Two steps, two venvs (nothing is installed or modified):
  1. transcribe (needs faster_whisper; run on CPU so training keeps the GPU)
       ~/.venvs/sirov2/bin/python scripts/tts_train/check_corpus_asr.py transcribe \
         --model ~/.local/share/siro/data/models/faster-whisper-small \
         --wavs ~/.local/share/siro/tts-corpus/siro-sweet-b-v1/wavs \
         --ids 000001,000004 --random 60 --out /tmp/asr.jsonl
  2. score (needs opencc for Traditional/Simplified folding)
       ~/.venvs/melotts/bin/python scripts/tts_train/check_corpus_asr.py score \
         --metadata ~/.local/share/siro/tts-corpus/siro-sweet-b-v1/metadata.csv --asr /tmp/asr.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import wave
from pathlib import Path


def transcribe(args) -> int:
    from faster_whisper import WhisperModel

    wavs = Path(args.wavs).expanduser()
    ids = [i for i in args.ids.split(",") if i]
    pool = sorted(p.stem for p in wavs.glob("*.wav") if p.stem not in ids)
    ids += random.Random(args.seed).sample(pool, min(args.random, len(pool)))
    model = WhisperModel(str(Path(args.model).expanduser()), device="cpu", compute_type="int8",
                         cpu_threads=args.threads)
    with open(args.out, "w", encoding="utf-8") as out:
        for n, utt in enumerate(ids, 1):
            path = wavs / f"{utt}.wav"
            with wave.open(str(path)) as w:
                dur = w.getnframes() / w.getframerate()
            segs, _ = model.transcribe(str(path), language="zh", beam_size=5, vad_filter=False)
            text = "".join(s.text for s in segs).strip()
            out.write(json.dumps({"id": utt, "wav": str(path), "dur": round(dur, 2), "asr": text},
                                 ensure_ascii=False) + "\n")
            out.flush()
            print(f"{n}/{len(ids)} {utt} {text}", flush=True)
    return 0


def norm(text: str, conv) -> str:
    text = conv(text).lower()
    return "".join(re.findall(r"[一-鿿a-z0-9]", text))


def cer(ref: str, hyp: str) -> float:
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


def score(args) -> int:
    import opencc

    conv = opencc.OpenCC("t2s").convert
    texts = dict(line.split("|", 1) for line in
                 Path(args.metadata).expanduser().read_text(encoding="utf-8").splitlines() if line.strip())
    rows = [json.loads(line) for line in open(args.asr, encoding="utf-8")]
    scores = []
    for r in rows:
        ref = texts[r["id"]].strip()
        c = cer(norm(ref, conv), norm(r["asr"], conv))
        cps = len(norm(ref, conv)) / r["dur"] if r["dur"] else 0
        scores.append(c)
        print(f"{r['id']}  CER {c:5.0%}  {cps:4.1f} 字/秒  {r['dur']:.1f}s\n   原文: {ref}\n   轉寫: {r['asr']}")
    if scores:
        bad = sum(s > 0.3 for s in scores)
        print(f"\nN={len(scores)}  CER 中位數 {statistics.median(scores):.0%}  平均 {statistics.mean(scores):.0%}  "
              f">30%: {bad} ({bad / len(scores):.0%})  >60%: {sum(s > 0.6 for s in scores)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("transcribe")
    t.add_argument("--model", required=True)
    t.add_argument("--wavs", required=True)
    t.add_argument("--ids", default="")
    t.add_argument("--random", type=int, default=0)
    t.add_argument("--seed", type=int, default=7)
    t.add_argument("--threads", type=int, default=6)
    t.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("--metadata", required=True)
    s.add_argument("--asr", required=True)
    args = ap.parse_args()
    return transcribe(args) if args.cmd == "transcribe" else score(args)


if __name__ == "__main__":
    sys.exit(main())
