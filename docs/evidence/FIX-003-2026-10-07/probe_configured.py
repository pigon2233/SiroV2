"""Two bounded synthetic requests; never replay a private conversation."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from siro.adapters.models.openai_compatible import (
    OpenAICompatibleAdapter,
    ProviderOutputTruncated,
)
from siro.ports.models import CancellationToken, ModelRequest, Privacy


async def main() -> bool:
    if "--run-configured" not in sys.argv:
        raise SystemExit("Explicit --run-configured required for two synthetic provider requests")
    root = Path(__file__).resolve().parents[3]
    allowed = {"SIRO_OPENAI_BASE_URL", "SIRO_OPENAI_MODEL", "SIRO_OPENAI_API_KEY"}
    for line in (root / ".env.local").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.removeprefix("export ").split("=", 1)
            if key.strip() in allowed:
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    model = OpenAICompatibleAdapter(
        base_url=os.environ["SIRO_OPENAI_BASE_URL"],
        api_key=os.environ["SIRO_OPENAI_API_KEY"],
        model=os.environ["SIRO_OPENAI_MODEL"],
        timeout=30,
    )
    cases = (
        ("normal", "請只回答四個字：連線正常。", 512),
        ("output_limit", "請用繁體中文寫一篇一千字的太空探險故事。", 8),
    )
    results: list[dict[str, object]] = []
    for name, prompt, budget in cases:
        start = time.monotonic()
        text = ""
        finished = False
        error = None
        try:
            async for chunk in model.stream(
                ModelRequest(prompt, f"synthetic-fix003-{name}", Privacy.CLOUD_ALLOWED, budget),
                CancellationToken(),
            ):
                text += chunk.text
                finished |= chunk.kind == "finished"
        except Exception as failure:
            error = type(failure).__name__  # No provider headers/body/credentials in evidence.
        passed = (finished and bool(text) and error is None) if name == "normal" else (
            not finished and error == ProviderOutputTruncated.__name__
        )
        results.append({
            "case": name, "max_output_tokens": budget,
            "seconds": round(time.monotonic() - start, 3),
            "partial_characters": len(text), "finished": finished,
            "error": error, "passed": passed,
        })
    print(json.dumps({"synthetic_only": True, "requests": 2, "results": results}, ensure_ascii=False))
    return all(row["passed"] for row in results)


if __name__ == "__main__":
    raise SystemExit(not asyncio.run(main()))
