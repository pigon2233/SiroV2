"""Compare the owner's listening marks with corpus_scorer's automatic scores.

    python3 scripts/tts_train/analyze_listen_marks.py \
        --quality ~/tts-train/data/siro-sweet-b-v1/quality.csv \
        --marks ~/tts-train/data/siro-sweet-b-v1/listen-marks-1.json

Prints bad-rate per listening-page group (worst 10 / around the cut / best 10 /
references), the AUC of every score for predicting "bad", the confusion matrix
of the automatic pass/fail, and every marked clip by rank. stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REFS = {"001329", "000620", "000001", "000004"}
FEATS = ["suspicion", "bad_tone", "bad_quality", "bad_spectrum", "bad_asr", "bad_emotion", "whisper_cer",
         "sensevoice_cer", "avg_logprob", "dnsmos_ovrl", "dnsmos_sig", "tone_mismatch", "jump_rate", "f0_range",
         "cps", "silence_ratio", "centroid", "rolloff95", "emotion_score"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quality", required=True)
    ap.add_argument("--marks", required=True)
    args = ap.parse_args()
    rows = {r["id"]: r for r in csv.DictReader(open(Path(args.quality).expanduser(), encoding="utf-8"))}
    marks = json.load(open(Path(args.marks).expanduser(), encoding="utf-8"))["marks"]
    n = len(rows)
    failed = sum(r["passed"] == "False" for r in rows.values())

    def group(r):
        k = int(r["rank"])
        if k <= 10:
            return "最可疑 10"
        if k > n - 10:
            return "最乾淨 10"
        if failed - 10 < k <= failed + 10:
            return "分界 20"
        return "參考句" if r["id"] in REFS else "其他"

    groups: dict[str, list[str]] = {}
    for i, m in marks.items():
        groups.setdefault(group(rows[i]), []).append(m)
    for k, v in groups.items():
        print(f"{k}: {len(v)} 句，怪 {v.count('bad')}（{v.count('bad') / len(v):.0%}）")

    def auc(f):
        pos = [float(rows[i][f]) for i, m in marks.items() if m == "bad" and rows[i].get(f) not in ("", "nan", None)]
        neg = [float(rows[i][f]) for i, m in marks.items() if m == "ok" and rows[i].get(f) not in ("", "nan", None)]
        if not pos or not neg:
            return float("nan")
        return sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))

    print("\nAUC（>0.5 越大＝分數越高越容易被判怪；<0.5＝方向相反）")
    for f in sorted(FEATS, key=lambda f: -abs(auc(f) - 0.5)):
        print(f"  {f:15s} {auc(f):.2f}")
    tp = sum(marks[i] == "bad" and rows[i]["passed"] == "False" for i in marks)
    fp = sum(marks[i] == "ok" and rows[i]["passed"] == "False" for i in marks)
    fn = sum(marks[i] == "bad" and rows[i]["passed"] == "True" for i in marks)
    tn = sum(marks[i] == "ok" and rows[i]["passed"] == "True" for i in marks)
    print(f"\n自動 fail vs 擁有者怪：TP {tp}  FP {fp}  FN {fn}  TN {tn}")
    print()
    for i, m in sorted(marks.items(), key=lambda x: int(rows[x[0]]["rank"])):
        r = rows[i]
        print(f"{r['rank']:>5} {i} {m:3s} {float(r['suspicion']):.2f} {r.get('text_issue', '')[:20]} {r['text'][:28]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
