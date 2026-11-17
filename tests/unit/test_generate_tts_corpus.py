"""Corpus generation: LJSpeech layout, skipped lines recorded, reruns resume."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "generate_tts_corpus.py"
spec = importlib.util.spec_from_file_location("generate_tts_corpus", SCRIPT)
assert spec is not None and spec.loader is not None
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)

FAKE_WORKER = """
import base64, io, json, sys, wave
print("progress text that is not json", flush=True)
print(json.dumps({"ready": True}), flush=True)
for line in sys.stdin:
    text = json.loads(line)["text"]
    if "bad" in text:
        print(json.dumps({"error": "QwenOutputIncomplete"}), flush=True)
        continue
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(b"\\0\\0" * 12000)
    print(json.dumps({"audio": base64.b64encode(out.getvalue()).decode()}), flush=True)
"""


def test_corpus_layout_skips_and_resume(tmp_path: Path) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text(FAKE_WORKER)
    texts = tmp_path / "texts.txt"
    texts.write_text("第一句\n\n  第一句  \nbad 句子\n第二句\n", encoding="utf-8")
    out = tmp_path / "out"
    command = [sys.executable, str(worker)]

    listed = corpus.read_texts(texts, None)
    assert listed == ["第一句", "bad 句子", "第二句"]
    written, skipped, seconds = corpus.generate(command, listed, out)
    assert (written, skipped, seconds) == (2, 1, 1.0)
    assert (out / "metadata.csv").read_text("utf-8") == "000001|第一句\n000002|第二句\n"
    assert (out / "skipped.txt").read_text("utf-8") == "bad 句子\n"
    assert sorted(path.name for path in (out / "wavs").iterdir()) == ["000001.wav", "000002.wav"]

    assert corpus.generate(command, listed, out) == (0, 0, 0.0)
    written, skipped, _ = corpus.generate(command, [*listed, "第三句"], out)
    assert (written, skipped) == (1, 0)
    assert (out / "metadata.csv").read_text("utf-8").endswith("000003|第三句\n")
