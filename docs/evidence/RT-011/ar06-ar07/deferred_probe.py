"""Synthetic gate evidence; no provider, private data, or tool effects."""
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from siro.core.consolidation import ConsolidationScheduler
from siro.ports.models import ModelMessage, ModelRequest, Privacy
from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.services.agent.native_context import GPTOSSBudget

async def main():
    class Fake:
        async def run(self, *args, **kwargs):
            return None
    scheduler = ConsolidationScheduler(Fake())
    for index in range(100):
        await scheduler.schedule(str(index), 'synthetic', (), now=datetime.now(UTC), idle=True, resources_available=True)
    await asyncio.sleep(0)
    retained = len(scheduler._runs)
    active = sum(not item.task.done() for item in scheduler._runs.values())
    await scheduler.close()
    adapter = OpenAICompatibleAdapter(base_url='https://api.groq.com/openai', api_key='synthetic', model='openai/gpt-oss-20b')
    budget = GPTOSSBudget(Path('.siro-data/tokenizers/gpt-oss-20b'), adapter.request_payload)
    messages = [ModelMessage('system', 'Synthetic goal and authorization preserved.')]
    for index in range(6):
        messages.extend([ModelMessage('user', '合成日常對話。' * 100), ModelMessage('assistant', '合成回答。' * 100)])
    request = ModelRequest('synthetic', 'goal', Privacy.CLOUD_ALLOWED, messages=tuple(messages), max_output_tokens=512)
    count = budget.validate(request)
    print(json.dumps({'scheduler_completed_retained': retained, 'scheduler_active': active, 'after_close': len(scheduler._runs), 'six_pairs_reference_tokens': count, 'summary_need_proven': False}, indent=2))

asyncio.run(main())
