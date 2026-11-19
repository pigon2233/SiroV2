# ruff: noqa: RUF001
"""Sentence list generation: cleaning, de-duplication, resume and failure stop."""

from __future__ import annotations

import importlib.util
import urllib.error
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "generate_tts_sentences.py"
spec = importlib.util.spec_from_file_location("generate_tts_sentences", SCRIPT)
assert spec is not None and spec.loader is not None
sentences = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sentences)


def test_clean_keeps_only_readable_lines() -> None:
    reply = "\n".join(
        [
            "1. 今天天氣真好，要不要出去走走？",
            "- 「這個 bug 我幫你看一下喔。」",
            "太短",
            "這一句有表情符號😀所以不要",
            "好的，以下是句子：" + "很長" * 30,
            "晚餐大概要 250 元左右。",
        ]
    )
    assert sentences.clean(reply) == [
        "今天天氣真好，要不要出去走走？",
        "這個 bug 我幫你看一下喔。",
        "晚餐大概要 250 元左右。",
    ]


def test_clean_drops_truncated_and_unbalanced_lines() -> None:
    reply = "\n".join(
        [
            "做三明治時把",  # cut off by the token limit: no final mark, must not become 「…把。」
            "走廊的燈一亮，就像有人在說「歡迎回家。",  # unbalanced quote
            "「她說「晚安」就睡了。」",  # one outer pair removed, inner pair kept
            "\"今天也要加油喔！\"",
        ]
    )
    assert sentences.clean(reply) == ["她說「晚安」就睡了。", "今天也要加油喔！"]


def test_generate_appends_unique_sentences_and_resumes(tmp_path: Path) -> None:
    out = tmp_path / "s.txt"
    out.write_text("已經存在的第一句話。\n", encoding="utf-8")
    calls = 0

    def ask(_prompt: str) -> str:
        nonlocal calls
        calls += 1
        return f"已經存在的第一句話。\n這是第 {calls} 次產生的句子。\n這是第 {calls} 次產生的句子。"

    assert sentences.generate(ask, out, 4) == 3
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(set(lines)) == 4 and lines[0] == "已經存在的第一句話。"
    assert sentences.generate(ask, out, 4) == 0 and calls == 3


def test_generate_stops_after_repeated_failures(tmp_path: Path) -> None:
    calls = 0

    def ask(_prompt: str) -> str:
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("offline")

    sentences.time.sleep = lambda _seconds: None  # type: ignore[attr-defined]
    assert sentences.generate(ask, tmp_path / "s.txt", 10) == 0
    assert calls == 5


def test_styles_are_recorded_for_new_sentences_and_backfilled_for_old(tmp_path: Path) -> None:
    out = tmp_path / "s.txt"
    out.write_text(
        "嗯…我想一下喔。\n你今天過得好嗎？\n太棒了！\n這個 API 很好用。\n今天天氣不錯。\n", "utf-8"
    )
    assert sentences.backfill_styles(out) == 5
    assert sentences.backfill_styles(out) == 0
    rows = [row.split("\t") for row in sentences.styles_path(out).read_text("utf-8").splitlines()]
    assert [row[1:] for row in rows] == [
        ["shy", "guessed"],
        ["question", "guessed"],
        ["lively", "guessed"],
        ["english", "guessed"],
        ["calm", "guessed"],
    ]

    assert sentences.generate(lambda _prompt: "這是模型新產生的一句話。", out, 6) == 1
    last = sentences.styles_path(out).read_text("utf-8").splitlines()[-1].split("\t")
    assert last[0] == "這是模型新產生的一句話。" and last[2] == "requested"
    assert last[1] in sentences.STYLE_IDS.values()
