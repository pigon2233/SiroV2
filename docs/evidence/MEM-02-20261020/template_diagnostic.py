"""Synthetic, isolated Qwen template diagnostic; never a production adapter or acceptance."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "context_evaluation", ROOT / "scripts/evaluate_context_understanding.py"
)
assert spec and spec.loader
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)
from siro.ports.models import ModelChunk  # noqa: E402


class Capture:
    name = "diagnostic-capture-only"

    async def stream(self, request, cancellation):
        self.request = request
        yield ModelChunk("text", "CAPTURE_ONLY")
        yield ModelChunk("finished")


async def main(output):
    # New path only. No existing evidence may be overwritten.
    with Path(output).open("x", encoding="utf-8") as handle:
        result = {"diagnostic_only": True, "synthetic_only": True, "cases": []}
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", timeout=55) as client:
            show = await client.post("/api/show", json={"model": "qwen3:4b-instruct"})
            show.raise_for_status()
            template = show.json()["template"]
            result["template_sha256"] = hashlib.sha256(template.encode()).hexdigest()
            result["template_tail"] = template[-320:]
            for case in evaluation.load_cases():
                if case["id"] not in {"C02", "C19", "C22", "C28"}:
                    continue
                capture = Capture()
                captured = await evaluation.execute_case(case, capture)
                if not captured["capture_passed"]:
                    raise RuntimeError("Core request capture hard gate failed")
                request = capture.request
                if request.tools or any(m.tool_calls or m.role == "tool" for m in request.messages):
                    raise ValueError("This limited diagnostic does not serialize tools")
                messages = [{"role": m.role, "content": m.content} for m in request.messages]
                prompt = "".join(
                    f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages
                ) + "<|im_start|>assistant\n"
                row = {"id": case["id"], "request_sha256": hashlib.sha256(
                    json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()
                ).hexdigest(), "arms": []}
                for arm in ("chat", "raw", "raw_nonthinking"):
                    payload = {
                        "model": "qwen3:4b-instruct", "stream": False,
                        "options": {"seed": 42, "temperature": 0.7, "top_k": 20,
                                    "top_p": 0.8, "num_predict": 2048},
                    }
                    if arm == "chat":
                        endpoint = "/api/chat"
                        payload.update(messages=messages, think=False)
                    else:
                        endpoint = "/api/generate"
                        suffix = "<think>\n\n</think>\n\n" if arm == "raw_nonthinking" else ""
                        payload.update(prompt=prompt + suffix, raw=True)
                    response = await client.post(endpoint, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    text = (data.get("message", {}).get("content", "") if arm == "chat"
                            else data.get("response", ""))
                    passed, failures = evaluation.score_answer(text, case)
                    row["arms"].append({
                        "arm": arm, "response": text, "rubric_passed": passed,
                        "rubric_failures": failures, "done": data.get("done"),
                        "done_reason": data.get("done_reason"),
                        "prompt_eval_count": data.get("prompt_eval_count"),
                        "eval_count": data.get("eval_count"),
                        "separate_thinking_present": bool(data.get("thinking") or
                            data.get("message", {}).get("thinking")),
                    })
                    print(case["id"], arm, passed, data.get("done_reason"), flush=True)
                result["cases"].append(row)
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
