# ruff: noqa: RUF001
"""Pick the sentences for a regeneration trial and write <out>/plan.json.

Corpus-scorer venv (needs opencc):
    ~/.venvs/corpus-scorer/bin/python scripts/tts_train/trial_select.py \
        --out ~/.local/share/siro/tts-corpus/siro-sweet-b-v2-trial --n 50

Takes every v1 sentence the owner marked "bad" (using its v2 rewrite when the
text was fixed), then sentences with characters Qwen misread (饗/癒/炫…), mixed
English, numbers, and random v2 sentences up to --n. Each item carries the
Traditional text (what SIRO shows) and an opencc t2s Simplified version (an
alternative input for Qwen only).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

RARE = "饗癒炫鬱龜嚐瀏覽籤韻璀璨"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", default="~/.local/share/siro/tts-corpus")
    ap.add_argument("--marks", default="~/tts-train/data/siro-sweet-b-v1/listen-marks-1.json")
    ap.add_argument("--rewrites", default="~/tts-train/data/sentences-v2/rewrites.csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--candidates", type=int, default=3)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    import opencc

    t2s = opencc.OpenCC("t2s").convert
    corpus = Path(args.corpus_dir).expanduser()
    meta = dict(
        line.split("|", 1)
        for line in (corpus / "siro-sweet-b-v1" / "metadata.csv").read_text(encoding="utf-8").splitlines()
        if line
    )
    rewrites = {
        r["old"]: r["new"]
        for r in csv.DictReader(open(Path(args.rewrites).expanduser(), encoding="utf-8"))
        if r["status"] == "rewritten"
    }
    v2 = [s for s in (corpus / "sentences-v2.txt").read_text(encoding="utf-8").splitlines() if s]
    marks = json.load(open(Path(args.marks).expanduser(), encoding="utf-8"))["marks"]

    picked: list[tuple[str, str]] = []  # (reason, text)
    seen: set[str] = set()

    def add(reason: str, text: str) -> None:
        if text not in seen and len(picked) < args.n:
            seen.add(text)
            picked.append((reason, text))

    for utt, mark in sorted(marks.items()):
        if mark == "bad":
            old = meta[utt].strip()
            add(f"v1 {utt} 擁有者判怪", rewrites.get(old, old))
    rng = random.Random(args.seed)
    pool = v2[:]
    rng.shuffle(pool)
    for s in pool:
        if any(c in RARE for c in s):
            add("少見字", s)
        if sum(r == "少見字" for r, _ in picked) >= 5:
            break
    for reason, pattern, quota in (("中英夾雜", r"[A-Za-z]{2,}", 6), ("數字", r"\d", 4)):
        got = 0
        for s in pool:
            if got >= quota:
                break
            if re.search(pattern, s) and s not in seen:
                add(reason, s)
                got += 1
    for s in pool:
        add("隨機", s)

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    items = [
        {"sentence": f"t{i:03d}", "reason": reason, "text_trad": text, "text_simp": t2s(text)}
        for i, (reason, text) in enumerate(picked, 1)
    ]
    plan = {
        "total_sentences": len(items),
        "candidates_per_sentence": args.candidates * 2,
        "variants": ["trad", "simp"],
        "candidates_per_variant": args.candidates,
        "items": items,
    }
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    counts: dict[str, int] = {}
    for it in items:
        key = it["reason"].split(" ")[-1] if it["reason"].startswith("v1") else it["reason"]
        counts[key] = counts.get(key, 0) + 1
    print(f"{len(items)} sentences -> {out / 'plan.json'}  {counts}")
    for it in items[:5]:
        print(" ", it["sentence"], it["reason"], it["text_trad"], "|", it["text_simp"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
