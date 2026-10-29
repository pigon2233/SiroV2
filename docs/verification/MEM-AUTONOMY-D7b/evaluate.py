"""Compare v1 (quote-only, one sentence) and v2 (context, reworded + quote) memory nomination.

Runs the real AutonomousMemory screening with a fake store; usage: python evaluate.py MODEL RUNS OUT
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from siro.adapters.models.ollama import OllamaAdapter
from siro.contracts.events import Priority, UserTextEvent, UserTextPayload
from siro.contracts.events import Privacy as EventPrivacy
from siro.core.memory_autonomy import (
    AutonomousMemory,
    contextual_nomination_prompt,
    memory_nomination_prompt,
    parse_contextual_nominations,
    parse_nominations,
)
from siro.ports.models import CancellationToken, ModelRequest

HERE = Path(__file__).parent


class Store:
    def __init__(self) -> None:
        self.saved: list[str] = []

    async def remember(self, memory: object, _source: object) -> None:
        self.saved.append(memory.text)  # type: ignore[attr-defined]


def event(text: str) -> UserTextEvent:
    now = datetime.now(UTC)
    return UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="siro.presentation",
        occurred_at=now,
        received_at=now,
        trace_id="eval",
        session_id="eval",
        turn_id="t",
        sequence=0,
        priority=Priority.INTERACTIVE,
        privacy=EventPrivacy.LOCAL_ONLY,
        payload=UserTextPayload(text=text, language="zh"),
    )


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

    rows: list[dict[str, object]] = []
    for case in cases:
        context = [tuple(pair) for pair in case["context"]]
        for version in ("v1", "v2"):
            for run in range(runs):
                store = Store()

                async def nominate(text: str, context=context, version=version):  # type: ignore[no-untyped-def]
                    if version == "v1":
                        return parse_nominations(await ask(memory_nomination_prompt(text)))
                    return parse_contextual_nominations(
                        await ask(contextual_nomination_prompt(text, context))
                    )

                saved, confirm = await AutonomousMemory(store, nominate).consider(  # type: ignore[arg-type]
                    "siro", event(case["text"])
                )
                texts = [m.text for m in saved] + [
                    c if isinstance(c, str) else c.text for c in confirm
                ]
                hit = [any(all(k in t for k in keys) for t in texts) for keys in case["expect"]]
                false = [
                    t
                    for t in texts
                    if not any(all(k in t for k in keys) for keys in case["expect"])
                ]
                rows.append(
                    {
                        "case": case["id"],
                        "version": version,
                        "run": run,
                        "saved": texts,
                        "expected": len(case["expect"]),
                        "caught": sum(hit),
                        "false": false,
                    }
                )
            print(case["id"], version, [r["saved"] for r in rows[-runs:]], flush=True)

    summary = {}
    for version in ("v1", "v2"):
        mine = [r for r in rows if r["version"] == version]
        summary[version] = {
            "trials": len(mine),
            "expected_facts": sum(int(r["expected"]) for r in mine),
            "caught": sum(int(r["caught"]) for r in mine),
            "false_memories": sum(len(r["false"]) for r in mine),  # type: ignore[arg-type]
            "false_in_should_be_empty": sum(
                len(r["false"])
                for r in mine
                if r["expected"] == 0  # type: ignore[arg-type]
            ),
        }
    out.write_text(
        json.dumps(
            {
                "model": model_name,
                "runs": runs,
                "at": datetime.now(UTC).isoformat(),
                "summary": summary,
                "rows": rows,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))


asyncio.run(main())
