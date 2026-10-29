# ruff: noqa: RUF001
"""Compare curation prompts v1 (P2a) and v2 on synthetic cases with the local model.

usage: python evaluate.py MODEL RUNS OUT.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from siro.adapters.models.ollama import OllamaAdapter
from siro.core.memory import Memory
from siro.core.memory_curation import CurationOp, Tier, decision_prompt, parse_decision
from siro.ports.models import CancellationToken, ModelRequest

HERE = Path(__file__).parent


def v1_prompt(candidate: Memory, neighbors: list[Memory]) -> str:
    """The P2a prompt, verbatim from commit 657a424."""
    listed = "\n".join(f"[{index}] {m.text}" for index, m in enumerate(neighbors))
    return (
        "你是 SIRO 的記憶整理。比較「新記憶」和「既有記憶」，只選一種操作：\n"
        "ADD＝沒有相同意思的既有記憶；UPDATE＝和某筆既有記憶講同一件事，應合併成一筆；"
        "DELETE＝新記憶推翻了某筆既有記憶（舊的不再成立）；NOOP＝既有記憶已涵蓋，不需要存。\n"
        "UPDATE 和 DELETE 必須填 target（既有記憶編號）。importance 是 1 到 10 的整數，"
        "1 是瑣碎，10 是非常重要。只輸出 JSON："
        '{"op": "ADD|UPDATE|DELETE|NOOP", "target": [編號], '
        '"importance": 整數, "reason": "一句話"}\n'
        f"既有記憶：\n{listed or '（沒有）'}\n新記憶：{candidate.text}"
    )


def mem(text: str) -> Memory:
    return Memory(uuid4(), "siro", text, (uuid4(),), datetime.now(UTC))


async def main() -> None:
    model_name, runs, out = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
    model = OllamaAdapter(model=model_name, thinking=False)
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]

    async def ask(prompt: str) -> str:
        parts: list[str] = []
        request = ModelRequest(prompt, str(uuid4()), max_output_tokens=200)
        async for chunk in model.stream(request, CancellationToken()):
            if chunk.kind == "text":
                parts.append(chunk.text)
        return "".join(parts)

    results: dict[str, list[dict[str, object]]] = {"v1": [], "v2": []}
    for case in cases:
        neighbors = [mem(text) for text in case["existing"]]
        candidate = mem(case["new"])
        for version, build in (("v1", v1_prompt), ("v2", decision_prompt)):
            for run in range(runs):
                decision = parse_decision(
                    await ask(build(candidate, neighbors)), neighbors, Tier.ARCHIVE
                )
                cited = [
                    neighbors.index(next(n for n in neighbors if n.memory_id == t))
                    for t in decision.target_ids
                ]
                op_ok = decision.op.value in case["expect"]
                target_ok = (
                    "target" not in case or decision.op is CurationOp.ADD or case["target"] in cited
                )
                results[version].append(
                    {
                        "case": case["id"],
                        "run": run,
                        "op": decision.op.value,
                        "targets": cited,
                        "importance": decision.importance,
                        "ok": op_ok and target_ok,
                        "lost_new": "ADD" in case["expect"]
                        and decision.op in {CurationOp.NOOP, CurationOp.DELETE},
                        "false_delete": decision.op is CurationOp.DELETE
                        and "DELETE" not in case["expect"],
                        "reason": decision.reason,
                    }
                )
            print(case["id"], version, [r["op"] for r in results[version][-runs:]], flush=True)

    summary = {}
    for version, rows in results.items():
        research = [
            r["importance"] for r in rows if r["case"].startswith("research") and r["importance"]
        ]
        summary[version] = {
            "trials": len(rows),
            "correct": sum(bool(r["ok"]) for r in rows),
            "lost_new": sum(bool(r["lost_new"]) for r in rows),
            "false_delete": sum(bool(r["false_delete"]) for r in rows),
            "unknown": sum(r["op"] == "UNKNOWN" for r in rows),
            "ops": dict(Counter(str(r["op"]) for r in rows)),
            "research_importance": dict(Counter(research)),
        }
    out.write_text(
        json.dumps(
            {
                "model": model_name,
                "runs": runs,
                "at": datetime.now(UTC).isoformat(),
                "summary": summary,
                "results": results,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))


asyncio.run(main())
