# ruff: noqa: RUF001
"""Write the plan for the full v2 regeneration (corpus-scorer venv, needs opencc).

    ~/.venvs/corpus-scorer/bin/python scripts/tts_train/full_plan.py \
        --out ~/.local/share/siro/tts-corpus/siro-sweet-b-v2

Owner decisions (2026-11-18): Simplified text into Qwen, temperature 0.65 /
top_k 30, 3 candidates, automatic pick by error rate plus a spot-check page.
Sentences the owner already approved are reused, not regenerated:
  * trial picks (owner-choices-1.json, not "none") -> their v2 text is skipped
  * v1 clips marked OK (listen-marks-1.json) whose text is unchanged in v2
Sentences with characters Qwen was unstable on get 6 candidates. The plan
format is the one trial_generate.py reads (variants ["simp"]).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

UNSTABLE = "龜饗"  # owner rejected every candidate of 龜 sentences and the 饗 sentence in the trial


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", default="~/.local/share/siro/tts-corpus")
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidates", type=int, default=3)
    ap.add_argument("--unstable-candidates", type=int, default=6)
    args = ap.parse_args()

    import opencc

    t2s = opencc.OpenCC("t2s").convert
    corpus = Path(args.corpus_dir).expanduser()
    v2 = [s for s in (corpus / "sentences-v2.txt").read_text(encoding="utf-8").splitlines() if s]
    trial = corpus / "siro-sweet-b-v2-trial"
    tplan = {i["sentence"]: i for i in json.loads((trial / "plan.json").read_text(encoding="utf-8"))["items"]}
    choice = json.loads((trial / "owner-choices-1.json").read_text(encoding="utf-8"))["choice"]
    reuse_trial = {tplan[s]["text_trad"]: c for s, c in choice.items() if c != "none"}
    meta = dict(
        line.split("|", 1)
        for line in (corpus / "siro-sweet-b-v1" / "metadata.csv").read_text(encoding="utf-8").splitlines()
        if line
    )
    marks = json.loads(
        Path("~/tts-train/data/siro-sweet-b-v1/listen-marks-1.json").expanduser().read_text(encoding="utf-8")
    )["marks"]
    reuse_v1 = {meta[u].strip(): u for u, m in marks.items() if m == "ok"}

    items, reused = [], []
    for n, text in enumerate(v2, 1):
        sid = f"s{n:04d}"
        if text in reuse_trial:
            reused.append({"sentence": sid, "text": text, "source": "trial", "clip": reuse_trial[text]})
            continue
        if text in reuse_v1:
            reused.append({"sentence": sid, "text": text, "source": "v1", "clip": reuse_v1[text]})
            continue
        item = {"sentence": sid, "reason": "v2", "text_trad": text, "text_simp": t2s(text)}
        if any(c in UNSTABLE for c in text):
            item["candidates"] = args.unstable_candidates
            item["reason"] = "v2 不穩字"
        items.append(item)
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    total_cands = sum(int(i.get("candidates", args.candidates)) for i in items)
    plan = {
        "total_sentences": len(items),
        "candidates_per_sentence": args.candidates,
        "variants": ["simp"],
        "candidates_per_variant": args.candidates,
        "total_candidates": total_cands,
        "items": items,
    }
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "reused.json").write_text(json.dumps(reused, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"v2 {len(v2)} sentences: generate {len(items)} ({total_cands} candidates, "
        f"{sum('candidates' in i for i in items)} unstable x{args.unstable_candidates}), "
        f"reuse {len(reused)} (trial {sum(r['source'] == 'trial' for r in reused)}, "
        f"v1 {sum(r['source'] == 'v1' for r in reused)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
