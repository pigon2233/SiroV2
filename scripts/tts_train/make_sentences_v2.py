# ruff: noqa: RUF001
"""Build sentences-v2.txt: v1's sentence list with the broken sentences rewritten.

    python3 scripts/tts_train/make_sentences_v2.py prep  --corpus-dir ~/.local/share/siro/tts-corpus \
        --issues ~/tts-train/data/siro-sweet-b-v1/text_issues.csv --work ~/tts-train/data/sentences-v2
    (Windows) scripts/tts_train/make_sentences_v2.ps1      # claude -p rewrites <work>/rewrite_input.txt
    python3 scripts/tts_train/make_sentences_v2.py apply --corpus-dir ... --work ...

v1 files (sentences.txt, sentences.styles.tsv, siro-sweet-b-v1/) are never modified.
apply writes <corpus-dir>/sentences-v2.txt, sentences-v2.styles.tsv and
<work>/rewrites.csv (v1 id, old, new). A rewrite is accepted only if it has
balanced quotes/brackets, sentence-final punctuation and 8–40 characters;
otherwise the sentence is dropped from v2 and listed as such.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

PAIRS = [("「", "」"), ("『", "』"), ("（", "）"), ("(", ")")]


def acceptable(text: str) -> bool:
    return (
        8 <= len(text) <= 40
        and text[-1] in "。！？…～」』）!?"
        and all(text.count(a) == text.count(b) for a, b in PAIRS)
        and re.fullmatch(r"[一-鿿A-Za-z0-9，。！？、；：～…「」『』（）\- %.:/+,'!?&]+", text)
        is not None
    )


def cmd_prep(args) -> int:
    work = Path(args.work).expanduser()
    work.mkdir(parents=True, exist_ok=True)
    rows = [
        r
        for r in csv.DictReader(open(Path(args.issues).expanduser(), encoding="utf-8"))
        if r["severity"] == "strong"
    ]
    with (work / "rewrite_input.txt").open("w", encoding="utf-8") as f:
        for r in rows:
            issue = r["llm_issue"] or r["rule_issues"]
            f.write(f"{r['id']}|{r['text']}|{issue}\n")
    print(f"{len(rows)} sentences to rewrite -> {work / 'rewrite_input.txt'}")
    return 0


def cmd_apply(args) -> int:
    corpus, work = Path(args.corpus_dir).expanduser(), Path(args.work).expanduser()
    meta = dict(
        line.split("|", 1)
        for line in (corpus / "siro-sweet-b-v1" / "metadata.csv")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    )
    asked = {
        line.split("|", 1)[0]
        for line in (work / "rewrite_input.txt").read_text(encoding="utf-8").splitlines()
    }
    new: dict[str, str] = {}
    for line in (
        (work / "rewrite_output.txt").read_text(encoding="utf-8", errors="replace").splitlines()
    ):
        if "|" in line:
            utt, text = (p.strip() for p in line.split("|", 1))
            if utt in asked:
                new[utt] = text
    replace, dropped = {}, []
    for utt in sorted(asked):
        old = meta[utt].strip()
        text = new.get(utt, "")
        if text and acceptable(text):
            replace[old] = text
        else:
            dropped.append((utt, old, text))
    sentences = (corpus / "sentences.txt").read_text(encoding="utf-8").splitlines()
    styles = dict(
        line.split("\t", 1)
        for line in (corpus / "sentences.styles.tsv").read_text(encoding="utf-8").splitlines()
        if "\t" in line
    )
    drop_old = {old for _, old, _ in dropped}
    out_s, out_t, seen = [], [], set()
    for s in sentences:
        if s in drop_old:
            continue
        t = replace.get(s, s)
        if t in seen:
            continue
        seen.add(t)
        out_s.append(t)
        out_t.append(f"{t}\t{styles.get(s, 'calm\tguessed')}")
    (corpus / "sentences-v2.txt").write_text("\n".join(out_s) + "\n", encoding="utf-8")
    (corpus / "sentences-v2.styles.tsv").write_text("\n".join(out_t) + "\n", encoding="utf-8")
    with (work / "rewrites.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["v1_id", "old", "new", "status"])
        for utt in sorted(asked):
            old = meta[utt].strip()
            if old in replace:
                w.writerow([utt, old, replace[old], "rewritten"])
        for utt, old, text in dropped:
            w.writerow([utt, old, text, "dropped"])
    print(
        f"v1 {len(sentences)} -> v2 {len(out_s)} sentences; rewritten {len(replace)}, dropped {len(dropped)}"
    )
    for utt, old in list((u, meta[u].strip()) for u in sorted(asked))[:8]:
        print(f"  {utt} {old}  ->  {replace.get(old, '(dropped)')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prep", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--corpus-dir", default="~/.local/share/siro/tts-corpus")
        p.add_argument("--work", default="~/tts-train/data/sentences-v2")
        if name == "prep":
            p.add_argument("--issues", default="~/tts-train/data/siro-sweet-b-v1/text_issues.csv")
    args = ap.parse_args()
    return cmd_prep(args) if args.cmd == "prep" else cmd_apply(args)


if __name__ == "__main__":
    sys.exit(main())
