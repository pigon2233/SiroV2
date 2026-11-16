# ruff: noqa: RUF001
"""P0-6 time-to-first-token benchmark for SIRO's local chat model.

Builds N realistic chat turns through the real product path (IntegratedCompanion, candidate
profile, production-like tool catalogue, seeded memories, a clock that advances between turns)
with a recording model, then replays the captured requests in order against Ollama and reports
first-delta p50/p95 and total seconds. Requests are replayed sequentially so Ollama's prompt
prefix cache behaves as it does in a live conversation.

    uv run python scripts/bench_ttft.py --prompt-only            # sizes and stable prefix only
    uv run python scripts/bench_ttft.py --turns 10               # replay against Ollama
    uv run python scripts/bench_ttft.py --src ../main/src ...    # measure another source tree

Synthetic data only. keep_alive is left to Ollama's default (VRAM policy is task P0-5); pass
--keep-alive to override it for an experiment.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import tempfile
import time
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

TURNS = (
    "早安，今天好冷喔",
    "你還記得我最喜歡哪個季節嗎？",
    "我昨天跟朋友去爬山，腳好痠",
    "晚餐要吃什麼比較好？",
    "麻糬今天一直在睡覺",
    "幫我想一句鼓勵自己的話",
    "你覺得我週末要去看展還是待在家？",
    "我等等要開會，有點緊張",
    "剛剛那個建議不錯，謝謝你",
    "今天就先聊到這裡，晚安",
    "其實我還不想睡，再陪我聊一下",
    "你今天心情怎麼樣？",
)
SEEDS = (
    "請記住我最喜歡秋天",
    "請記住我的貓叫做麻糬",
    "請記住我週三晚上要上日文課",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", help="import siro from this src directory instead")
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--minutes-between-turns", type=float, default=3.0)
    parser.add_argument("--url", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    parser.add_argument("--model", default=os.environ.get("SIRO_OLLAMA_MODEL", "qwen3:4b"))
    parser.add_argument("--num-predict", type=int, default=512)
    parser.add_argument("--keep-alive", help="override Ollama keep_alive (default: unset)")
    parser.add_argument("--prompt-only", action="store_true", help="do not call Ollama")
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--json", type=Path, help="also write raw results here")
    parser.add_argument("--dump", type=Path, help="write each turn's system prompt here")
    return parser.parse_args()


def _catalog() -> Any:
    """Mirror of the candidate catalogue built in gateway.main (definitions and metadata)."""
    from siro.services.computer_use import tool as computer_tool
    from siro.services.tools.claude import CLAUDE_DEFINITION, CLAUDE_TOOL
    from siro.services.tools.orchestrator import (
        BROWSER_SESSION_TOOLS,
        DEFAULT_MODEL_TOOLS,
        ToolCatalog,
        ToolDescriptor,
        ToolMetadata,
    )
    from siro.services.tools.workspace import WORKSPACE_TOOLS

    definitions = {d.name: d for d in DEFAULT_MODEL_TOOLS}
    definitions.update({d.name: d for d in WORKSPACE_TOOLS})
    definitions.update({d.name: d for d in BROWSER_SESSION_TOOLS})
    definitions[CLAUDE_TOOL] = CLAUDE_DEFINITION
    definitions.update(computer_tool.DEFINITIONS)
    names = (
        "browser.navigate+read",
        "process.start",
        "computer.execute",
        "browser.read",
        "browser.fill",
        "browser.click",
        "browser.close",
        CLAUDE_TOOL,
        *computer_tool.DEFINITIONS,
        *(d.name for d in WORKSPACE_TOOLS),
    )
    read_only = {
        CLAUDE_TOOL,
        "browser.navigate+read",
        "browser.read",
        "filesystem.read",
        "filesystem.list",
        *computer_tool.READ_ONLY,
    }

    async def never(arguments: dict[str, object]) -> object:
        raise RuntimeError("benchmark never executes tools")

    labels = {
        "computer.execute": "執行電腦任務",
        "process.start": "啟動應用程式",
        "browser.navigate+read": "開啟並閱讀網頁",
        "browser.read": "閱讀目前網頁",
        "browser.fill": "填寫網頁欄位",
        "browser.click": "操作網頁按鈕",
        "browser.close": "關閉目前網頁",
        "filesystem.read": "讀取工作目錄文字檔",
        "filesystem.list": "查看工作目錄檔案",
        CLAUDE_TOOL: "請 Claude 幫忙查",
        **computer_tool.LABELS,
    }

    def metadata(name: str) -> Any:
        return ToolMetadata(
            display_name=labels.get(name),
            required_permissions=("tool_approval", "workspace_path_grant")
            if name.startswith("filesystem.")
            else ("tool_approval",),
            risk_level="observe/read-only" if name in read_only else "computer",
            version="siro-tool-contract-v1",
            provenance="siro_builtin",
            timeout_seconds=120
            if name == "computer.execute"
            else (30 if name.startswith("browser.") else None),
            failure_behavior="Failures produce failed observations. Unknown effects are not "
            "automatically repeated. Availability is not proof of successful execution.",
        )

    return ToolCatalog(
        tuple(
            ToolDescriptor(
                name,
                definitions.get(name),
                never,
                lambda: True,
                "playwright" if name.startswith("browser.") else "python.argv",
                "read" if name in read_only else "computer",
                metadata=metadata(name),
            )
            for name in names
        )
    )


async def capture(turns: int, minutes_between: float) -> list[Any]:
    """Run the product path with a recording model; return one ModelRequest per user turn."""
    import siro.core.memory as memory_module
    from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
    from siro.persistence.sqlite import SQLiteStore
    from siro.ports.models import ModelChunk, Privacy
    from siro.services.presentation.gateway import GatewayHub
    from siro.services.presentation.integrated import IntegratedCompanion
    from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator

    real_datetime = memory_module.datetime

    class Clock(real_datetime):  # type: ignore[misc, valid-type]
        offset = timedelta()

        @classmethod
        def now(cls, tz: Any = None) -> Any:
            return real_datetime.now(tz) + cls.offset

    class Recorder:
        name = "bench-recorder"

        def __init__(self) -> None:
            self.requests: list[Any] = []

        async def stream(self, request: Any, cancellation: Any) -> Any:
            self.requests.append(request)
            yield ModelChunk("text", "好呀，我在這裡陪你。")
            yield ModelChunk("finished")

    os.environ["SIRO_AUTO_MEMORY"] = "0"
    memory_module.datetime = Clock  # type: ignore[misc]
    model = Recorder()
    with tempfile.TemporaryDirectory(prefix="siro-bench-") as directory:
        data_dir = Path(directory)
        store = SQLiteStore(data_dir / "siro.db")
        await store.initialize()
        orchestrator = ToolOrchestrator(SQLiteToolProposalRepository(store), {}, catalog=_catalog())
        hub = GatewayHub()
        companion = IntegratedCompanion(
            data_dir,
            model,
            hub,
            MinimalWebBodyAdapter(WebSocketBodyTransport()),
            privacy=Privacy.LOCAL_ONLY,
            tool_orchestrator=orchestrator,
            runtime_profile="candidate",
            situation_lines=lambda _privacy: ("seen: foreground app is a code editor",),
        )
        try:
            for seed in SEEDS:
                await companion.respond("bench", seed)
            model.requests.clear()
            for index in range(turns):
                Clock.offset = timedelta(minutes=minutes_between * (index + 1))
                before = len(model.requests)
                await companion.respond("bench", TURNS[index % len(TURNS)])
                if len(model.requests) != before + 1:
                    raise RuntimeError("expected exactly one model request per turn")
        finally:
            memory_module.datetime = real_datetime
            await hub.shutdown()
    return model.requests


def _payload(request: Any, args: argparse.Namespace) -> dict[str, object]:
    """Same shape as OllamaAdapter (router builds it with thinking=False)."""
    options: dict[str, object] = {"num_predict": args.num_predict}
    if os.environ.get("SIRO_OLLAMA_CONTEXT_LENGTH"):
        options["num_ctx"] = int(os.environ["SIRO_OLLAMA_CONTEXT_LENGTH"])
    payload: dict[str, object] = {
        "model": args.model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages]
        or [{"role": "user", "content": request.prompt}],
        "stream": True,
        "think": False,
        "options": options,
    }
    if args.keep_alive:
        payload["keep_alive"] = args.keep_alive
    if request.tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in request.tools
        ]
    return payload


def _common_prefix(a: str, b: str) -> int:
    size = min(len(a), len(b))
    index = 0
    while index < size and a[index] == b[index]:
        index += 1
    return index


def prompt_stats(requests: list[Any]) -> dict[str, object]:
    systems = [r.messages[0].content if r.messages else r.prompt for r in requests]
    tools = [
        len(
            json.dumps(
                [[t.name, t.description, t.input_schema] for t in r.tools], ensure_ascii=False
            )
        )
        for r in requests
    ]
    marker = "[SIRO_TOOL_CAPABILITIES_V1]"
    capability = [
        len(s.split(marker, 1)[1].split("[/SIRO_TOOL_CAPABILITIES_V1]", 1)[0]) if marker in s else 0
        for s in systems
    ]
    prefixes = [_common_prefix(a, b) for a, b in pairwise(systems)]
    return {
        "turns": len(requests),
        "system_chars_median": statistics.median(len(s) for s in systems),
        "system_bytes_median": statistics.median(len(s.encode()) for s in systems),
        "capability_block_chars_median": statistics.median(capability),
        "tool_schema_chars_median": statistics.median(tools),
        "tools_per_turn": sorted({len(r.tools) for r in requests}),
        "stable_prefix_chars_min": min(prefixes) if prefixes else None,
        "stable_prefix_chars_median": statistics.median(prefixes) if prefixes else None,
    }


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


async def replay(requests: list[Any], args: argparse.Namespace) -> list[dict[str, object]]:
    import httpx

    url = args.url.rstrip("/") + "/api/chat"
    results: list[dict[str, object]] = []
    async with httpx.AsyncClient(timeout=300) as client:
        if not args.no_warmup:
            warm = {"model": args.model, "messages": [{"role": "user", "content": "hi"}]}
            warm.update(stream=False, think=False, options={"num_predict": 1})
            if args.keep_alive:
                warm["keep_alive"] = args.keep_alive
            (await client.post(url, json=warm)).raise_for_status()
        for index, request in enumerate(requests):
            started = time.perf_counter()
            first: float | None = None
            done: dict[str, Any] = {}
            async with client.stream("POST", url, json=_payload(request, args)) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if "error" in event:
                        raise RuntimeError(f"ollama error: {event['error']}")
                    message = event.get("message") or {}
                    if first is None and (message.get("content") or message.get("tool_calls")):
                        first = time.perf_counter() - started
                    if event.get("done"):
                        done = event
                        break
            total = time.perf_counter() - started
            row = {
                "turn": index + 1,
                "first_delta_seconds": first,
                "total_seconds": total,
                "prompt_eval_count": done.get("prompt_eval_count"),
                "prompt_eval_seconds": (done.get("prompt_eval_duration") or 0) / 1e9,
                "eval_count": done.get("eval_count"),
            }
            results.append(row)
            print(
                f"turn {index + 1:2d}: first_delta={first if first is None else round(first, 2)}s "
                f"total={total:.2f}s prompt_eval_count={row['prompt_eval_count']} "
                f"prompt_eval={row['prompt_eval_seconds']:.2f}s",
                flush=True,
            )
    return results


def main() -> int:
    args = _arguments()
    if args.src:
        sys.path.insert(0, str(Path(args.src).resolve()))
    import siro

    print(f"siro source: {Path(siro.__file__).parent}")
    requests = asyncio.run(capture(args.turns, args.minutes_between_turns))
    stats = prompt_stats(requests)
    print("prompt:", json.dumps(stats, ensure_ascii=False))
    output: dict[str, object] = {"prompt": stats}
    if args.dump:
        args.dump.mkdir(parents=True, exist_ok=True)
        for index, request in enumerate(requests):
            system = request.messages[0].content if request.messages else request.prompt
            (args.dump / f"turn-{index + 1:02d}.txt").write_text(system, encoding="utf-8")
    if not args.prompt_only:
        try:
            results = asyncio.run(replay(requests, args))
        except Exception as error:  # report, never invent numbers
            print(f"ollama replay failed at {args.url}: {type(error).__name__}: {error}")
            return 2
        firsts = [float(r["first_delta_seconds"]) for r in results if r["first_delta_seconds"]]
        totals = [float(r["total_seconds"]) for r in results]
        summary = {
            "model": args.model,
            "first_delta_p50": round(_percentile(firsts, 0.5), 2) if firsts else None,
            "first_delta_p95": round(_percentile(firsts, 0.95), 2) if firsts else None,
            "total_p50": round(_percentile(totals, 0.5), 2),
            "total_p95": round(_percentile(totals, 0.95), 2),
            "total_sum": round(sum(totals), 2),
        }
        print("ttft:", json.dumps(summary))
        output.update(results=results, summary=summary)
    if args.json:
        args.json.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
