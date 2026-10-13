"""Synthetic-only Groq probe; outputs token counts/status, never credentials/content."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.ports.models import CancellationToken, ModelMessage, ModelRequest, Privacy, ToolCall, ToolDefinition
from siro.services.agent.context import ContextBudgetModel
from siro.services.agent.native_context import GPTOSSBudget


async def main() -> None:
    root = Path(__file__).parents[4]
    key = None
    for filename in (".env", ".env.local"):
        path = root / filename
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            if line.startswith("SIRO_OPENAI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    if not key:
        raise RuntimeError("configured provider credential unavailable")
    usages: list[dict[str, int]] = []

    class Transport:
        async def post(self, url, payload, headers, timeout):
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"provider status {response.status_code}")
            data = response.json()
            usages.append({"prompt_tokens": data["usage"]["prompt_tokens"],
                           "completion_tokens": data["usage"]["completion_tokens"]})
            return data

    adapter = OpenAICompatibleAdapter(
        base_url="https://api.groq.com/openai", api_key=key,
        model="openai/gpt-oss-20b", transport=Transport(),
    )
    budget = GPTOSSBudget(root / ".siro-data/tokenizers/gpt-oss-20b", adapter.request_payload)
    wrapper = ContextBudgetModel(adapter, max_bytes=65536, token_budget=budget)
    rows = []
    for name, request in [
        ("plain", ModelRequest("Synthetic token fixture: reply OK, do not use tools.", "synthetic", Privacy.CLOUD_ALLOWED, max_output_tokens=128)),
        ("paired_tool", ModelRequest("synthetic", "synthetic", Privacy.CLOUD_ALLOWED, max_output_tokens=128,
            tools=(ToolDefinition("fixture_inspect", "Synthetic fixture only; no execution.", {"type":"object", "properties":{"flag":{"type":"boolean"}}}),),
            messages=(ModelMessage("system", "Synthetic tokenizer verification; do not call tools."),
                      ModelMessage("user", "Please reply OK."),
                      ModelMessage("assistant", "", (ToolCall("fixture", "fixture_inspect", {"flag":True}),)),
                      ModelMessage("tool", '{"synthetic":true}', tool_call_id="fixture"))))
    ]:
        reference = budget.validate(request)
        _ = [chunk async for chunk in wrapper.stream(request, CancellationToken())]
        usage = usages[-1]
        covered = usage["prompt_tokens"] <= reference + 256
        row = {"case":name,"reference_input_tokens":reference,**usage,"safety_tokens":256,"server_count_covered":covered}
        rows.append(row)
        print(json.dumps(row))
        assert covered, "server framing exceeds configured safety allowance"
    (Path(__file__).parent / "real-provider-counts.json").write_text(json.dumps(rows,indent=2)+"\n")


if __name__ == "__main__":
    asyncio.run(main())
