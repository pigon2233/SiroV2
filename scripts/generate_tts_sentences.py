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
)
MIN_CHARS, MAX_CHARS = 5, 40
_ALLOWED = re.compile(r"^[一-鿿A-Za-z0-9，。！？、；：～…「」『』（）\- %.:/+]+$")
_NUMBERING = re.compile(r"^\s*(?:[-*•]|\d+[.)、．])\s*")


def prompt(topic: str, style: str, count: int) -> str:
    return (
        f"請用台灣的繁體中文口語，寫 {count} 句可以直接唸出來的句子。\n"
        f"主題：{topic}。語氣：{style}。\n"
        f"說話的人是一位親切的年輕女性桌面夥伴，對象是熟悉的朋友。\n"
        f"每句 {MIN_CHARS + 3} 到 {MAX_CHARS - 5} 個字，句子之間不要重複句型，"
        "不要提到任何真實人名。\n"
        "一行一句，不要編號、不要引號、不要表情符號、不要任何說明。"
    )


def clean(reply: str) -> list[str]:
    sentences = []
    for line in reply.splitlines():
        text = _NUMBERING.sub("", line).strip().strip("\"'「」")
        text = " ".join(text.split())
        if MIN_CHARS <= len(text) <= MAX_CHARS and _ALLOWED.fullmatch(text):
            sentences.append(text)
    return sentences


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
            "temperature": 1.0,
            "max_tokens": 2000,
        }
        request = urllib.request.Request(
            url,
            json.dumps(body).encode(),
            {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
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
) -> int:
    """Append new sentences to ``out`` until it holds ``target``; returns how many were added."""
    out.parent.mkdir(parents=True, exist_ok=True)
    known = set(out.read_text(encoding="utf-8").splitlines()) if out.is_file() else set()
    combos = list(itertools.product(TOPICS, STYLES))
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
            print(f"request failed: {type(error).__name__}", file=sys.stderr)
            time.sleep(max(pause, 1.0) * failures)
            continue
        fresh = [text for text in dict.fromkeys(clean(reply)) if text not in known]
        if fresh:
            with out.open("a", encoding="utf-8") as target_file:
                target_file.write("\n".join(fresh) + "\n")
            known.update(fresh)
            added += len(fresh)
        print(f"{len(known)}/{target} sentences ({topic} / {style})", file=sys.stderr, flush=True)
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
    arguments = parser.parse_args()
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
    )
    print(f"added={added} out={arguments.out.expanduser()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
