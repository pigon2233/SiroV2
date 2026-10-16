"""CPU-only comparison of frozen pre-change and current synthetic speech plans."""

from __future__ import annotations

import ast
import hashlib
import json
import runpy
from pathlib import Path

from siro.services.audio.tts import plan_speech

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main() -> None:
    previous = runpy.run_path(str(HERE / "before/tts.py"))["plan_speech"]
    fixture = ROOT / "docs/evidence/FIX-005-2026-10-07/verify_real_voice.py"
    story = next(
        ast.literal_eval(node.value)
        for node in ast.parse(fixture.read_text()).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "STORY" for target in node.targets)
    )
    cases = (
        ("existing-story", story),
        ("long-canonical", "合成長文完整朗讀驗收,保留每一個段落。" * 250 + "最後一句也必須保留。"),
        ("unpunctuated", "甲" * 7999),
    )
    rows = []
    for name, text in cases:
        old, current = previous(text), plan_speech(text)
        assert old["spoken_text"] == current["spoken_text"] == "".join(current["segments"])
        assert 0 < len(current["segments"][0]) <= 24
        assert all(0 < len(segment) <= 80 for segment in current["segments"])
        rows.append(
            {
                "case": name,
                "canonical_chars": len(current["spoken_text"]),
                "before_lengths": [len(segment) for segment in old["segments"]],
                "after_lengths": [len(segment) for segment in current["segments"]],
                "version_before": old["version"],
                "version_after": current["version"],
                "canonical_sha256": hashlib.sha256(current["spoken_text"].encode()).hexdigest(),
                "complete_text_preserved": True,
            }
        )
    report = {
        "kind": "CPU planner comparison, no inference",
        "real_qwen_inference": "NOT_RUN",
        "human_listening": "NOT_RUN",
        "rows": rows,
        "sources": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in ("src/siro/services/audio/tts.py", "scripts/qwen_tts_worker.py")
        },
    }
    (HERE / "plan-comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print("PASS: complete synthetic text retained; first segment bounded to 24 characters")


if __name__ == "__main__":
    main()
