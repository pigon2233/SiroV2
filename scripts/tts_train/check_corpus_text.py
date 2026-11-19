# ruff: noqa: RUF001
"""Find corpus sentences whose *text* is broken (truncated, garbled, unbalanced).

Three steps (the middle one runs the Claude CLI on Windows, see check_corpus_text.ps1):
  1. rules + batches (MeloTTS venv for jieba):
       ~/.venvs/melotts/bin/python scripts/tts_train/check_corpus_text.py rules \
         --metadata ~/.local/share/siro/tts-corpus/siro-sweet-b-v1/metadata.csv \
         --work ~/tts-train/data/siro-sweet-b-v1/textcheck
  2. LLM fluency pass over <work>/batch_*.txt -> <work>/llm_*.txt  (check_corpus_text.ps1)
  3. merge -> text_issues.csv, and mark the rows in quality.csv:
       python3 scripts/tts_train/check_corpus_text.py merge --work ... --out .../text_issues.csv \
         --quality .../quality.csv
The rule checks are cheap and explainable; the LLM pass catches sentences that are
grammatical-looking but meaningless (e.g. "昨天的程式碼審查發。").
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

PAIRS = [("「", "」"), ("『", "』"), ("（", "）"), ("(", ")")]
END_PUNCT = "。！？!?…～~」』）)"
BAD_LAST_POS = {"p", "c", "uj", "ud", "ug", "uv", "uz"}  # 介詞、連詞、助詞（的地得）


def rules(text: str) -> list[str]:
    import jieba.posseg as psg

    issues = []
    for a, b in PAIRS:
        if text.count(a) != text.count(b):
            issues.append(f"括號引號不成對{a}{b}")
    body = text.rstrip(END_PUNCT + "，,、 ")
    if text and text[-1] not in END_PUNCT:
        issues.append("沒有句尾標點")
    if len(re.sub(r"[^一-鿿A-Za-z0-9]", "", text)) < 6:
        issues.append("過短")
    if re.search(r"(?<![A-Za-z])[A-Za-z](?![A-Za-z ])", text) and not re.search(
        r"[A-Z]{1,}\d|\d[A-Za-z]", text
    ):
        issues.append("單一英文字母")
    if re.search(r"(.{2,})\1", re.sub(r"[^一-鿿]", "", text)):
        issues.append("字詞重複")
    words = [w for w in psg.lcut(body) if w.word.strip()]
    if words:
        last = words[-1]
        if last.flag in BAD_LAST_POS:
            issues.append(f"結尾是{last.word}（{last.flag}）")
        elif (
            len(last.word) == 1
            and last.flag.startswith("v")
            and len(words) >= 2
            and words[-2].flag.startswith(("n", "v"))
            and len(words[-2].word) >= 2
        ):
            issues.append(f"結尾單字動詞「{last.word}」可能截斷")
    return issues


def cmd_rules(args) -> int:
    work = Path(args.work).expanduser()
    work.mkdir(parents=True, exist_ok=True)
    rows = [
        line.split("|", 1)
        for line in Path(args.metadata).expanduser().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    with (work / "rules.jsonl").open("w", encoding="utf-8") as f:
        for utt, text in rows:
            f.write(
                json.dumps(
                    {"id": utt, "text": text.strip(), "rules": rules(text.strip())},
                    ensure_ascii=False,
                )
                + "\n"
            )
    for old in work.glob("batch_*.txt"):
        old.unlink()
    for i in range(0, len(rows), args.batch):
        chunk = rows[i : i + args.batch]
        (work / f"batch_{i // args.batch:03d}.txt").write_text(
            "".join(f"{u}|{t.strip()}\n" for u, t in chunk), encoding="utf-8"
        )
    n = sum(
        1
        for line in (work / "rules.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line)["rules"]
    )
    print(
        f"{len(rows)} sentences, {n} flagged by rules, {(len(rows) + args.batch - 1) // args.batch} LLM batches in {work}"
    )
    return 0


def cmd_merge(args) -> int:
    work = Path(args.work).expanduser()
    found: dict[str, dict] = {}
    for line in (work / "rules.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        found[r["id"]] = {"id": r["id"], "text": r["text"], "rules": r["rules"], "llm": ""}
    llm_done = 0
    for out in sorted(work.glob("llm_*.txt")):
        for line in out.read_text(encoding="utf-8", errors="replace").splitlines():
            line = re.sub(r"^\s*(沒問題|有問題)\s*[:：]\s*", "", line.strip())
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2 and parts[0] in found:
                llm_done += 1
                if parts[1].upper() != "OK":
                    found[parts[0]]["llm"] = "｜".join(parts[1:])
    issues = [r for r in found.values() if r["rules"] or r["llm"]]
    # The LLM read every sentence; rule hits alone were mostly false positives on
    # 2026-11-18 (e.g. 「超好聽。」 flagged as a truncated verb). Only unbalanced
    # quotes/brackets are trusted without the LLM agreeing.
    strong = [
        r for r in issues if r["llm"] or any(x.startswith("括號引號不成對") for x in r["rules"])
    ]
    out = Path(args.out).expanduser()
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "text", "severity", "rule_issues", "llm_issue"])
        for r in sorted(issues, key=lambda r: r["id"]):
            sev = "strong" if r in strong else "weak"
            w.writerow([r["id"], r["text"], sev, "；".join(r["rules"]), r["llm"]])
    print(
        f"LLM judged {llm_done}/{len(found)}; issues: {len(issues)} (strong {len(strong)}, "
        f"LLM {sum(bool(r['llm']) for r in issues)}, rules {sum(bool(r['rules']) for r in issues)}) -> {out}"
    )
    if args.quality:
        q = Path(args.quality).expanduser()
        rows = list(csv.DictReader(q.open(encoding="utf-8")))
        keys = list(rows[0].keys())
        if "text_issue" not in keys:
            keys.insert(keys.index("suspicion") + 1, "text_issue")
        strong_ids = {r["id"]: (r["llm"] or "；".join(r["rules"])) for r in strong}
        for r in rows:
            r["text_issue"] = strong_ids.get(r["id"], "")
        with q.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(
            f"marked {len(strong_ids)} rows in {q} (run corpus_scorer.sh rerank to fold into the ranking)"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rules")
    r.add_argument("--metadata", required=True)
    r.add_argument("--work", required=True)
    r.add_argument("--batch", type=int, default=150)
    m = sub.add_parser("merge")
    m.add_argument("--work", required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--quality", default=None)
    args = ap.parse_args()
    return cmd_rules(args) if args.cmd == "rules" else cmd_merge(args)


if __name__ == "__main__":
    sys.exit(main())
