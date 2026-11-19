# ruff: noqa: RUF001
"""Write the v2 training selection and a 20-sentence OK/怪 spot-check CSV (stdlib only).

    python3 scripts/tts_train/select_final.py --out ~/.local/share/siro/tts-corpus/siro-sweet-b-v2

Owner decision 2026-11-19: 250 spot-check sentences are too many, so every
sentence whose best candidate still has recognition errors (W+S CER > 0.08)
is simply excluded; owner-approved reused clips (trial picks, v1 OK) are kept.
Writes <out>/selected.csv (id, source, clip, wav, text, text_fed, whisper_cer,
sensevoice_cer, dur) and <out>/spot20.csv (rows in trial_quality.csv format for
build_listen_page.py --all).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import wave
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--threshold", type=float, default=0.08)
    ap.add_argument("--spot", type=int, default=20)
    ap.add_argument("--seed", type=int, default=19)
    args = ap.parse_args()
    out = Path(args.out).expanduser()
    corpus = out.parent
    rows = list(csv.DictReader(open(out / "trial_quality.csv", encoding="utf-8")))
    best = [r for r in rows if r["best_of_variant"] == "True"]
    keep = [r for r in best if float(r["whisper_cer"]) + float(r["sensevoice_cer"]) <= args.threshold]
    sel = [
        {
            "id": r["sentence"],
            "source": "v2",
            "clip": r["id"],
            "wav": r["wav"],
            "text": r["text"],
            "text_fed": r["text_fed"],
            "whisper_cer": r["whisper_cer"],
            "sensevoice_cer": r["sensevoice_cer"],
            "dur": r["dur"],
        }
        for r in keep
    ]
    trial = corpus / "siro-sweet-b-v2-trial"
    tcands = {
        json.loads(line)["id"]: json.loads(line)
        for line in (trial / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
    }
    for r in json.loads((out / "reused.json").read_text(encoding="utf-8")):
        if r["source"] == "trial":
            c = tcands[r["clip"]]
            wav, fed = c["wav"], c["text_fed"]
        else:
            wav, fed = str(corpus / "siro-sweet-b-v1" / "wavs" / f"{r['clip']}.wav"), r["text"]
        with wave.open(wav) as w:
            dur = w.getnframes() / w.getframerate()
        sel.append(
            {"id": r["sentence"], "source": f"owner-{r['source']}", "clip": r["clip"], "wav": wav,
             "text": r["text"], "text_fed": fed, "whisper_cer": "", "sensevoice_cer": "", "dur": round(dur, 3)}
        )
    sel.sort(key=lambda r: r["id"])
    with (out / "selected.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sel[0].keys()))
        w.writeheader()
        w.writerows(sel)
    spot = random.Random(args.seed).sample(keep, min(args.spot, len(keep)))
    with (out / "spot20.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(spot)
    hours = sum(float(r["dur"]) for r in sel) / 3600
    print(
        f"selected {len(sel)} sentences ({hours:.2f} h): v2 auto {len(keep)} of {len(best)} "
        f"(excluded {len(best) - len(keep)}), owner-approved reused {len(sel) - len(keep)}; spot {len(spot)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
