# ruff: noqa: RUF001
"""Run the reflection prompt and parser on a synthetic month of owner messages.

Planted habits (each in 3 messages): running in the morning, coffee avoidance / green tea,
calling mum on Saturdays. Decoys: a one-off, a hypothetical, a coworker's preference, a joke.
usage: python evaluate.py MODEL RUNS OUT.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from siro.adapters.models.ollama import OllamaAdapter
from siro.ports.models import CancellationToken, ModelRequest
from siro.services.agent.reflection import parse_patterns, reflection_prompt

MESSAGES = [
    "早安，剛跑完步回來",
    "今天工作好多",
    "我不喝咖啡，給我綠茶就好",
    "如果我中樂透就辭職去環遊世界",
    "週六晚上照例打給我媽聊天",
    "午餐吃了牛肉麵",
    "今天早上跑了五公里",
    "同事說他超愛香菜",
    "超商又只買了無糖綠茶",
    "哈哈我其實是外星人啦",
    "這週六也有打電話給媽媽",
    "晚上有點累",
    "早上六點起床去河堤跑步",
    "明天要去看牙醫",
    "咖啡我真的不行，喝了會心悸，還是綠茶",
    "週六跟我媽講了一小時電話",
    "今天天氣不錯",
    "下班去超市買菜",
]
HABITS = {"跑步": ["跑"], "綠茶／不喝咖啡": ["綠茶"], "週六打給媽媽": ["媽", "母"]}
DECOYS = ["樂透", "香菜", "外星", "牙醫", "環遊"]


async def main() -> None:
    model_name, runs, out = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
    model = OllamaAdapter(model=model_name, thinking=False)
    rows = []
    for run in range(runs):
        parts: list[str] = []
        request = ModelRequest(reflection_prompt(MESSAGES), str(uuid4()), max_output_tokens=200)
        async for chunk in model.stream(request, CancellationToken()):
            if chunk.kind == "text":
                parts.append(chunk.text)
        patterns = parse_patterns("".join(parts), len(MESSAGES))
        texts = [p.text for p in patterns]
        rows.append(
            {
                "run": run,
                "patterns": [{"text": p.text, "evidence": list(p.evidence)} for p in patterns],
                "habits_found": [
                    h for h, keys in HABITS.items() if any(any(k in t for k in keys) for t in texts)
                ],
                "decoys": [t for t in texts if any(d in t for d in DECOYS)],
                "committed": sum(len(p.evidence) >= 3 for p in patterns),
            }
        )
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    out.write_text(
        json.dumps(
            {"model": model_name, "at": datetime.now(UTC).isoformat(), "rows": rows},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


asyncio.run(main())
