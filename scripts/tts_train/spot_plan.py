# ruff: noqa: RUF001
"""Pick the owner's spot-check set after a full regeneration (stdlib only).

    python3 scripts/tts_train/spot_plan.py --out ~/.local/share/siro/tts-corpus/siro-sweet-b-v2

Writes:
  <out>/auto_choice.json  {"choice": {sentence: best candidate id}}  (lowest Whisper+SenseVoice CER)
  <out>/spot_plan.json    plan for build_trial_page.py: every sentence whose best
                          candidate still has recognition errors (capped, worst first)
                          plus a random sample of the rest
Owner decision 2026-11-18: automatic pick, owner only spot-checks.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--threshold", type=float, default=0.08, help="best W+S CER above this is suspicious")
    ap.add_argument("--max-suspicious", type=int, default=200)
    ap.add_argument("--random", type=int, default=50)
    ap.add_argument("--seed", type=int, default=5)
    args = ap.parse_args()
    out = Path(args.out).expanduser()
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(open(out / "trial_quality.csv", encoding="utf-8")))
    best = {r["sentence"]: r for r in rows if r["best_of_variant"] == "True"}
    err = {s: float(r["whisper_cer"]) + float(r["sensevoice_cer"]) for s, r in best.items()}
    (out / "auto_choice.json").write_text(
        json.dumps({"version": 1, "choice": {s: r["id"] for s, r in best.items()}}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    suspicious = sorted((s for s in best if err[s] > args.threshold), key=lambda s: -err[s])
    shown_susp = suspicious[: args.max_suspicious]
    rest = [s for s in best if s not in set(suspicious)]
    sample = random.Random(args.seed).sample(rest, min(args.random, len(rest)))
    items = {i["sentence"]: i for i in plan["items"]}
    chosen = []
    for s in shown_susp:
        chosen.append({**items[s], "reason": f"可疑：最佳候選仍有錯字（W+S {err[s]:.0%}）"})
    for s in sample:
        chosen.append({**items[s], "reason": "隨機抽樣（自動判定沒問題）"})
    spot = {
        **{k: v for k, v in plan.items() if k != "items"},
        "help": (
            f"全量重新生成完成：{len(best)} 句已自動選好每句字錯率最低的版本（★）。這頁只列出要你抽聽的 {len(chosen)} 句："
            f"上面 {len(shown_susp)} 句是最佳版本仍可能有錯字的（共 {len(suspicious)} 句，按錯字多到少），"
            f"下面 {len(sample)} 句是隨機抽樣。<br>★ 那個 OK 就不用動；想換別的版本按「選這個」；都不行按「全部怪」。"
            "沒按的句子就照自動選的用。做完按「下載選擇」。"
        ),
        "items": chosen,
    }
    (out / "spot_plan.json").write_text(json.dumps(spot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"best picked for {len(best)} sentences; suspicious {len(suspicious)} "
        f"({len(suspicious) / max(1, len(best)):.0%}), page shows {len(shown_susp)} + random {len(sample)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
