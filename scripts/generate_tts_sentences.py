# ruff: noqa: RUF001
"""Ask an OpenAI-compatible chat model for varied Traditional Chinese sentences to read aloud.

Output is the text list for ``generate_tts_corpus.py``: UTF-8, one sentence per line. Each
request asks for one batch about one topic in one speaking style, so the list covers
questions, exclamations, numbers, mixed English and different moods. Only these generic
prompts are sent; nothing from SIRO's conversations or memory is read.

Reads ``SIRO_OPENAI_BASE_URL``, ``SIRO_OPENAI_MODEL`` and ``SIRO_OPENAI_API_KEY`` from the
environment, or from ``--env-file`` (for example the repository's ``.env.local``). Reruns
append to the same file and never repeat a sentence that is already there.

    python scripts/generate_tts_sentences.py --env-file .env.local \\
        --out ~/.local/share/siro/tts-corpus/sentences.txt --target 3000
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

TOPICS = (
    "早晨問候與起床",
    "天氣與季節",
    "吃飯、料理與飲料",
    "工作與寫程式",
    "讀書與考試",
    "電腦、手機與網路",
    "遊戲與動畫",
    "音樂與電影",
    "散步、運動與健康",
    "睡覺與休息",
    "購物與金錢，包含價格數字",
    "時間、日期與行程，包含數字",
    "交通與旅行",
    "家裡的燈光、溫度與家電",
    "心情低落時的安慰",
    "開心與慶祝",
    "撒嬌與玩笑",
    "道歉與感謝",
    "提醒與待辦事項",
    "查資料後的說明與解釋",
    "不確定時的回答與反問",
    "科學與冷知識",
    "寵物與動物",
    "夜晚與道晚安",
)
STYLES = (
    "溫柔的陳述句",
    "好奇的問句",
    "活潑的感嘆句",
    "有點害羞或猶豫、帶停頓的句子",
    "冷靜清楚的說明句",
    "夾雜一兩個常見英文單字或縮寫的句子",
    "開心、雀躍的句子",
    "難過、失落的句子",
    "有點生氣或鬧彆扭的句子",
    "驚訝、嚇一跳的句子",
    "放鬆、慵懶的句子",
    "擔心、不安的句子",
    "很睏、想睡的句子",
    "調皮、開玩笑逗對方的句子",
)
# Short ids for the styles above, written next to each sentence so a later TTS can be
# trained with a tone label. "english" is a content style, not a tone. happy, sad, angry,
# surprised and relaxed are the emotion names SIRO's replies already carry (motion_cues).
STYLE_IDS = dict(
    zip(
        STYLES,
        (
            "gentle",
            "question",
            "lively",
            "shy",
            "calm",
            "english",
            "happy",
            "sad",
            "angry",
            "surprised",
            "relaxed",
            "worried",
            "sleepy",
            "teasing",
        ),
        strict=True,
    )
)
MIN_CHARS, MAX_CHARS = 5, 40
_ALLOWED = re.compile(r"^[一-鿿A-Za-z0-9，。！？、；：～…「」『』（）\- %.:/+,'!?&]+$")
_NUMBERING = re.compile(r"^\s*(?:[-*•]|\d+[.)、．])\s*")


def prompt(topic: str, style: str, count: int) -> str:
    return (
        f"請用台灣的繁體中文口語，寫 {count} 句可以直接唸出來的句子。\n"
        f"主題：{topic}。語氣：{style}。\n"
        f"說話的人是一位親切的年輕女性桌面夥伴，對象是熟悉的朋友。\n"
        f"每句 {MIN_CHARS + 3} 到 {MAX_CHARS - 5} 個字，句子之間不要重複句型，"
        "不要提到任何真實人名。\n"
        "每句都要是意思完整、通順的一句話，結尾加上標點（。！？…～）。\n"
        "一行一句，不要編號、不要引號、不要表情符號、不要任何說明。"
    )


_PAIRS = (("「", "」"), ("『", "』"), ("（", "）"), ('"', '"'), ("'", "'"))


def clean(reply: str) -> list[str]:
    """Keep complete, readable lines.

    2026-11-18 corpus review: appending "。" to lines without a final mark turned
    replies cut off by the token limit into sentences like 「做三明治時把。」, and
    stripping 「」 from both ends left unbalanced quotes inside the sentence. Now a
    line must already end with a sentence-final mark (else it is likely
    truncated and dropped), only one matching outer quote pair is removed, and
    lines with unbalanced quotes or brackets are dropped.
    """
    sentences = []
    for line in reply.splitlines():
        text = " ".join(_NUMBERING.sub("", line).split())
        for left, right in _PAIRS:
            if len(text) > 2 and text.startswith(left) and text.endswith(right):
                text = text[len(left): -len(right)].strip()
                break
        if not text or text[-1] not in "。！？!?～…":
            continue
        if any(text.count(a) != text.count(b) for a, b in _PAIRS[:3]):
            continue
        if MIN_CHARS <= len(text) <= MAX_CHARS and _ALLOWED.fullmatch(text):
            sentences.append(text)
    return sentences


def styles_path(out: Path) -> Path:
    """Sidecar of ``out``: one ``sentence<TAB>style id<TAB>source`` row per sentence."""
    return out.with_name(out.stem + ".styles.tsv")


def guess_style(text: str) -> str:
    """Tone from punctuation, for sentences whose requested style was not recorded."""
    if "…" in text or text.startswith(("嗯", "那個", "呃")):
        return "shy"
    if "？" in text or "?" in text:
        return "question"
    if "！" in text or "!" in text:
        return "lively"
    if any(character.isascii() and character.isalpha() for character in text):
        return "english"
    return "calm"


def backfill_styles(out: Path) -> int:
    """Add a guessed row for every sentence in ``out`` that has none; returns rows added."""
    sidecar = styles_path(out)
    labelled = set()
    if sidecar.is_file():
        labelled = {row.split("\t", 1)[0] for row in sidecar.read_text("utf-8").splitlines()}
    missing = [
        text for text in out.read_text(encoding="utf-8").splitlines() if text not in labelled
    ]
    if missing:
        with sidecar.open("a", encoding="utf-8") as target:
            target.writelines(f"{text}\t{guess_style(text)}\tguessed\n" for text in missing)
    return len(missing)


def load_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key.startswith("SIRO_OPENAI_"):
            os.environ.setdefault(key, value.strip().strip("\"'"))


def http_ask(base_url: str, model: str, key: str) -> Callable[[str], str]:
    url = base_url.rstrip("/") + "/v1/chat/completions"

    def ask(text: str) -> str:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": text}],
            "temperature": 0.8,  # 1.0 produced garbled sentences (115 of 2,649 in v1)
            "max_tokens": 8000,  # reasoning models think inside this; 4000 cut replies short
        }
        request = urllib.request.Request(
            url,
            json.dumps(body).encode(),
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                # Groq's edge answers urllib's default agent with 403 (error code 1010).
                "User-Agent": "tts-sentence-generator/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.load(response)
        return str(payload["choices"][0]["message"]["content"])

    return ask


def generate(
    ask: Callable[[str], str],
    out: Path,
    target: int,
    *,
    batch: int = 40,
    max_requests: int = 400,
    pause: float = 0.0,
    seed: int = 0,
    only_styles: frozenset[str] | None = None,
) -> int:
    """Append new sentences to ``out`` until it holds ``target``; returns how many were added."""
    out.parent.mkdir(parents=True, exist_ok=True)
    known = set(out.read_text(encoding="utf-8").splitlines()) if out.is_file() else set()
    styles = [s for s in STYLES if only_styles is None or STYLE_IDS[s] in only_styles]
    if not styles:
        raise ValueError("no known style id selected")
    combos = list(itertools.product(TOPICS, styles))
    random.Random(seed + len(known)).shuffle(combos)
    added = failures = 0
    for request_index, (topic, style) in enumerate(itertools.cycle(combos)):
        if len(known) >= target or request_index >= max_requests or failures >= 5:
            break
        try:
            reply = ask(prompt(topic, style, batch))
            failures = 0
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as error:
            failures += 1
            code = getattr(error, "code", "")
            print(f"request failed: {type(error).__name__} {code}", file=sys.stderr, flush=True)
            # 429 is the per-minute token limit; wait it out instead of giving up early.
            time.sleep((20.0 if code == 429 else max(pause, 1.0)) * failures)
            continue
        kept = clean(reply)
        fresh = [text for text in dict.fromkeys(kept) if text not in known]
        if fresh:
            with out.open("a", encoding="utf-8") as target_file:
                target_file.write("\n".join(fresh) + "\n")
            with styles_path(out).open("a", encoding="utf-8") as target_file:
                target_file.writelines(f"{text}\t{STYLE_IDS[style]}\trequested\n" for text in fresh)
            known.update(fresh)
            added += len(fresh)
        print(
            f"{len(known)}/{target} sentences; kept {len(kept)} of "
            f"{sum(1 for line in reply.splitlines() if line.strip())} lines ({topic} / {style})",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(pause)
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--target", type=int, default=3000, help="total sentences wanted")
    parser.add_argument("--batch", type=int, default=40, help="sentences asked per request")
    parser.add_argument("--max-requests", type=int, default=400)
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between requests")
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument(
        "--styles",
        default="",
        help="comma-separated style ids to ask for (default all): " + ",".join(STYLE_IDS.values()),
    )
    parser.add_argument(
        "--backfill-styles",
        action="store_true",
        help="only label sentences that have no style row yet (no network), then exit",
    )
    arguments = parser.parse_args()
    if arguments.backfill_styles:
        labelled = backfill_styles(arguments.out.expanduser())
        print(f"labelled={labelled} styles={styles_path(arguments.out.expanduser())}")
        return 0
    if arguments.env_file is not None:
        load_env_file(arguments.env_file.expanduser())
    key = os.environ.get("SIRO_OPENAI_API_KEY", "")
    model = os.environ.get("SIRO_OPENAI_MODEL", "")
    if not key or not model:
        raise SystemExit("SIRO_OPENAI_API_KEY and SIRO_OPENAI_MODEL are required")
    base_url = os.environ.get("SIRO_OPENAI_BASE_URL", "https://api.groq.com/openai")
    added = generate(
        http_ask(base_url, model, key),
        arguments.out.expanduser(),
        arguments.target,
        batch=arguments.batch,
        max_requests=arguments.max_requests,
        pause=arguments.pause,
        only_styles=frozenset(arguments.styles.split(",")) if arguments.styles else None,
    )
    print(f"added={added} out={arguments.out.expanduser()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
