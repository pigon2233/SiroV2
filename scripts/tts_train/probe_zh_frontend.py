# ruff: noqa: RUF001
"""Check how MeloTTS's Chinese text frontend handles the SIRO corpus.

Run with the MeloTTS venv (not the SIRO venv):
    ~/.venvs/melotts/bin/python scripts/tts_train/probe_zh_frontend.py \
        --metadata ~/.local/share/siro/tts-corpus/siro-sweet-b-v1/metadata.csv

For every sentence it runs ``clean_text`` (normalize + g2p, no BERT) for the
given language codes and reports exceptions, phones outside Melo's symbol set
and characters the normalizer silently dropped. It also prints a 20-sentence
sample (English, digits, punctuation, plain) so a human can eyeball the pinyin.
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

LATIN = re.compile(r"[A-Za-z]")
DIGIT = re.compile(r"\d")
PUNCT = re.compile(r"[…～~「」『』—！？；：%]")
CJK = re.compile(r"[一-龥]")


def load(metadata: Path) -> list[tuple[str, str]]:
    rows = []
    for line in metadata.read_text(encoding="utf-8").splitlines():
        if line.strip():
            utt, text = line.split("|", 1)
            rows.append((utt, text.strip()))
    return rows


def pick_sample(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    def take(pred, n, used):
        out = [r for r in rows if r[0] not in used and pred(r[1])][:n]
        used.update(r[0] for r in out)
        return out

    used: set[str] = set()
    sample = take(lambda t: LATIN.search(t), 6, used)
    sample += take(lambda t: DIGIT.search(t), 5, used)
    sample += take(lambda t: PUNCT.search(t), 5, used)
    sample += take(lambda t: not (LATIN.search(t) or DIGIT.search(t)), 4, used)
    return sample


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", type=Path, required=True)
    ap.add_argument("--languages", default="ZH,ZH_MIX_EN")
    args = ap.parse_args()

    from melo.text.cleaner import clean_text
    from melo.text.chinese_mix import rep_map
    from melo.text.symbols import symbols

    known = set(symbols)
    rows = load(args.metadata)
    sample_ids = {u for u, _ in pick_sample(rows)}

    for lang in args.languages.split(","):
        errors, unknown, dropped = [], collections.Counter(), collections.Counter()
        lost_latin = 0
        print(f"\n===== {lang}: {len(rows)} sentences =====")
        for utt, text in rows:
            try:
                norm, phones, tones, word2ph = clean_text(text, lang)
            except Exception as exc:  # noqa: BLE001 - we want every failure
                errors.append((utt, text, repr(exc)[:120]))
                continue
            unknown.update(p for p in phones if p not in known)
            # characters that vanished (not mapped punctuation, not digits -> 中文數字)
            dropped.update(c for c in text if c not in norm and not c.isspace()
                           and not c.isdigit() and c not in rep_map and c not in "嗯呣")
            if LATIN.search(text) and not LATIN.search(norm):
                lost_latin += 1
            if utt in sample_ids:
                print(f"{utt} | {text}\n   norm: {norm}\n   phones: {' '.join(phones)}")
        print(f"-- errors: {len(errors)}")
        for e in errors[:10]:
            print("   ", e)
        print(f"-- unknown phones: {dict(unknown)}")
        print(f"-- sentences whose English was removed: {lost_latin}")
        print(f"-- characters dropped by normalizer (top 30): {dropped.most_common(30)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
