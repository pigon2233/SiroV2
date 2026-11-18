# ruff: noqa: RUF001
"""Score trial candidates with corpus_scorer and compare Traditional vs Simplified input.

Run through the scorer wrapper (it sets PATH / LD_LIBRARY_PATH), after
trial_generate.py has finished so Qwen and the scoring models do not share the GPU:
    SCORER_SCRIPT=trial_score.py bash scripts/tts_train/corpus_scorer.sh <trial dir>

Writes <trial>/trial_quality.csv (one row per candidate, plus best-of-variant
flags), appends "scored" lines with area scores to progress.jsonl for the
monitor, and prints the Traditional-vs-Simplified comparison.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import corpus_scorer as cs  # noqa: E402

TPE = timezone(timedelta(hours=8))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("trial")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    trial = Path(args.trial).expanduser()
    cands = [json.loads(line) for line in (trial / "candidates.jsonl").read_text(encoding="utf-8").splitlines()]
    raw_path = trial / "trial_raw.jsonl"
    done = {}
    if raw_path.exists():
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[r["id"]] = r
    todo = [c for c in cands if c["id"] not in done]
    if todo:
        scorer = cs.CorpusScorer()
        with raw_path.open("a", encoding="utf-8") as f:
            for n, c in enumerate(todo, 1):
                r = {**c, **scorer.model_features(c["wav"], c["text"])}
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                done[c["id"]] = r
                if n % 25 == 0:
                    print(f"models {n}/{len(todo)}", flush=True)
    rows = [done[c["id"]] for c in cands]
    jobs = [(r["id"], r["wav"], r.get("words", [])) for r in rows]
    with ProcessPoolExecutor(args.workers) as pool:
        for key, feats in pool.map(cs._acoustic_job, jobs, chunksize=4):
            done[key].update(feats)
    for r in rows:
        r["cps"] = r.get("ref_chars", 0) / r["dur"] if r.get("dur") else float("nan")
    cs.rank(rows)

    # best candidate per (sentence, variant): lowest ASR badness, then suspicion
    best: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["sentence"], r["variant"])
        score = (r["whisper_cer"] + r["sensevoice_cer"], r["suspicion"])
        if key not in best or score < best[key]["_score"]:
            best[key] = {**r, "_score": score}
    for r in rows:
        r["best_of_variant"] = best[(r["sentence"], r["variant"])]["id"] == r["id"]

    keys = ["sentence", "variant", "candidate", "best_of_variant", "reason", "text_fed", "gen_sec"]
    keys += [k for k in cs.CSV_KEYS if k not in keys and k != "owner_mark"]
    with (trial / "trial_quality.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["sentence"], r["variant"], r["candidate"])):
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})

    with (trial / "progress.jsonl").open("a", encoding="utf-8") as prog:
        for r in rows:
            prog.write(
                json.dumps(
                    {
                        "time": datetime.now(TPE).isoformat(),
                        "sentence": r["sentence"],
                        "candidate": f"{r['variant']}{r['candidate']}",
                        "stage": "scored",
                        "passed": r["passed"],
                        "suspicion": r["suspicion"],
                        "areas": {a: r[f"bad_{a}"] for a in cs.AREAS},
                    }
                )
                + "\n"
            )

    print("\n繁體 vs 簡體（每組 = 全部候選；best = 每句該組 3 個候選中最好的一個）")
    for variant in ("trad", "simp"):
        vs = [r for r in rows if r["variant"] == variant]
        bs = [b for (s, v), b in best.items() if v == variant]
        print(
            f"  {variant}: 候選 {len(vs)}  Whisper CER 平均 {statistics.mean(r['whisper_cer'] for r in vs):.3f}"
            f"  SenseVoice CER 平均 {statistics.mean(r['sensevoice_cer'] for r in vs):.3f}"
            f"  零錯字候選 {sum(r['whisper_cer'] == 0 and r['sensevoice_cer'] == 0 for r in vs) / len(vs):.0%}"
            f" | best-of-3: Whisper {statistics.mean(b['whisper_cer'] for b in bs):.3f}"
            f"  SenseVoice {statistics.mean(b['sensevoice_cer'] for b in bs):.3f}"
            f"  零錯字句 {sum(b['whisper_cer'] == 0 and b['sensevoice_cer'] == 0 for b in bs)}/{len(bs)}"
        )
    win = {"trad": 0, "simp": 0, "tie": 0}
    for s in {r["sentence"] for r in rows}:
        a, b = best[(s, "trad")]["_score"][0], best[(s, "simp")]["_score"][0]
        win["tie" if abs(a - b) < 1e-9 else ("trad" if a < b else "simp")] += 1
    print(f"  每句最佳候選誰比較好（字錯率）：繁體 {win['trad']}、簡體 {win['simp']}、平手 {win['tie']}")
    gen = [r["gen_sec"] for r in rows]
    print(f"  生成時間：平均 {statistics.mean(gen):.2f} 秒／候選，共 {sum(gen) / 60:.1f} 分鐘")
    return 0


if __name__ == "__main__":
    sys.exit(main())
